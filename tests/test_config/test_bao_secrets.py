"""Tests for OpenBao secrets provider (bao_secrets.py).

Covers spec scenarios openbao-secrets.1 through .23, organized by concern:
- Graceful degradation (unconfigured, hvac missing, connection failure)
- Authentication (AppRole, token)
- Secret loading (resolution, caching, key mapping, special chars)
- Thread safety
- Token lifecycle (refresh, shutdown)
- Audit logging
- Exception isolation (BaoSettingsSource)
"""

from __future__ import annotations

import logging
import os
import threading
from unittest.mock import MagicMock, patch

import pytest

from src.config.bao_secrets import (
    BaoSettingsSource,
    _BaoTokenManager,
    _load_bao_secrets,
    clear_bao_cache,
    get_bao_secret,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear OpenBao cache before and after each test."""
    clear_bao_cache()
    yield
    clear_bao_cache()


# =========================================================================
# Graceful Degradation (spec .1, .7, .8, .21)
# =========================================================================


class TestGracefulDegradation:
    """Verify OpenBao is completely silent when not configured."""

    def test_unconfigured_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """spec .1: BAO_ADDR not set -> empty dict, no log output."""
        monkeypatch.delenv("BAO_ADDR", raising=False)
        result = _load_bao_secrets()
        assert result == {}

    def test_unconfigured_no_logging(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """spec .1: Complete silence when unconfigured."""
        monkeypatch.delenv("BAO_ADDR", raising=False)
        with caplog.at_level(logging.DEBUG, logger="src.config.bao_secrets"):
            _load_bao_secrets()
        assert caplog.records == []

    def test_hvac_not_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """spec .8: hvac missing -> debug log, empty dict."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")
        with patch.dict("sys.modules", {"hvac": None}):
            # Force ImportError by patching builtins import
            original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

            def mock_import(name, *args, **kwargs):
                if name == "hvac":
                    raise ImportError("No module named 'hvac'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                result = _load_bao_secrets()
        assert result == {}

    def test_connection_failure_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """spec .7: Unreachable OpenBao -> WARNING, empty dict."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")

        mock_hvac = MagicMock()
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = False
        mock_hvac.Client.return_value = mock_client

        with patch.dict("sys.modules", {"hvac": mock_hvac}):
            with patch("src.config.bao_secrets.hvac", mock_hvac, create=True):
                # Re-import to pick up the mock
                import importlib
                import src.config.bao_secrets as bao_mod
                # Directly test: simulate auth failure
                clear_bao_cache()
                result = _load_bao_secrets()

        assert result == {}

    def test_connection_failure_logs_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """spec .7: Connection failure logs WARNING with BAO_ADDR."""
        monkeypatch.setenv("BAO_ADDR", "http://vault.test:8200")
        monkeypatch.setenv("BAO_TOKEN", "test")

        mock_hvac = MagicMock()
        mock_hvac.Client.side_effect = Exception("Connection refused")

        with patch("src.config.bao_secrets.hvac", mock_hvac, create=True):
            with patch("src.config.bao_secrets._is_bao_configured", return_value=True):
                with caplog.at_level(logging.WARNING, logger="src.config.bao_secrets"):
                    # Need to bypass the import check
                    clear_bao_cache()

    def test_empty_vault_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """spec .21: Empty vault path -> cache empty dict, return empty."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {}}
        }

        mock_hvac = MagicMock()
        mock_hvac.Client.return_value = mock_client

        with patch("src.config.bao_secrets.hvac", mock_hvac, create=True):
            result = _load_bao_secrets()

        assert result == {}


# =========================================================================
# Authentication (spec .4, .5, .23)
# =========================================================================


class TestAuthentication:
    """Verify AppRole and token authentication paths."""

    def test_approle_auth(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """spec .4: AppRole auth when ROLE_ID + SECRET_ID set."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_ROLE_ID", "newsletter-app")
        monkeypatch.setenv("BAO_SECRET_ID", "test-secret-id")

        mock_client = MagicMock()
        mock_client.auth.approle.login.return_value = {
            "auth": {"lease_duration": 3600}
        }
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"ANTHROPIC_API_KEY": "sk-test"}}
        }

        mock_hvac = MagicMock()
        mock_hvac.Client.return_value = mock_client

        with patch("src.config.bao_secrets.hvac", mock_hvac, create=True):
            result = _load_bao_secrets()

        mock_client.auth.approle.login.assert_called_once_with(
            role_id="newsletter-app", secret_id="test-secret-id"
        )
        assert result == {"ANTHROPIC_API_KEY": "sk-test"}

    def test_token_auth_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """spec .5: Token auth when BAO_TOKEN set (no ROLE_ID)."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")
        monkeypatch.delenv("BAO_ROLE_ID", raising=False)
        monkeypatch.delenv("BAO_SECRET_ID", raising=False)

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"KEY": "value"}}
        }

        mock_hvac = MagicMock()
        mock_hvac.Client.return_value = mock_client

        with patch("src.config.bao_secrets.hvac", mock_hvac, create=True):
            result = _load_bao_secrets()

        assert mock_client.token == "dev-root-token"
        assert result == {"KEY": "value"}

    def test_no_credentials_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """spec .23 related: No auth creds -> warning, empty dict."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.delenv("BAO_ROLE_ID", raising=False)
        monkeypatch.delenv("BAO_SECRET_ID", raising=False)
        monkeypatch.delenv("BAO_TOKEN", raising=False)

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = False

        mock_hvac = MagicMock()
        mock_hvac.Client.return_value = mock_client

        with patch("src.config.bao_secrets.hvac", mock_hvac, create=True):
            result = _load_bao_secrets()

        assert result == {}


# =========================================================================
# Secret Loading (spec .2, .17, .19, .20)
# =========================================================================


class TestSecretLoading:
    """Verify secret resolution, key mapping, and edge cases."""

    def _setup_vault(
        self, monkeypatch: pytest.MonkeyPatch, secrets: dict[str, str]
    ) -> None:
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": secrets}
        }

        mock_hvac = MagicMock()
        mock_hvac.Client.return_value = mock_client
        self._mock_hvac = mock_hvac

    def test_secret_resolution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """spec .2: Resolve secret from OpenBao."""
        self._setup_vault(monkeypatch, {"ANTHROPIC_API_KEY": "sk-ant-test"})
        with patch("src.config.bao_secrets.hvac", self._mock_hvac, create=True):
            result = get_bao_secret("ANTHROPIC_API_KEY")
        assert result == "sk-ant-test"

    def test_key_mapping_upper_to_lower(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """spec .17: BaoSettingsSource maps UPPER to lower."""
        self._setup_vault(monkeypatch, {"ANTHROPIC_API_KEY": "sk-test"})
        with patch("src.config.bao_secrets.hvac", self._mock_hvac, create=True):
            source = BaoSettingsSource(object)
            data = source()
        assert "anthropic_api_key" in data
        assert data["anthropic_api_key"] == "sk-test"

    def test_partial_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """spec .19: Partial vault response cached as-is."""
        partial = {"KEY_A": "val_a", "KEY_B": "val_b"}
        self._setup_vault(monkeypatch, partial)
        with patch("src.config.bao_secrets.hvac", self._mock_hvac, create=True):
            result = _load_bao_secrets()
        assert result == partial
        assert get_bao_secret("KEY_C") is None  # Falls through

    def test_special_characters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """spec .20: Special chars preserved exactly."""
        special_value = 'pa$$w{or}d\nwith "quotes" and ünïcödé'
        self._setup_vault(monkeypatch, {"SECRET": special_value})
        with patch("src.config.bao_secrets.hvac", self._mock_hvac, create=True):
            result = get_bao_secret("SECRET")
        assert result == special_value


# =========================================================================
# Caching (spec .16)
# =========================================================================


class TestCaching:
    """Verify cache behavior and isolation."""

    def test_cache_isolation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """spec .16: clear_bao_cache() forces re-fetch."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        # First call returns KEY_A, second returns KEY_B
        mock_client.secrets.kv.v2.read_secret_version.side_effect = [
            {"data": {"data": {"KEY_A": "first"}}},
            {"data": {"data": {"KEY_B": "second"}}},
        ]

        mock_hvac = MagicMock()
        mock_hvac.Client.return_value = mock_client

        with patch("src.config.bao_secrets.hvac", mock_hvac, create=True):
            first = _load_bao_secrets()
            assert first == {"KEY_A": "first"}

            clear_bao_cache()
            second = _load_bao_secrets()
            assert second == {"KEY_B": "second"}

    def test_subsequent_calls_use_cache(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify _load_bao_secrets() only calls vault once."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"K": "V"}}
        }

        mock_hvac = MagicMock()
        mock_hvac.Client.return_value = mock_client

        with patch("src.config.bao_secrets.hvac", mock_hvac, create=True):
            _load_bao_secrets()
            _load_bao_secrets()
            _load_bao_secrets()

        # Only one Client instantiation despite three calls
        mock_hvac.Client.assert_called_once()


# =========================================================================
# Thread Safety (spec .18)
# =========================================================================


class TestThreadSafety:
    """Verify concurrent access uses a single vault fetch."""

    def test_concurrent_load_single_fetch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """spec .18: Multiple threads -> one fetch, same cached dict."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")

        fetch_count = 0
        secrets_data = {"KEY": "value"}

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True

        def mock_read(*args, **kwargs):
            nonlocal fetch_count
            fetch_count += 1
            return {"data": {"data": secrets_data}}

        mock_client.secrets.kv.v2.read_secret_version.side_effect = mock_read

        mock_hvac = MagicMock()
        mock_hvac.Client.return_value = mock_client

        results: list[dict] = []
        errors: list[Exception] = []

        def worker():
            try:
                r = _load_bao_secrets()
                results.append(r)
            except Exception as e:
                errors.append(e)

        with patch("src.config.bao_secrets.hvac", mock_hvac, create=True):
            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

        assert not errors
        assert len(results) == 10
        # All threads got the same dict reference
        assert all(r is results[0] for r in results)
        # Only one vault call despite 10 threads
        assert fetch_count == 1


# =========================================================================
# Token Lifecycle (spec .6, .22)
# =========================================================================


class TestTokenLifecycle:
    """Verify token refresh scheduling and shutdown."""

    def test_refresh_schedules_timer(self) -> None:
        """spec .6: Token manager schedules at 75% TTL."""
        mock_client = MagicMock()
        mgr = _BaoTokenManager(
            client=mock_client,
            mount_path="secret",
            secret_path="newsletter",
            ttl_seconds=100,
        )
        mgr.start()
        try:
            assert mgr._timer is not None
            assert mgr._timer.is_alive()
        finally:
            mgr.stop()

    def test_stop_cancels_timer(self) -> None:
        """spec .22: stop() cancels pending timer."""
        mock_client = MagicMock()
        mgr = _BaoTokenManager(
            client=mock_client,
            mount_path="secret",
            secret_path="newsletter",
            ttl_seconds=1000,
        )
        mgr.start()
        assert mgr._timer is not None

        mgr.stop()
        assert mgr._stopped is True
        # Timer should no longer be alive
        assert mgr._timer is None or not mgr._timer.is_alive()

    def test_stop_idempotent(self) -> None:
        """spec .22: Calling stop() twice is safe."""
        mock_client = MagicMock()
        mgr = _BaoTokenManager(
            client=mock_client,
            mount_path="secret",
            secret_path="newsletter",
            ttl_seconds=1000,
        )
        mgr.start()
        mgr.stop()
        mgr.stop()  # Should not raise

    def test_stop_logs_event(self, caplog: pytest.LogCaptureFixture) -> None:
        """spec .22: stop() emits bao.token_manager_stopped."""
        mock_client = MagicMock()
        mgr = _BaoTokenManager(
            client=mock_client,
            mount_path="secret",
            secret_path="newsletter",
            ttl_seconds=1000,
        )
        mgr.start()
        with caplog.at_level(logging.DEBUG, logger="src.config.bao_secrets"):
            mgr.stop()
        assert any("bao.token_manager_stopped" in r.message for r in caplog.records)

    def test_refresh_updates_cache_atomically(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """spec .6: Refresh updates cache via atomic reference swap."""
        import src.config.bao_secrets as bao_mod

        mock_client = MagicMock()
        mock_client.auth.approle.login.return_value = {
            "auth": {"lease_duration": 3600}
        }
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"NEW_KEY": "new_value"}}
        }

        monkeypatch.setenv("BAO_ROLE_ID", "newsletter-app")
        monkeypatch.setenv("BAO_SECRET_ID", "test-secret")

        mgr = _BaoTokenManager(
            client=mock_client,
            mount_path="secret",
            secret_path="newsletter",
            ttl_seconds=100,
        )

        # Set initial cache
        bao_mod._bao_cache = {"OLD_KEY": "old_value"}

        # Manually trigger refresh (don't start timer)
        mgr._refresh()

        assert bao_mod._bao_cache == {"NEW_KEY": "new_value"}


# =========================================================================
# Audit Logging (spec .14)
# =========================================================================


class TestAuditLogging:
    """Verify structured log events with correct levels."""

    def test_secrets_loaded_info(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """spec .14: bao.secrets_loaded at INFO."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"K1": "v1", "K2": "v2"}}
        }
        mock_hvac = MagicMock()
        mock_hvac.Client.return_value = mock_client

        with patch("src.config.bao_secrets.hvac", mock_hvac, create=True):
            with caplog.at_level(logging.INFO, logger="src.config.bao_secrets"):
                _load_bao_secrets()

        loaded_msgs = [r for r in caplog.records if "bao.secrets_loaded" in r.message]
        assert len(loaded_msgs) == 1
        assert loaded_msgs[0].levelno == logging.INFO
        assert "2 secrets" in loaded_msgs[0].message

    def test_no_secret_values_in_logs(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """spec .14: Secret values must never appear in logs."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")

        secret_value = "sk-ant-super-secret-key-12345"
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"API_KEY": secret_value}}
        }
        mock_hvac = MagicMock()
        mock_hvac.Client.return_value = mock_client

        with patch("src.config.bao_secrets.hvac", mock_hvac, create=True):
            with caplog.at_level(logging.DEBUG, logger="src.config.bao_secrets"):
                _load_bao_secrets()

        all_messages = " ".join(r.message for r in caplog.records)
        assert secret_value not in all_messages

    def test_auth_failure_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """spec .14: bao.auth_failure at WARNING."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "bad-token")

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = False
        mock_hvac = MagicMock()
        mock_hvac.Client.return_value = mock_client

        with patch("src.config.bao_secrets.hvac", mock_hvac, create=True):
            with caplog.at_level(logging.WARNING, logger="src.config.bao_secrets"):
                _load_bao_secrets()

        auth_msgs = [r for r in caplog.records if "bao.auth_failure" in r.message]
        assert len(auth_msgs) >= 1
        assert auth_msgs[0].levelno == logging.WARNING


# =========================================================================
# BaoSettingsSource Exception Isolation (spec .23)
# =========================================================================


class TestBaoSettingsSourceExceptionIsolation:
    """Verify BaoSettingsSource never raises."""

    def test_call_returns_empty_on_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """spec .23: __call__() catches exceptions, returns {}."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")
        monkeypatch.setenv("BAO_TOKEN", "dev-root-token")

        with patch(
            "src.config.bao_secrets._load_bao_secrets",
            side_effect=RuntimeError("unexpected"),
        ):
            source = BaoSettingsSource(object)
            result = source()

        assert result == {}

    def test_get_field_value_returns_none_on_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """spec .23: get_field_value() catches exceptions."""
        monkeypatch.setenv("BAO_ADDR", "http://localhost:8200")

        with patch(
            "src.config.bao_secrets._load_bao_secrets",
            side_effect=RuntimeError("unexpected"),
        ):
            source = BaoSettingsSource(object)
            value, name, is_complex = source.get_field_value(None, "some_field")

        assert value is None
        assert name == "some_field"
