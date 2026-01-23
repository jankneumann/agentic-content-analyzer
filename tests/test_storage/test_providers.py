"""Tests for database provider abstraction."""

from unittest.mock import MagicMock

import pytest

from src.storage.providers import (
    LocalPostgresProvider,
    NeonProvider,
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

    def test_neon_project_id_indicates_neon(self):
        """NEON_PROJECT_ID presence indicates Neon provider."""
        result = detect_provider(
            database_url="postgresql://localhost/db",
            provider_override=None,
            supabase_project_ref=None,
            neon_project_id="test-neon-project",
        )
        assert result == "neon"

    def test_neon_url_detected(self):
        """DATABASE_URL containing .neon.tech indicates Neon provider."""
        result = detect_provider(
            database_url="postgresql://user:pass@ep-cool-darkness-123456.us-east-2.aws.neon.tech/dbname",
            provider_override=None,
            supabase_project_ref=None,
        )
        assert result == "neon"

    def test_neon_explicit_override(self):
        """Explicit neon override works."""
        result = detect_provider(
            database_url="postgresql://localhost/db",
            provider_override="neon",
            supabase_project_ref=None,
        )
        assert result == "neon"


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


class TestNeonProvider:
    """Tests for Neon cloud provider."""

    def test_name_is_neon(self):
        """Provider name should be 'neon'."""
        provider = NeonProvider(
            database_url="postgresql://user:pass@ep-cool-darkness-123456.us-east-2.aws.neon.tech/dbname"
        )
        assert provider.name == "neon"

    def test_get_engine_url_returns_pooled_url(self):
        """Should convert direct URL to pooled URL."""
        direct_url = "postgresql://user:pass@ep-cool-darkness-123456.us-east-2.aws.neon.tech/dbname"
        provider = NeonProvider(database_url=direct_url)
        engine_url = provider.get_engine_url()

        assert "-pooler." in engine_url
        assert "ep-cool-darkness-123456-pooler.us-east-2.aws.neon.tech" in engine_url

    def test_get_engine_url_keeps_pooled_url(self):
        """Should keep already pooled URL as-is."""
        pooled_url = (
            "postgresql://user:pass@ep-cool-darkness-123456-pooler.us-east-2.aws.neon.tech/dbname"
        )
        provider = NeonProvider(database_url=pooled_url)
        engine_url = provider.get_engine_url()

        assert engine_url == pooled_url

    def test_get_engine_url_missing_url_raises_error(self):
        """Should raise ValueError when no URL is provided."""
        provider = NeonProvider(project_id="test-project")
        with pytest.raises(ValueError, match="Neon provider requires database_url"):
            provider.get_engine_url()

    def test_get_direct_url_removes_pooler(self):
        """Should remove -pooler from URL."""
        pooled_url = (
            "postgresql://user:pass@ep-cool-darkness-123456-pooler.us-east-2.aws.neon.tech/dbname"
        )
        provider = NeonProvider(database_url=pooled_url)
        direct_url = provider.get_direct_url()

        assert "-pooler." not in direct_url
        assert "ep-cool-darkness-123456.us-east-2.aws.neon.tech" in direct_url

    def test_get_direct_url_keeps_direct_url(self):
        """Should keep direct URL as-is."""
        direct_url = "postgresql://user:pass@ep-cool-darkness-123456.us-east-2.aws.neon.tech/dbname"
        provider = NeonProvider(database_url=direct_url)
        result = provider.get_direct_url()

        assert result == direct_url
        assert "-pooler." not in result

    def test_get_engine_options_has_neon_settings(self):
        """Should include Neon-specific pool and SSL settings."""
        provider = NeonProvider(
            database_url="postgresql://user:pass@ep-cool-darkness-123456.us-east-2.aws.neon.tech/dbname"
        )
        options = provider.get_engine_options()

        assert options["pool_pre_ping"] is True
        assert options["pool_size"] == 5  # Conservative for Neon
        assert options["pool_recycle"] == 300  # 5 min recycle
        assert options["connect_args"]["sslmode"] == "require"
        assert "statement_timeout" in options["connect_args"]["options"]

    def test_health_check_success(self):
        """Health check returns True on success."""
        provider = NeonProvider(
            database_url="postgresql://user:pass@ep-cool-darkness-123456.us-east-2.aws.neon.tech/dbname"
        )
        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_connection)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        result = provider.health_check(mock_engine)
        assert result is True

    def test_health_check_failure(self):
        """Health check returns False on failure."""
        provider = NeonProvider(
            database_url="postgresql://user:pass@ep-cool-darkness-123456.us-east-2.aws.neon.tech/dbname"
        )
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("Connection refused")

        result = provider.health_check(mock_engine)
        assert result is False


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

    def test_returns_neon_provider_from_url(self):
        """Should return NeonProvider when URL contains .neon.tech."""
        provider = get_provider(
            database_url="postgresql://user:pass@ep-cool-darkness-123456.us-east-2.aws.neon.tech/dbname"
        )
        assert isinstance(provider, NeonProvider)
        assert provider.name == "neon"

    def test_explicit_override_to_neon(self):
        """Should return NeonProvider with explicit override."""
        provider = get_provider(
            database_url="postgresql://user:pass@localhost:5432/db",
            provider_override="neon",
        )
        assert isinstance(provider, NeonProvider)

    def test_neon_project_id_config_works(self):
        """Should pass neon_project_id to provider."""
        provider = get_provider(
            database_url="postgresql://user:pass@ep-cool-darkness-123456.us-east-2.aws.neon.tech/dbname",
            neon_project_id="my-neon-project",
        )
        assert isinstance(provider, NeonProvider)
        assert provider._project_id == "my-neon-project"


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

    @pytest.fixture
    def neon_provider(self):
        return NeonProvider(
            database_url="postgresql://user:pass@ep-cool-darkness-123456.us-east-2.aws.neon.tech/dbname"
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

    def test_neon_implements_protocol(self, neon_provider):
        """NeonProvider should implement DatabaseProvider protocol."""
        assert hasattr(neon_provider, "name")
        assert hasattr(neon_provider, "get_engine_url")
        assert hasattr(neon_provider, "get_engine_options")
        assert hasattr(neon_provider, "health_check")
