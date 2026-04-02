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


def _is_bao_configured() -> bool:
    """Check if OpenBao environment variables are present."""
    return bool(os.environ.get("BAO_ADDR"))


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
    global _bao_cache, _bao_checked, _token_manager

    # Fast path: already loaded
    if _bao_checked:
        return _bao_cache or {}

    with _bao_lock:
        # Double-check after acquiring lock
        if _bao_checked:
            return _bao_cache or {}

        _bao_checked = True

        if not _is_bao_configured():
            return {}

        if hvac is None:
            logger.debug(
                "bao.connection_error: hvac not installed -- install with: pip install '.[vault]'"
            )
            return {}

        bao_addr = os.environ["BAO_ADDR"]
        mount_path = os.environ.get("BAO_MOUNT_PATH", "secret")
        secret_path = os.environ.get("BAO_SECRET_PATH", "newsletter")

        try:
            client = hvac.Client(url=bao_addr, timeout=10)
            client, token_ttl = _authenticate_client(client)

            if not client.is_authenticated():
                logger.warning("bao.auth_failure: authentication failed at %s", bao_addr)
                return {}

            secrets = _fetch_secrets(client, mount_path, secret_path)

            # Atomic cache update (reference swap)
            _bao_cache = secrets
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

            return secrets

        except Exception:
            logger.warning(
                "bao.connection_error: failed to load secrets from %s",
                bao_addr,
                exc_info=True,
            )
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


def clear_bao_cache() -> None:
    """Clear the cached OpenBao secrets. Useful for testing."""
    global _bao_cache, _bao_checked, _token_manager
    if _token_manager is not None:
        _token_manager.stop()
        _token_manager = None
    _bao_cache = None
    _bao_checked = False


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
        global _bao_cache

        if self._stopped:
            return

        try:
            self._client, new_ttl = _authenticate_client(self._client)

            if not self._client.is_authenticated():
                logger.warning("bao.auth_failure: token refresh authentication failed")
                return

            secrets = _fetch_secrets(self._client, self._mount_path, self._secret_path)

            # Atomic cache update
            _bao_cache = secrets

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
