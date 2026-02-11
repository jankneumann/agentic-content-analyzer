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
                allowed_origins="http://localhost:5173,http://localhost:3000",
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
            allowed_origins="http://localhost:5173,http://localhost:3000",
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
        """Development mode with defaults should return localhost origins."""
        s = _make_settings(environment="development")
        assert s.get_allowed_origins_list() == [
            "http://localhost:5173",
            "http://localhost:3000",
        ]

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
