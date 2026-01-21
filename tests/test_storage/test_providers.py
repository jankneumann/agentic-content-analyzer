"""Tests for database provider abstraction."""

from unittest.mock import MagicMock

import pytest

from src.storage.providers import (
    LocalPostgresProvider,
    SupabaseProvider,
    get_provider,
)
from src.storage.providers.factory import detect_provider


class TestDetectProvider:
    """Tests for provider auto-detection logic."""

    def test_explicit_override_takes_precedence(self):
        """Explicit provider override should always be used."""
        result = detect_provider(
            database_url="postgresql://localhost/db",
            provider_override="supabase",
            supabase_project_ref=None,
        )
        assert result == "supabase"

    def test_supabase_project_ref_indicates_supabase(self):
        """SUPABASE_PROJECT_REF presence indicates Supabase provider."""
        result = detect_provider(
            database_url="postgresql://localhost/db",
            provider_override=None,
            supabase_project_ref="test-project-ref",
        )
        assert result == "supabase"

    def test_supabase_url_detected(self):
        """DATABASE_URL containing .supabase. indicates Supabase provider."""
        result = detect_provider(
            database_url="postgresql://postgres.abc@aws-0-us-east-1.pooler.supabase.com:6543/postgres",
            provider_override=None,
            supabase_project_ref=None,
        )
        assert result == "supabase"

    def test_default_is_local(self):
        """Default provider should be local PostgreSQL."""
        result = detect_provider(
            database_url="postgresql://user:pass@localhost:5432/db",
            provider_override=None,
            supabase_project_ref=None,
        )
        assert result == "local"

    def test_local_explicit_override(self):
        """Explicit local override should work even with Supabase URL."""
        result = detect_provider(
            database_url="postgresql://postgres@pooler.supabase.com/db",
            provider_override="local",
            supabase_project_ref=None,
        )
        assert result == "local"


class TestLocalPostgresProvider:
    """Tests for local PostgreSQL provider."""

    def test_name_is_local(self):
        """Provider name should be 'local'."""
        provider = LocalPostgresProvider("postgresql://localhost/db")
        assert provider.name == "local"

    def test_get_engine_url_returns_configured_url(self):
        """Should return the configured database URL."""
        url = "postgresql://user:pass@localhost:5432/newsletters"
        provider = LocalPostgresProvider(url)
        assert provider.get_engine_url() == url

    def test_get_engine_options_has_required_settings(self):
        """Should include essential pool settings."""
        provider = LocalPostgresProvider("postgresql://localhost/db")
        options = provider.get_engine_options()

        assert options["pool_pre_ping"] is True
        assert "pool_size" in options
        assert "max_overflow" in options
        assert options["echo"] is False

    def test_health_check_success(self):
        """Health check should return True on successful query."""
        provider = LocalPostgresProvider("postgresql://localhost/db")
        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_connection)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        result = provider.health_check(mock_engine)
        assert result is True

    def test_health_check_failure(self):
        """Health check should return False on connection error."""
        provider = LocalPostgresProvider("postgresql://localhost/db")
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("Connection refused")

        result = provider.health_check(mock_engine)
        assert result is False


class TestSupabaseProvider:
    """Tests for Supabase cloud provider."""

    def test_name_is_supabase(self):
        """Provider name should be 'supabase'."""
        provider = SupabaseProvider(database_url="postgresql://postgres@supabase.com/db")
        assert provider.name == "supabase"

    def test_get_engine_url_with_direct_url(self):
        """Should return direct URL when provided."""
        url = "postgresql://postgres@pooler.supabase.com:6543/postgres"
        provider = SupabaseProvider(database_url=url)
        assert provider.get_engine_url() == url

    def test_get_engine_url_from_components_transaction_mode(self):
        """Should construct correct pooler URL for transaction mode."""
        provider = SupabaseProvider(
            project_ref="test-ref",
            db_password="test-pass",
            region="us-east-1",
            pooler_mode="transaction",
        )
        url = provider.get_engine_url()

        assert "postgres.test-ref" in url
        assert "test-pass" in url
        assert "us-east-1" in url
        assert ":6543" in url  # Transaction mode port

    def test_get_engine_url_from_components_session_mode(self):
        """Should construct correct pooler URL for session mode."""
        provider = SupabaseProvider(
            project_ref="test-ref",
            db_password="test-pass",
            region="eu-west-1",
            pooler_mode="session",
        )
        url = provider.get_engine_url()

        assert "eu-west-1" in url
        assert ":5432" in url  # Session mode port

    def test_get_engine_url_missing_config_raises_error(self):
        """Should raise ValueError when required config is missing."""
        provider = SupabaseProvider(
            project_ref="test-ref",
            db_password=None,  # Missing password
        )
        with pytest.raises(ValueError, match="requires either database_url"):
            provider.get_engine_url()

    def test_get_engine_options_has_supabase_settings(self):
        """Should include Supabase-specific pool and SSL settings."""
        provider = SupabaseProvider(database_url="postgresql://postgres@supabase.com/db")
        options = provider.get_engine_options()

        assert options["pool_pre_ping"] is True
        assert options["pool_size"] == 5  # Conservative for free tier
        assert options["pool_recycle"] == 300  # 5 min recycle
        assert options["connect_args"]["sslmode"] == "require"
        assert "statement_timeout" in options["connect_args"]["options"]

    def test_get_direct_url_from_components(self):
        """Should construct direct URL bypassing pooler."""
        provider = SupabaseProvider(
            project_ref="test-ref",
            db_password="test-pass",
            region="us-east-1",
        )
        direct_url = provider.get_direct_url()

        assert direct_url is not None
        assert "db.test-ref.supabase.co" in direct_url
        assert ":5432" in direct_url
        assert "pooler" not in direct_url

    def test_get_direct_url_returns_none_without_components(self):
        """Should return None when component config is not available."""
        provider = SupabaseProvider(database_url="postgresql://postgres@supabase.com/db")
        assert provider.get_direct_url() is None


class TestGetProvider:
    """Tests for provider factory function."""

    def test_returns_local_provider_by_default(self):
        """Should return LocalPostgresProvider for standard URLs."""
        provider = get_provider(database_url="postgresql://user:pass@localhost:5432/db")
        assert isinstance(provider, LocalPostgresProvider)
        assert provider.name == "local"

    def test_returns_supabase_provider_from_url(self):
        """Should return SupabaseProvider when URL contains supabase domain."""
        provider = get_provider(database_url="postgresql://postgres@pooler.supabase.com:6543/db")
        assert isinstance(provider, SupabaseProvider)
        assert provider.name == "supabase"

    def test_returns_supabase_provider_from_components(self):
        """Should return SupabaseProvider when project_ref is provided."""
        provider = get_provider(
            database_url="postgresql://localhost/db",  # Ignored
            supabase_project_ref="test-ref",
            supabase_db_password="test-pass",
        )
        assert isinstance(provider, SupabaseProvider)

    def test_explicit_override_to_local(self):
        """Should return LocalPostgresProvider with explicit override."""
        provider = get_provider(
            database_url="postgresql://postgres@pooler.supabase.com/db",
            provider_override="local",
        )
        assert isinstance(provider, LocalPostgresProvider)

    def test_explicit_override_to_supabase_requires_config(self):
        """Should raise ValueError when Supabase override lacks config."""
        with pytest.raises(ValueError, match="Supabase provider requires"):
            get_provider(
                database_url="postgresql://localhost/db",
                provider_override="supabase",
            )

    def test_supabase_pooler_mode_propagates(self):
        """Should pass pooler_mode to SupabaseProvider."""
        provider = get_provider(
            database_url="postgresql://localhost/db",
            supabase_project_ref="test-ref",
            supabase_db_password="test-pass",
            supabase_pooler_mode="session",
        )
        assert isinstance(provider, SupabaseProvider)
        # Verify session mode port in URL
        assert ":5432" in provider.get_engine_url()


class TestProviderProtocol:
    """Tests to verify providers conform to DatabaseProvider protocol."""

    @pytest.fixture
    def local_provider(self):
        return LocalPostgresProvider("postgresql://localhost/db")

    @pytest.fixture
    def supabase_provider(self):
        return SupabaseProvider(
            project_ref="test-ref",
            db_password="test-pass",
        )

    def test_local_implements_protocol(self, local_provider):
        """LocalPostgresProvider should implement DatabaseProvider protocol."""
        assert hasattr(local_provider, "name")
        assert hasattr(local_provider, "get_engine_url")
        assert hasattr(local_provider, "get_engine_options")
        assert hasattr(local_provider, "health_check")

    def test_supabase_implements_protocol(self, supabase_provider):
        """SupabaseProvider should implement DatabaseProvider protocol."""
        assert hasattr(supabase_provider, "name")
        assert hasattr(supabase_provider, "get_engine_url")
        assert hasattr(supabase_provider, "get_engine_options")
        assert hasattr(supabase_provider, "health_check")
