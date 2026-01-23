"""Tests for settings configuration and validation."""

import os
import warnings

import pytest
from pydantic import ValidationError


class TestDatabaseProviderValidation:
    """Tests for DATABASE_PROVIDER validation in Settings."""

    @pytest.fixture(autouse=True)
    def clear_env(self):
        """Clear relevant env vars and caches before each test."""
        # Clear the settings cache to ensure fresh Settings instance
        from src.config.settings import get_settings

        get_settings.cache_clear()

        env_vars = [
            "DATABASE_PROVIDER",
            "DATABASE_URL",
            "SUPABASE_PROJECT_REF",
            "SUPABASE_DB_PASSWORD",
            "SUPABASE_DIRECT_URL",
            "NEON_PROJECT_ID",
            "NEON_API_KEY",
            "NEON_DIRECT_URL",
        ]
        original = {k: os.environ.get(k) for k in env_vars}
        for k in env_vars:
            os.environ.pop(k, None)

        # Set required env vars
        os.environ["ANTHROPIC_API_KEY"] = "test-key"

        yield

        # Restore original env
        for k, v in original.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

        # Clear cache again after test
        get_settings.cache_clear()

    def test_local_provider_with_local_url_passes(self):
        """Local provider with localhost URL should pass validation."""
        os.environ["DATABASE_PROVIDER"] = "local"
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"

        # Import fresh to trigger validation
        from src.config.settings import Settings

        settings = Settings()
        assert settings.database_provider == "local"

    def test_neon_provider_with_neon_url_passes(self):
        """Neon provider with Neon URL should pass validation."""
        os.environ["DATABASE_PROVIDER"] = "neon"
        os.environ["DATABASE_URL"] = "postgresql://user:pass@ep-test.us-east-1.aws.neon.tech/db"

        from src.config.settings import Settings

        settings = Settings()
        assert settings.database_provider == "neon"

    def test_neon_provider_with_non_neon_url_fails(self):
        """Neon provider with non-Neon URL should fail validation."""
        os.environ["DATABASE_PROVIDER"] = "neon"
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"

        from src.config.settings import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "DATABASE_PROVIDER=neon requires DATABASE_URL containing .neon.tech" in str(
            exc_info.value
        )

    def test_supabase_provider_with_project_ref_passes(self):
        """Supabase provider with project ref should pass validation."""
        os.environ["DATABASE_PROVIDER"] = "supabase"
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
        os.environ["SUPABASE_PROJECT_REF"] = "test-project"

        from src.config.settings import Settings

        settings = Settings()
        assert settings.database_provider == "supabase"

    def test_supabase_provider_with_supabase_url_passes(self):
        """Supabase provider with Supabase URL should pass validation."""
        os.environ["DATABASE_PROVIDER"] = "supabase"
        os.environ["DATABASE_URL"] = "postgresql://user:pass@db.test.supabase.co:5432/postgres"

        from src.config.settings import Settings

        settings = Settings()
        assert settings.database_provider == "supabase"

    def test_supabase_provider_without_config_fails(self):
        """Supabase provider without Supabase config should fail validation."""
        os.environ["DATABASE_PROVIDER"] = "supabase"
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"

        from src.config.settings import Settings

        # Explicitly disable .env file loading to isolate the test
        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None)

        assert "DATABASE_PROVIDER=supabase requires" in str(exc_info.value)

    def test_local_provider_with_neon_url_warns(self, caplog):
        """Local provider with Neon URL should log a warning."""
        import logging

        os.environ["DATABASE_PROVIDER"] = "local"
        os.environ["DATABASE_URL"] = "postgresql://user:pass@ep-test.us-east-1.aws.neon.tech/db"

        from src.config.settings import Settings

        with caplog.at_level(logging.WARNING):
            settings = Settings()

        assert settings.database_provider == "local"
        assert "DATABASE_URL contains .neon.tech but DATABASE_PROVIDER=local" in caplog.text

    def test_local_provider_with_supabase_url_warns(self, caplog):
        """Local provider with Supabase URL should log a warning."""
        import logging

        os.environ["DATABASE_PROVIDER"] = "local"
        os.environ["DATABASE_URL"] = "postgresql://user:pass@db.test.supabase.co:5432/postgres"

        from src.config.settings import Settings

        with caplog.at_level(logging.WARNING):
            settings = Settings()

        assert settings.database_provider == "local"
        assert "DATABASE_URL contains .supabase. but DATABASE_PROVIDER=local" in caplog.text

    def test_password_masked_in_error_message(self):
        """Password should be masked in validation error messages."""
        os.environ["DATABASE_PROVIDER"] = "neon"
        os.environ["DATABASE_URL"] = "postgresql://user:secret_password@localhost/db"

        from src.config.settings import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        error_str = str(exc_info.value)
        assert "secret_password" not in error_str
        assert "***" in error_str


class TestDatabaseUrlMethods:
    """Tests for get_effective_database_url and get_migration_database_url."""

    @pytest.fixture(autouse=True)
    def setup_env(self):
        """Set up required env vars and clear caches."""
        from src.config.settings import get_settings

        get_settings.cache_clear()

        # Clear relevant env vars
        for key in [
            "DATABASE_PROVIDER",
            "DATABASE_URL",
            "SUPABASE_PROJECT_REF",
            "SUPABASE_DB_PASSWORD",
            "NEON_DIRECT_URL",
        ]:
            os.environ.pop(key, None)

        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        yield
        get_settings.cache_clear()

    def test_local_provider_returns_database_url(self):
        """Local provider should return DATABASE_URL directly."""
        os.environ["DATABASE_PROVIDER"] = "local"
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"

        from src.config.settings import Settings

        settings = Settings()
        assert settings.get_effective_database_url() == "postgresql://user:pass@localhost/db"
        assert settings.get_migration_database_url() == "postgresql://user:pass@localhost/db"

    def test_neon_provider_migration_url_removes_pooler(self):
        """Neon provider should remove -pooler from migration URL."""
        os.environ["DATABASE_PROVIDER"] = "neon"
        os.environ["DATABASE_URL"] = (
            "postgresql://user:pass@ep-test-pooler.us-east-1.aws.neon.tech/db"
        )

        from src.config.settings import Settings

        settings = Settings()

        # Effective URL keeps pooler
        assert "-pooler" in settings.get_effective_database_url()

        # Migration URL removes pooler
        migration_url = settings.get_migration_database_url()
        assert "-pooler" not in migration_url
        assert "ep-test.us-east-1.aws.neon.tech" in migration_url

    def test_neon_direct_url_override(self):
        """NEON_DIRECT_URL should override automatic conversion."""
        os.environ["DATABASE_PROVIDER"] = "neon"
        os.environ["DATABASE_URL"] = (
            "postgresql://user:pass@ep-test-pooler.us-east-1.aws.neon.tech/db"
        )
        os.environ["NEON_DIRECT_URL"] = "postgresql://user:pass@custom-direct/db"

        from src.config.settings import Settings

        settings = Settings()

        assert settings.get_migration_database_url() == "postgresql://user:pass@custom-direct/db"

    def test_supabase_provider_with_components_builds_urls(self):
        """Supabase provider should build URLs from components."""
        os.environ["DATABASE_PROVIDER"] = "supabase"
        os.environ["DATABASE_URL"] = "postgresql://ignored/db"
        os.environ["SUPABASE_PROJECT_REF"] = "test-project"
        os.environ["SUPABASE_DB_PASSWORD"] = "test-pass"

        from src.config.settings import Settings

        settings = Settings()

        # Effective URL is pooler URL
        effective = settings.get_effective_database_url()
        assert "pooler.supabase.com" in effective
        assert "test-project" in effective

        # Migration URL is direct URL
        migration = settings.get_migration_database_url()
        assert "db.test-project.supabase.co" in migration


class TestDeprecatedDetectedDatabaseProvider:
    """Tests for deprecated detected_database_provider property."""

    @pytest.fixture(autouse=True)
    def setup_env(self):
        """Set up required env vars and clear caches."""
        from src.config.settings import get_settings

        get_settings.cache_clear()

        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        os.environ["DATABASE_PROVIDER"] = "local"
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
        yield
        get_settings.cache_clear()

    def test_detected_database_provider_emits_warning(self):
        """detected_database_provider should emit DeprecationWarning."""
        from src.config.settings import Settings

        settings = Settings()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = settings.detected_database_provider

            assert result == "local"
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
