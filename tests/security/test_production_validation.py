"""Tests for production startup validation and environment-aware CORS defaults.

Validates that:
- Production mode logs warnings for insecure configuration
- Production mode with dev-default CORS origins returns empty origins list
- Development mode retains permissive localhost defaults
- Explicit ALLOWED_ORIGINS in production returns configured list
"""

import logging

from src.config.settings import Settings


def _make_settings(**overrides) -> Settings:
    """Create a Settings instance with test defaults.

    Passes _env_file=None to avoid picking up .env values,
    and provides required fields with test defaults.
    """
    defaults = {
        "anthropic_api_key": "test-key",
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


class TestProductionSecurityWarnings:
    """Test that production mode logs appropriate security warnings."""

    def test_production_missing_admin_key_logs_warning(self, caplog):
        """Production with no ADMIN_API_KEY should log a warning."""
        with caplog.at_level(logging.WARNING, logger="src.config.settings"):
            _make_settings(environment="production", admin_api_key=None)

        assert any("ADMIN_API_KEY is not set" in msg for msg in caplog.messages)

    def test_production_with_admin_key_no_warning(self, caplog):
        """Production with ADMIN_API_KEY set should NOT log admin key warning."""
        with caplog.at_level(logging.WARNING, logger="src.config.settings"):
            _make_settings(
                environment="production",
                admin_api_key="my-secret-key",
                allowed_origins="https://myapp.com",
            )

        assert not any("ADMIN_API_KEY is not set" in msg for msg in caplog.messages)

    def test_production_dev_default_cors_logs_warning(self, caplog):
        """Production with dev-default CORS origins should log a warning."""
        with caplog.at_level(logging.WARNING, logger="src.config.settings"):
            _make_settings(
                environment="production",
                admin_api_key="my-key",
                allowed_origins="http://localhost:5173,http://localhost:3000,capacitor://localhost,http://localhost,tauri://localhost",
            )

        assert any(
            "ALLOWED_ORIGINS is using development defaults" in msg for msg in caplog.messages
        )

    def test_production_explicit_origins_no_cors_warning(self, caplog):
        """Production with explicit origins should NOT log CORS warning."""
        with caplog.at_level(logging.WARNING, logger="src.config.settings"):
            _make_settings(
                environment="production",
                admin_api_key="my-key",
                allowed_origins="https://myapp.com",
            )

        assert not any(
            "ALLOWED_ORIGINS is using development defaults" in msg for msg in caplog.messages
        )

    def test_development_no_warnings(self, caplog):
        """Development mode should NOT log production security warnings."""
        with caplog.at_level(logging.WARNING, logger="src.config.settings"):
            _make_settings(environment="development", admin_api_key=None)

        assert not any("ADMIN_API_KEY is not set" in msg for msg in caplog.messages)
        assert not any(
            "ALLOWED_ORIGINS is using development defaults" in msg for msg in caplog.messages
        )


class TestCORSDefaults:
    """Test environment-aware CORS origin behavior."""

    def test_production_dev_defaults_returns_empty_list(self):
        """Production with dev-default origins should deny all cross-origin."""
        s = _make_settings(
            environment="production",
            admin_api_key="key",
            allowed_origins="http://localhost:5173,http://localhost:3000,capacitor://localhost,http://localhost,tauri://localhost",
        )
        assert s.get_allowed_origins_list() == []

    def test_production_explicit_origins_returns_configured(self):
        """Production with explicit origins should return the configured list."""
        s = _make_settings(
            environment="production",
            admin_api_key="key",
            allowed_origins="https://myapp.com,https://admin.myapp.com",
        )
        assert s.get_allowed_origins_list() == ["https://myapp.com", "https://admin.myapp.com"]

    def test_production_wildcard_returns_wildcard(self):
        """Production with wildcard should return ['*']."""
        s = _make_settings(
            environment="production",
            admin_api_key="key",
            allowed_origins="*",
        )
        assert s.get_allowed_origins_list() == ["*"]

    def test_development_dev_defaults_returns_localhost(self):
        """Development mode with defaults should return all dev origins including Capacitor."""
        s = _make_settings(environment="development")
        origins = s.get_allowed_origins_list()
        assert "http://localhost:5173" in origins
        assert "http://localhost:3000" in origins
        assert "capacitor://localhost" in origins
        assert "http://localhost" in origins

    def test_development_explicit_origins_returns_configured(self):
        """Development with explicit origins should return configured list."""
        s = _make_settings(
            environment="development",
            allowed_origins="http://localhost:8080",
        )
        assert s.get_allowed_origins_list() == ["http://localhost:8080"]

    def test_production_without_explicit_origins_returns_empty(self):
        """Production with no change to default origins returns empty."""
        s = _make_settings(
            environment="production",
            admin_api_key="key",
            # allowed_origins defaults to dev defaults
        )
        assert s.get_allowed_origins_list() == []

    def test_production_dev_defaults_with_spaces_returns_empty(self):
        """Dev defaults with extra spaces should still be detected."""
        s = _make_settings(
            environment="production",
            admin_api_key="key",
            allowed_origins="http://localhost:5173, http://localhost:3000, capacitor://localhost, http://localhost, tauri://localhost",
        )
        assert s.get_allowed_origins_list() == []

    def test_production_dev_defaults_reversed_returns_empty(self):
        """Dev defaults in reversed order should still be detected."""
        s = _make_settings(
            environment="production",
            admin_api_key="key",
            allowed_origins="http://localhost:3000,http://localhost:5173,http://localhost,capacitor://localhost,tauri://localhost",
        )
        assert s.get_allowed_origins_list() == []

    def test_production_single_localhost_not_dev_default(self):
        """Single localhost origin is not the dev default set — should pass through."""
        s = _make_settings(
            environment="production",
            admin_api_key="key",
            allowed_origins="http://localhost:5173",
        )
        assert s.get_allowed_origins_list() == ["http://localhost:5173"]


class TestCapacitorCORSOrigins:
    """Test that Capacitor native origins are included in CORS defaults."""

    def test_capacitor_ios_origin_in_defaults(self):
        """capacitor://localhost (iOS WKWebView) should be in dev defaults."""
        s = _make_settings(environment="development")
        origins = s.get_allowed_origins_list()
        assert "capacitor://localhost" in origins

    def test_capacitor_android_origin_in_defaults(self):
        """http://localhost (Android WebView) should be in dev defaults."""
        s = _make_settings(environment="development")
        origins = s.get_allowed_origins_list()
        assert "http://localhost" in origins

    def test_capacitor_origins_in_dev_default_set(self):
        """Both Capacitor origins should be in _DEV_DEFAULT_ORIGINS ClassVar."""
        from src.config.settings import Settings

        assert "capacitor://localhost" in Settings._DEV_DEFAULT_ORIGINS
        assert "http://localhost" in Settings._DEV_DEFAULT_ORIGINS

    def test_production_with_capacitor_origins_still_blocked(self):
        """Production with only dev defaults (including Capacitor) returns empty."""
        s = _make_settings(
            environment="production",
            admin_api_key="key",
            # Uses default allowed_origins which includes Capacitor origins
        )
        assert s.get_allowed_origins_list() == []

    def test_production_explicit_capacitor_origin_passes_through(self):
        """Production with explicitly set capacitor origin should pass through."""
        s = _make_settings(
            environment="production",
            admin_api_key="key",
            allowed_origins="https://myapp.com,capacitor://localhost",
        )
        origins = s.get_allowed_origins_list()
        assert "https://myapp.com" in origins
        assert "capacitor://localhost" in origins
