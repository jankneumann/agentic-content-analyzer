"""OpenBao secrets provider for profile-based configuration.

Integrates OpenBao (open-source Vault fork) into the settings resolution
chain. When ``BAO_ADDR`` is set, secrets are fetched from the KV v2 engine
and injected as a high-priority settings source -- above profiles and .env
but below explicit environment variables.

Resolution order with OpenBao enabled::

    1. Environment variables (always win)
    2. OpenBao KV v2 (this module)
    3. Profile values (profiles/{name}.yaml)
    4. .env file
    5. Defaults

Usage::

    export BAO_ADDR=http://localhost:8200
    export BAO_ROLE_ID=newsletter-app
    export BAO_SECRET_ID=<secret-id>

    # Or for dev mode:
    export BAO_ADDR=http://localhost:8200
    export BAO_TOKEN=dev-root-token
"""

from __future__ import annotations

import atexit
import logging
import os
import threading
import time
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

try:
    import hvac  # type: ignore[import-untyped]
except ImportError:
    hvac = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level cache (process lifetime, thread-safe)
# ---------------------------------------------------------------------------
_bao_lock = threading.Lock()
_bao_cache: dict[str, str] | None = None
_bao_checked = False
_token_manager: _BaoTokenManager | None = None
# Authenticated client and (mount, path) kept after a successful load so an
# on-demand refresh (``refresh_bao_secrets``) reuses them instead of logging in
# again. ``_last_fetch_at`` is the monotonic time of the last fetch ATTEMPT from
# any path (initial load, token manager, on-demand refresh); it bounds how often
# callers can make this process read OpenBao.
_bao_client: Any | None = None
_bao_location: tuple[str, str] | None = None
_last_fetch_at: float | None = None

# Default lower bound between two on-demand refreshes, process-wide.
DEFAULT_REFRESH_MIN_INTERVAL_S = 60.0


def _is_bao_configured() -> bool:
    """Check if OpenBao environment variables are present."""
    return bool(os.environ.get("BAO_ADDR"))


def _configured_location() -> tuple[str, str]:
    """Return the ``(mount, path)`` of the KV v2 secret from ``BAO_*`` env vars."""
    return (
        os.environ.get("BAO_MOUNT_PATH", "secret"),
        os.environ.get("BAO_SECRET_PATH", "newsletter"),
    )


def _authenticate_client(client: Any) -> tuple[Any, int | None]:
    """Authenticate an hvac client and return (client, token_ttl_seconds).

    Uses AppRole when ``BAO_ROLE_ID`` + ``BAO_SECRET_ID`` are set,
    otherwise falls back to direct token auth via ``BAO_TOKEN``.

    Returns:
        Tuple of (authenticated client, token TTL in seconds or None for
        token auth where TTL is unknown/infinite).
    """
    role_id = os.environ.get("BAO_ROLE_ID")
    secret_id = os.environ.get("BAO_SECRET_ID")
    token = os.environ.get("BAO_TOKEN")

    if role_id and secret_id:
        resp = client.auth.approle.login(role_id=role_id, secret_id=secret_id)
        ttl = resp.get("auth", {}).get("lease_duration")
        logger.info(
            "bao.auth_success: authenticated via AppRole (role=%s, ttl=%ss)",
            role_id,
            ttl,
        )
        return client, ttl
    elif token:
        client.token = token
        logger.info("bao.auth_success: authenticated via token")
        return client, None
    else:
        logger.warning(
            "bao.auth_failure: BAO_ADDR is set but no auth credentials "
            "(need BAO_ROLE_ID+BAO_SECRET_ID or BAO_TOKEN)"
        )
        return client, None


def _fetch_secrets(client: Any, mount_path: str, secret_path: str) -> dict[str, str]:
    """Read secrets from KV v2 and return as flat dict."""
    response = client.secrets.kv.v2.read_secret_version(
        path=secret_path,
        mount_point=mount_path,
    )
    data = response.get("data", {}).get("data", {})
    return {k: v for k, v in data.items() if isinstance(v, str)}


def _load_bao_secrets() -> dict[str, str]:
    """Fetch all secrets from OpenBao KV v2 (thread-safe).

    Uses a lock to ensure only one thread performs the initial fetch.
    Subsequent calls return the cached result.

    Returns:
        Flat dict of secret key -> value. Empty dict on any failure.
    """
    global _bao_cache, _bao_checked, _token_manager, _bao_client, _bao_location, _last_fetch_at

    # Fast path: already loaded
    if _bao_checked:
        return _bao_cache or {}

    with _bao_lock:
        # Double-check after acquiring lock
        if _bao_checked:
            return _bao_cache or {}

        # _bao_checked is set immediately before every return below, always
        # AFTER any _bao_cache write. Setting it first opened a window in which
        # the lockless fast path above saw checked=True while the cache was
        # still None and returned a fresh {} instead of the shared dict —
        # observed in CI as TestThreadSafety failing `r is results[0]`. The
        # 028d446c logging change widened the window (real stderr I/O between
        # the two writes) but the race predates it. The lock cannot protect
        # readers that never take it; the ORDER of the two writes is the
        # invariant.
        if not _is_bao_configured():
            _bao_checked = True
            return {}

        if hvac is None:
            logger.debug(
                "bao.connection_error: hvac not installed -- install with: pip install '.[vault]'"
            )
            _bao_checked = True
            return {}

        bao_addr = os.environ["BAO_ADDR"]
        mount_path, secret_path = _configured_location()

        try:
            _last_fetch_at = time.monotonic()
            client = hvac.Client(url=bao_addr, timeout=10)
            client, token_ttl = _authenticate_client(client)

            if not client.is_authenticated():
                logger.warning("bao.auth_failure: authentication failed at %s", bao_addr)
                _bao_checked = True
                return {}

            secrets = _fetch_secrets(client, mount_path, secret_path)

            # Atomic cache update (reference swap)
            _bao_cache = secrets
            _bao_client = client
            _bao_location = (mount_path, secret_path)
            logger.info(
                "bao.secrets_loaded: loaded %d secrets from %s/%s",
                len(secrets),
                mount_path,
                secret_path,
            )

            # Start token refresh manager for AppRole auth with known TTL
            if token_ttl and token_ttl > 0:
                _token_manager = _BaoTokenManager(
                    client=client,
                    mount_path=mount_path,
                    secret_path=secret_path,
                    ttl_seconds=token_ttl,
                )
                _token_manager.start()

            _bao_checked = True
            return secrets

        except Exception:
            logger.warning(
                "bao.connection_error: failed to load secrets from %s",
                bao_addr,
                exc_info=True,
            )
            _bao_checked = True
            return {}


def get_bao_secret(key: str) -> str | None:
    """Resolve a single secret from OpenBao.

    Args:
        key: The secret key (e.g. ``ANTHROPIC_API_KEY``)

    Returns:
        Secret value if found, None otherwise.
    """
    secrets = _load_bao_secrets()
    return secrets.get(key)


def get_bao_secrets() -> Mapping[str, str]:
    """Return a read-only view of the current OpenBao cache.

    Loads once on first use; afterwards every call reads the module-level
    cache reference, so a swap by the token manager, ``refresh_bao_secrets()``
    or ``apply_bao_local_write()`` is visible on the next call with no
    network I/O. The view is of one snapshot: a later swap replaces the dict
    rather than mutating it, so a caller reading two keys from one view sees
    a consistent pair.
    """
    return MappingProxyType(_load_bao_secrets())


def refresh_bao_secrets(*, min_interval_s: float = DEFAULT_REFRESH_MIN_INTERVAL_S) -> bool:
    """Re-read the KV v2 secret now, at most once per ``min_interval_s``.

    The bound is process-wide and counts every fetch attempt (initial load,
    token-manager refresh, earlier on-demand refreshes, successful or not),
    so callers that just saw an auth failure cannot hammer OpenBao. Works
    for token and AppRole auth: the client authenticated at load time is
    reused, and one re-authentication is tried when the read fails (an
    AppRole token may have expired between manager refreshes).

    Returns:
        True when the cache was replaced with freshly read values; False when
        OpenBao is not configured, the call was throttled, or the read failed.
        Never raises.
    """
    global _bao_cache, _bao_client, _bao_location, _last_fetch_at

    # Ensure the one-time load happened (it takes the lock itself).
    _load_bao_secrets()
    if not _is_bao_configured() or hvac is None:
        return False

    with _bao_lock:
        now = time.monotonic()
        if _last_fetch_at is not None and now - _last_fetch_at < min_interval_s:
            logger.debug(
                "bao.refresh_throttled: last fetch %.1fs ago (min interval %.1fs)",
                now - _last_fetch_at,
                min_interval_s,
            )
            return False
        _last_fetch_at = now

        mount_path, secret_path = _bao_location or _configured_location()
        try:
            client = _bao_client
            if client is None:
                # The boot-time load failed; build the client it never kept.
                client, _ttl = _authenticate_client(
                    hvac.Client(url=os.environ["BAO_ADDR"], timeout=10)
                )
            try:
                secrets = _fetch_secrets(client, mount_path, secret_path)
            except Exception:
                client, _ttl = _authenticate_client(client)
                secrets = _fetch_secrets(client, mount_path, secret_path)
        except Exception as exc:
            # Exception type only: hvac errors can carry server response text.
            logger.warning(
                "bao.connection_error: on-demand refresh of %s/%s failed (%s)",
                mount_path,
                secret_path,
                type(exc).__name__,
            )
            return False

        # Atomic cache update (reference swap)
        _bao_cache = secrets
        _bao_client = client
        _bao_location = (mount_path, secret_path)
        logger.info(
            "bao.secrets_refreshed: reloaded %d secrets from %s/%s on demand",
            len(secrets),
            mount_path,
            secret_path,
        )
        return True


def is_bao_configured() -> bool:
    """True when ``BAO_ADDR`` is set (whether or not the load succeeded)."""
    return _is_bao_configured()


def get_authenticated_bao_client() -> Any | None:
    """The hvac client this process authenticated for its OpenBao reads, if any.

    For a worker that writes back a value it just learned (a rotated X ``ct0``)
    through ``BaoSink``: reusing this client avoids a second AppRole login. It
    is ``None`` when OpenBao is not configured or no load has succeeded yet.
    The client carries a token: never log it or put it in a message.
    """
    _load_bao_secrets()
    return _bao_client


def apply_bao_local_write(values: Mapping[str, str]) -> list[str]:
    """Merge values this process just PATCHed into OpenBao into the cache.

    Call after a successful ``BaoSink.write()`` so the next read sees the new
    value without an OpenBao round trip. The merge builds a new dict and swaps
    the reference under the lock, so lockless readers see either the old or
    the new snapshot, never a partial one. Non-string values are ignored, as
    ``_fetch_secrets`` ignores them.

    Returns:
        The key names applied (never values).
    """
    global _bao_cache

    _load_bao_secrets()
    updates = {k: v for k, v in values.items() if isinstance(k, str) and isinstance(v, str)}
    if not updates:
        return []
    with _bao_lock:
        merged = dict(_bao_cache or {})
        merged.update(updates)
        _bao_cache = merged
    names = sorted(updates)
    logger.info("bao.local_write_applied: %s", ", ".join(names))
    return names


def clear_bao_cache() -> None:
    """Clear the cached OpenBao secrets. Useful for testing."""
    global _bao_cache, _bao_checked, _token_manager, _bao_client, _bao_location, _last_fetch_at
    if _token_manager is not None:
        _token_manager.stop()
        _token_manager = None
    _bao_cache = None
    _bao_checked = False
    _bao_client = None
    _bao_location = None
    _last_fetch_at = None


# ---------------------------------------------------------------------------
# Token Lifecycle Manager
# ---------------------------------------------------------------------------


class _BaoTokenManager:
    """Background token refresh for long-running processes.

    Schedules a timer at 75% of the token TTL to re-authenticate via
    AppRole and reload secrets. Cache is updated atomically (reference
    swap). Only activates for AppRole auth where TTL is known.
    """

    def __init__(
        self,
        client: Any,
        mount_path: str,
        secret_path: str,
        ttl_seconds: int,
    ) -> None:
        self._client = client
        self._mount_path = mount_path
        self._secret_path = secret_path
        self._ttl_seconds = ttl_seconds
        self._timer: threading.Timer | None = None
        self._stopped = False

    def start(self) -> None:
        """Schedule the first refresh."""
        self._schedule_refresh()
        atexit.register(self.stop)

    def stop(self) -> None:
        """Cancel pending refresh timer."""
        if self._stopped:
            return
        self._stopped = True
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        logger.debug("bao.token_manager_stopped: background refresh cancelled")

    def _schedule_refresh(self) -> None:
        """Schedule refresh at 75% of current TTL."""
        if self._stopped:
            return
        delay = max(int(self._ttl_seconds * 0.75), 1)
        self._timer = threading.Timer(delay, self._refresh)
        self._timer.daemon = True
        self._timer.start()

    def _refresh(self) -> None:
        """Re-authenticate and reload secrets."""
        global _bao_cache, _bao_client, _last_fetch_at

        if self._stopped:
            return

        try:
            self._client, new_ttl = _authenticate_client(self._client)

            if not self._client.is_authenticated():
                logger.warning("bao.auth_failure: token refresh authentication failed")
                return

            # Fetch and swap under the lock so an on-demand refresh or a local
            # write-back (apply_bao_local_write) is ordered against this fetch
            # and can never be overwritten by a read that started before it.
            with _bao_lock:
                _last_fetch_at = time.monotonic()
                secrets = _fetch_secrets(self._client, self._mount_path, self._secret_path)

                # Atomic cache update
                _bao_cache = secrets
                _bao_client = self._client

            if new_ttl and new_ttl > 0:
                self._ttl_seconds = new_ttl

            logger.info(
                "bao.token_refreshed: reloaded %d secrets (next refresh in %ds)",
                len(secrets),
                int(self._ttl_seconds * 0.75),
            )

            self._schedule_refresh()

        except Exception:
            logger.warning("bao.connection_error: token refresh failed", exc_info=True)
            # Schedule retry at the same interval
            self._schedule_refresh()


# ---------------------------------------------------------------------------
# Pydantic Settings Source
# ---------------------------------------------------------------------------


class BaoSettingsSource:
    """Pydantic-compatible settings source backed by OpenBao KV v2.

    Implements enough of the ``PydanticBaseSettingsSource`` protocol to
    be used in ``settings_customise_sources()``. Loads all secrets once
    from OpenBao and maps UPPER_CASE vault keys to lower_case Settings
    field names.

    Exception-safe: ``__call__()`` and ``get_field_value()`` catch all
    exceptions and return empty results to ensure ``Settings()``
    instantiation never fails due to vault issues.
    """

    def __init__(self, settings_cls: type[Any]) -> None:
        self._settings_cls = settings_cls
        self._secrets: dict[str, str] | None = None

    def _load_once(self) -> dict[str, str]:
        if self._secrets is None:
            try:
                raw = _load_bao_secrets()
                self._secrets = {k.lower(): v for k, v in raw.items()}
            except Exception:
                logger.warning(
                    "bao.connection_error: BaoSettingsSource failed to load",
                    exc_info=True,
                )
                self._secrets = {}
        return self._secrets

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        """Get value for a specific field from OpenBao."""
        try:
            data = self._load_once()
            value = data.get(field_name)
            return value, field_name, False
        except Exception:
            return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        """Return all settings from OpenBao."""
        try:
            return self._load_once()
        except Exception:
            logger.warning(
                "bao.connection_error: BaoSettingsSource.__call__() failed",
                exc_info=True,
            )
            return {}
