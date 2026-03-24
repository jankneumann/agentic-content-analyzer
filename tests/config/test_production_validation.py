"""Tests for production security validation in Settings."""

from __future__ import annotations

import logging

from src.config.settings import Settings


class TestWeakSecretDetection:
    """Tests for weak secret detection in production validation."""

    def test_weak_app_secret_key_triggers_warning(self, caplog):
        """Weak APP_SECRET_KEY should trigger a warning in production."""
        with caplog.at_level(logging.WARNING):
            Settings(
                _env_file=None,
                environment="production",
                anthropic_api_key="test-key",
                app_secret_key="changeme",
                admin_api_key="a-long-enough-key-that-is-at-least-32-chars-ok",
                database_url="postgresql://user:strongpass@host/db",
            )
        assert "APP_SECRET_KEY matches a common default value" in caplog.text

    def test_weak_admin_api_key_triggers_warning(self, caplog):
        """Weak ADMIN_API_KEY should trigger a warning in production."""
        with caplog.at_level(logging.WARNING):
            Settings(
                _env_file=None,
                environment="production",
                anthropic_api_key="test-key",
                app_secret_key="a-strong-random-secret-key-that-is-long-enough",
                admin_api_key="password",
                database_url="postgresql://user:strongpass@host/db",
            )
        assert "ADMIN_API_KEY matches a common default value" in caplog.text

    def test_short_admin_api_key_triggers_warning(self, caplog):
        """Short ADMIN_API_KEY should trigger a warning in production."""
        with caplog.at_level(logging.WARNING):
            Settings(
                _env_file=None,
                environment="production",
                anthropic_api_key="test-key",
                app_secret_key="a-strong-random-secret-key-that-is-long-enough",
                admin_api_key="short-key-under-32",
                database_url="postgresql://user:strongpass@host/db",
            )
        assert "ADMIN_API_KEY is shorter than 32 characters" in caplog.text


class TestDefaultDatabasePasswordDetection:
    """Tests for default database password detection in production."""

    def test_default_db_password_triggers_warning(self, caplog):
        """DATABASE_URL with 'newsletter_password' should trigger a warning."""
        with caplog.at_level(logging.WARNING):
            Settings(
                _env_file=None,
                environment="production",
                anthropic_api_key="test-key",
                app_secret_key="a-strong-random-secret-key-that-is-long-enough",
                admin_api_key="a-long-enough-key-that-is-at-least-32-chars-ok",
                database_url="postgresql://user:newsletter_password@localhost/newsletters",
            )
        assert "DATABASE_URL contains the default development password" in caplog.text


class TestStrongSecretsPassValidation:
    """Tests that strong secrets do not trigger weak-secret warnings."""

    def test_strong_secrets_no_weak_warnings(self, caplog):
        """Strong secrets should not produce weak-secret warnings."""
        with caplog.at_level(logging.WARNING):
            Settings(
                _env_file=None,
                environment="production",
                anthropic_api_key="test-key",
                app_secret_key="xK9mP2qR7vB4nL8wF5jH3cT6yA0dE1gP9rZ2wQ5tV8xN3bM",
                admin_api_key="zW8kN3pQ6uC9mJ2xR5vB4hF7tL0yA1dEa7cK4pN9wR2mX6bJ",
                database_url="postgresql://user:str0ng_r4ndom_p@ss@host/db",
                allowed_origins="https://example.com",
            )

        # Should NOT contain any weak-secret warnings
        assert "matches a common default value" not in caplog.text
        assert "shorter than 32 characters" not in caplog.text
        assert "default development password" not in caplog.text

    def test_no_warnings_in_development(self, caplog):
        """Development environment should not trigger production validation warnings."""
        with caplog.at_level(logging.WARNING):
            Settings(
                _env_file=None,
                environment="development",
                anthropic_api_key="test-key",
                app_secret_key="changeme",
                admin_api_key="test",
                database_url="postgresql://user:newsletter_password@localhost/newsletters",
            )

        # Production-specific warnings should not appear in development
        assert "matches a common default value" not in caplog.text
        assert "shorter than 32 characters" not in caplog.text
        assert "default development password" not in caplog.text
