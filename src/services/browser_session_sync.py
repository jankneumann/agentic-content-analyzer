"""Server-side browser-session sync: validate once, PATCH OpenBao once.

The admin endpoint ``PUT /api/v1/browser-sessions/{substack,x}``
(:mod:`src.api.browser_session_routes`) hands freshly read browser cookies to
:func:`sync_browser_session`, which

1. refuses before any network I/O unless OpenBao is configured for writes
   (:func:`openbao_write_requirements_missing`). The server never falls back
   to ``.secrets.yaml``, the environment, or Railway;
2. authenticates the OpenBao sink, so a broken store costs no request to the site;
3. proves the session works with the SAME single request the capture CLI makes
   (:mod:`src.ingestion.browser_session_validation`), and writes nothing when
   the site refuses it;
4. writes every key of the site in ONE :class:`~src.cli.secret_sinks.BaoSink`
   KV v2 merge-PATCH, stamped with one ``saved_at`` (so the X
   ``auth_token``/``ct0`` pair never lands torn and sibling keys are untouched);
5. applies the same values and ``saved_at`` to this process's credential cache.

Nothing here logs, returns or raises a cookie value: exceptions carry site
names, key names, status codes, the OpenBao target and exception type names.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from src.cli.secret_sinks import BaoSink, SecretSink, SecretSinkError
from src.config import bao_secrets
from src.config.credentials import (
    SUBSTACK_SESSION_COOKIE,
    X_AUTH_TOKEN,
    X_CT0,
    get_credential_provider,
)
from src.config.secrets import saved_at_key
from src.ingestion.browser_session_validation import (
    SessionValidationError,
    SessionValidator,
    new_validation_client,
    validate_substack_session,
    validate_x_session,
)

__all__ = [
    "BROWSER_SESSION_SITES",
    "BrowserSessionSite",
    "BrowserSessionStoreUnavailableError",
    "BrowserSessionSyncResult",
    "BrowserSessionUnreachableError",
    "BrowserSessionWriteError",
    "build_bao_sink",
    "openbao_write_requirements_missing",
    "sync_browser_session",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BrowserSessionSite:
    """One site whose session the endpoint accepts."""

    site: str
    title: str
    keys: tuple[str, ...]
    """Credential keys written together, in order."""
    validate: SessionValidator


BROWSER_SESSION_SITES: Mapping[str, BrowserSessionSite] = {
    "substack": BrowserSessionSite(
        site="substack",
        title="Substack",
        keys=(SUBSTACK_SESSION_COOKIE,),
        validate=validate_substack_session,
    ),
    "x": BrowserSessionSite(
        site="x",
        title="X",
        keys=(X_AUTH_TOKEN, X_CT0),
        validate=validate_x_session,
    ),
}


class BrowserSessionStoreUnavailableError(Exception):
    """OpenBao is not configured for writes on this server.

    ``missing`` names the unmet requirements (environment variable names or the
    client library), never a value.
    """

    def __init__(self, missing: list[str]) -> None:
        super().__init__(
            "Browser sessions are written only to OpenBao, which is not configured "
            f"on this server (missing: {', '.join(missing)})"
        )
        self.missing = missing


class BrowserSessionWriteError(Exception):
    """OpenBao refused or failed the write. Messages never contain values."""


class BrowserSessionUnreachableError(Exception):
    """The site could not be reached (or failed) to validate the session."""


@dataclass(frozen=True)
class BrowserSessionSyncResult:
    """What was written. Carries key names and a timestamp, never values."""

    site: str
    keys_written: list[str]
    saved_at: datetime


def openbao_write_requirements_missing(environ: Mapping[str, str] | None = None) -> list[str]:
    """Return what this process lacks to PATCH OpenBao; empty when it can write.

    Mirrors the checks of the sink's default client, without any network I/O.
    """
    env = os.environ if environ is None else environ
    missing: list[str] = []
    if not env.get("BAO_ADDR"):
        missing.append("BAO_ADDR")
    if not ((env.get("BAO_ROLE_ID") and env.get("BAO_SECRET_ID")) or env.get("BAO_TOKEN")):
        missing.append("BAO_ROLE_ID+BAO_SECRET_ID or BAO_TOKEN")
    if bao_secrets.hvac is None:
        missing.append("hvac (pip install '.[vault]')")
    return missing


def build_bao_sink(saved_at: datetime) -> SecretSink:
    """The OpenBao sink for one sync, stamping ``<KEY>_SAVED_AT`` with ``saved_at``.

    Authenticates from ``BAO_*`` on first use (the API's AppRole needs only the
    ``patch`` capability on the path). Silent: the route reports the write.
    """
    return BaoSink(clock=lambda: saved_at, echo=None)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def sync_browser_session(
    site: str,
    values: Mapping[str, str],
    *,
    sink_factory: Callable[[datetime], SecretSink] | None = None,
    http_client_factory: Callable[[], httpx.Client] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> BrowserSessionSyncResult:
    """Validate ``values`` against ``site`` and write them to OpenBao once.

    ``values`` maps the site's credential keys (:attr:`BrowserSessionSite.keys`)
    to cookie values. The ``None`` seams resolve to the module-level defaults at
    call time, so tests can replace them.

    Raises:
        BrowserSessionStoreUnavailableError: OpenBao is not configured (no I/O done).
        SessionValidationError: the site refused the session (nothing written).
        BrowserSessionUnreachableError: the site could not be reached or failed.
        BrowserSessionWriteError: OpenBao authentication or the PATCH failed.
    """
    spec = BROWSER_SESSION_SITES[site]
    if set(values) != set(spec.keys):
        raise ValueError(f"{spec.title} sessions carry exactly {', '.join(spec.keys)}")

    missing = openbao_write_requirements_missing()
    if missing:
        raise BrowserSessionStoreUnavailableError(missing)

    saved_at = (clock or _utc_now)()
    sink = (sink_factory or build_bao_sink)(saved_at)
    try:
        sink.check()
    except SecretSinkError as exc:
        logger.warning(
            "browser_sessions.store_unavailable site=%s (%s)",
            site,
            type(exc.__cause__ or exc).__name__,
        )
        raise BrowserSessionWriteError(str(exc)) from None

    http = (http_client_factory or new_validation_client)()
    try:
        spec.validate(values, http)
    except SessionValidationError as exc:
        logger.warning(
            "browser_sessions.validation_failed site=%s reason=%s status=%s",
            site,
            exc.reason,
            exc.status_code,
        )
        if exc.upstream_unavailable:
            raise BrowserSessionUnreachableError(str(exc)) from None
        raise
    except httpx.HTTPError as exc:
        logger.warning(
            "browser_sessions.validation_unreachable site=%s (%s)", site, type(exc).__name__
        )
        raise BrowserSessionUnreachableError(
            f"Could not reach {spec.title} to validate the session ({type(exc).__name__})"
        ) from None
    finally:
        http.close()

    try:
        written = sink.write({key: values[key] for key in spec.keys})
    except SecretSinkError as exc:
        logger.warning(
            "browser_sessions.write_failed site=%s target=%s (%s)",
            site,
            sink.target,
            type(exc.__cause__ or exc).__name__,
        )
        raise BrowserSessionWriteError(str(exc)) from None

    try:
        get_credential_provider().apply_local_write(dict(values), saved_at=saved_at)
    except Exception as exc:
        # OpenBao already holds the new values; the next refresh picks them up.
        logger.warning(
            "browser_sessions.local_cache_not_refreshed site=%s (%s)", site, type(exc).__name__
        )

    keys_written = [*written, *(saved_at_key(key) for key in written)]
    logger.info(
        "browser_sessions.synced site=%s keys=%s target=%s saved_at=%s",
        site,
        ",".join(keys_written),
        sink.target,
        saved_at.isoformat(),
    )
    return BrowserSessionSyncResult(site=site, keys_written=keys_written, saved_at=saved_at)
