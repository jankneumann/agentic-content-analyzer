"""Live credential provider for secrets that rotate while a worker runs.

``settings`` (``get_settings()``) is built once behind ``lru_cache``, so an
adapter that reads ``settings.substack_session_cookie`` keeps the boot-time
value for the life of the process. Browser-session cookies rotate far more
often than that. :class:`CredentialProvider` resolves a credential at call
time instead:

1. the OpenBao cache (:mod:`src.config.bao_secrets`) - read from memory on
   every call, never from the network; the AppRole token manager, an explicit
   :meth:`CredentialProvider.refresh`, or :meth:`CredentialProvider.apply_local_write`
   swap that cache atomically;
2. ``Settings`` (environment, profile, ``.secrets.yaml``) - the boot-time value.

OpenBao is consulted first even though ``Settings`` ranks environment variables
above OpenBao: for a credential that rotates, the live store is authoritative
and a process environment variable is only a boot-time snapshot. Callers that
need a fixed value (a per-request override) pass it to the adapter directly.

Only the credentials registered in :data:`BROWSER_SESSION_CREDENTIALS` are
served, each with an explicit OpenBao/env key <-> ``Settings`` field mapping.

Logging: this module logs credential NAMES only, never values. Metadata
(``saved_at``, ``last_verified_at``) is never secret.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.config import bao_secrets
from src.config.secrets import SAVED_AT_SUFFIX, saved_at_key

logger = logging.getLogger(__name__)

SUBSTACK_SESSION_COOKIE = "SUBSTACK_SESSION_COOKIE"
X_AUTH_TOKEN = "X_AUTH_TOKEN"
X_CT0 = "X_CT0"


@dataclass(frozen=True)
class CredentialSpec:
    """Explicit mapping for one rotating credential."""

    name: str
    """OpenBao key and environment variable name, e.g. ``X_CT0``."""
    settings_field: str
    """``Settings`` attribute holding the boot-time value, e.g. ``x_ct0``."""
    label: str
    """Operator-facing identifier (site + cookie name), e.g. ``x.ct0``."""


BROWSER_SESSION_CREDENTIALS: Mapping[str, CredentialSpec] = {
    spec.name: spec
    for spec in (
        CredentialSpec(SUBSTACK_SESSION_COOKIE, "substack_session_cookie", "substack.sid"),
        CredentialSpec(X_AUTH_TOKEN, "x_auth_token", "x.auth_token"),
        CredentialSpec(X_CT0, "x_ct0", "x.ct0"),
    )
}


class UnknownCredentialError(KeyError):
    """Raised for a credential name with no registered :class:`CredentialSpec`."""


@dataclass(frozen=True)
class CredentialMetadata:
    """Non-secret facts about a credential. Never carries the value."""

    name: str
    label: str
    present: bool
    source: str | None
    """``"openbao"``, ``"settings"``, or ``None`` when the credential is absent."""
    saved_at: datetime | None
    """When a secret sink last wrote the value (``<NAME>_SAVED_AT`` in OpenBao)."""
    last_verified_at: datetime | None
    """When THIS process last saw the CURRENT value accepted by the remote site."""


def _parse_saved_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _fingerprint(value: str) -> bytes:
    # In-memory only, used to tell whether the verified value is still current.
    return hashlib.sha256(value.encode("utf-8")).digest()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _default_settings() -> Any:
    from src.config.settings import get_settings

    return get_settings()


class CredentialProvider:
    """Resolve rotating credentials at call time (OpenBao cache, then Settings).

    Thread-safe. ``get()`` and ``metadata()`` never do network I/O once the
    OpenBao cache has loaded; only :meth:`refresh` reads OpenBao, and at most
    once per interval process-wide.

    ``last_verified_at`` is kept in process memory only (see ``mark_verified``):
    writing it to OpenBao on every successful run would turn each ingestion
    into a secret-store write. A cross-process record is left to its consumer
    (``aca auth status``).
    """

    def __init__(
        self,
        *,
        settings_factory: Callable[[], Any] | None = None,
        bao_reader: Callable[[], Mapping[str, str]] | None = None,
        bao_refresher: Callable[..., bool] | None = None,
        bao_writer: Callable[[Mapping[str, str]], list[str]] | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._settings_factory = settings_factory or _default_settings
        self._bao_reader = bao_reader or bao_secrets.get_bao_secrets
        self._bao_refresher = bao_refresher or bao_secrets.refresh_bao_secrets
        self._bao_writer = bao_writer or bao_secrets.apply_bao_local_write
        self._clock = clock
        self._lock = threading.Lock()
        self._verified: dict[str, tuple[datetime, bytes]] = {}

    # -- resolution -----------------------------------------------------

    @staticmethod
    def spec(name: str) -> CredentialSpec:
        """Return the registered spec for ``name`` or raise UnknownCredentialError."""
        try:
            return BROWSER_SESSION_CREDENTIALS[name]
        except KeyError:
            raise UnknownCredentialError(name) from None

    def _bao_snapshot(self) -> Mapping[str, str]:
        try:
            return self._bao_reader()
        except Exception as exc:
            logger.warning(
                "credentials.bao_unavailable: falling back to settings (%s)",
                type(exc).__name__,
            )
            return {}

    def _settings_value(self, spec: CredentialSpec) -> str | None:
        value = getattr(self._settings_factory(), spec.settings_field, None)
        if value is None:
            return None
        if hasattr(value, "get_secret_value"):
            value = value.get_secret_value()
        return value if isinstance(value, str) and value else None

    def _resolve(self, spec: CredentialSpec) -> tuple[str | None, str | None, Mapping[str, str]]:
        snapshot = self._bao_snapshot()
        value = snapshot.get(spec.name)
        if isinstance(value, str) and value:
            return value, "openbao", snapshot
        fallback = self._settings_value(spec)
        return fallback, ("settings" if fallback else None), snapshot

    def get(self, name: str) -> str | None:
        """Return the current value of credential ``name``, or None when unset."""
        value, _source, _snapshot = self._resolve(self.spec(name))
        return value

    def metadata(self, name: str) -> CredentialMetadata:
        """Return ``saved_at``/``last_verified_at`` for ``name``. Never the value."""
        spec = self.spec(name)
        value, source, snapshot = self._resolve(spec)
        # saved_at is only meaningful for the OpenBao value it sits beside.
        saved_at = (
            _parse_saved_at(snapshot.get(saved_at_key(name))) if source == "openbao" else None
        )
        last_verified_at: datetime | None = None
        with self._lock:
            verified = self._verified.get(name)
        if verified is not None and value is not None:
            at, fingerprint = verified
            if hmac.compare_digest(fingerprint, _fingerprint(value)):
                last_verified_at = at
        return CredentialMetadata(
            name=name,
            label=spec.label,
            present=value is not None,
            source=source,
            saved_at=saved_at,
            last_verified_at=last_verified_at,
        )

    # -- lifecycle ------------------------------------------------------

    def mark_verified(self, name: str, *, at: datetime | None = None) -> None:
        """Record that the current value of ``name`` was just accepted remotely.

        In-process only; a later rotation of the value clears it implicitly
        (``metadata`` reports it only while the verified value is current).
        """
        value = self.get(name)
        if value is None:
            return
        with self._lock:
            self._verified[name] = (at or self._clock(), _fingerprint(value))

    def refresh(
        self, *, min_interval_s: float = bao_secrets.DEFAULT_REFRESH_MIN_INTERVAL_S
    ) -> bool:
        """Ask OpenBao for fresh values, at most once per ``min_interval_s``.

        For callers that just saw the remote site reject a credential (401, a
        login page). Returns True when the cache was replaced. A no-op
        returning False when OpenBao is unconfigured or the call is throttled.
        """
        refreshed = bool(self._bao_refresher(min_interval_s=min_interval_s))
        logger.debug("credentials.refresh: %s", "reloaded" if refreshed else "skipped")
        return refreshed

    def apply_local_write(
        self, values: Mapping[str, str], *, saved_at: datetime | None = None
    ) -> list[str]:
        """Make values this process just wrote through ``BaoSink`` visible now.

        Call only after the sink's PATCH succeeded. Each registered credential
        without a ``<NAME>_SAVED_AT`` entry in ``values`` gets one stamped with
        ``saved_at`` (default: now), mirroring what the sink wrote. Returns the
        key names applied, never values.
        """
        stamp = (saved_at or self._clock()).astimezone(UTC).isoformat(timespec="seconds")
        payload = {k: v for k, v in values.items() if isinstance(v, str)}
        for key in list(payload):
            if key.endswith(SAVED_AT_SUFFIX):
                continue
            self.spec(key)  # only registered credentials are written back
            payload.setdefault(saved_at_key(key), stamp)
        return list(self._bao_writer(payload))


_default_provider: CredentialProvider | None = None
_default_provider_lock = threading.Lock()


def get_credential_provider() -> CredentialProvider:
    """Return the process-wide provider (backed by OpenBao and ``get_settings()``)."""
    global _default_provider
    if _default_provider is None:
        with _default_provider_lock:
            if _default_provider is None:
                _default_provider = CredentialProvider()
    return _default_provider


def reset_credential_provider() -> None:
    """Drop the process-wide provider (tests)."""
    global _default_provider
    with _default_provider_lock:
        _default_provider = None
