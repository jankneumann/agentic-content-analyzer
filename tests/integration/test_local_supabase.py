"""Integration tests for local Supabase development support.

These tests verify:
- Local Supabase database connectivity
- Local Supabase storage connectivity
- Settings auto-configuration for local mode

Tests are automatically skipped if local Supabase is not running.

To run these tests:
    1. Start local Supabase: make supabase-up
    2. Run tests: pytest tests/integration/test_local_supabase.py -v

Requirements:
    - Local Supabase stack running (docker-compose.supabase.yml)
    - Ports 54321 (API), 54322 (DB) available
"""

import os

import pytest
from sqlalchemy import text

# Check if local Supabase appears to be running
LOCAL_SUPABASE_AVAILABLE = False
try:
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("127.0.0.1", 54322))
    LOCAL_SUPABASE_AVAILABLE = result == 0
    sock.close()
except Exception:
    pass

SKIP_REASON = "Local Supabase not running. Start with: make supabase-up"

# Marker for tests that require local Supabase
requires_local_supabase = pytest.mark.skipif(not LOCAL_SUPABASE_AVAILABLE, reason=SKIP_REASON)


@pytest.fixture
def local_supabase_env():
    """Set up environment for local Supabase testing."""
    original_env = {
        "SUPABASE_LOCAL": os.environ.get("SUPABASE_LOCAL"),
        "DATABASE_PROVIDER": os.environ.get("DATABASE_PROVIDER"),
        "SUPABASE_PROJECT_REF": os.environ.get("SUPABASE_PROJECT_REF"),
        "SUPABASE_DB_PASSWORD": os.environ.get("SUPABASE_DB_PASSWORD"),
    }

    os.environ["SUPABASE_LOCAL"] = "true"
    os.environ["DATABASE_PROVIDER"] = "supabase"
    os.environ.pop("SUPABASE_PROJECT_REF", None)
    os.environ.pop("SUPABASE_DB_PASSWORD", None)

    # Clear settings cache
    from src.config.settings import get_settings

    get_settings.cache_clear()

    yield

    # Restore original environment
    for key, value in original_env.items():
        if value is not None:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)

    get_settings.cache_clear()


@requires_local_supabase
class TestLocalSupabaseDatabase:
    """Test local Supabase database connectivity."""

    def test_local_database_connection(self, local_supabase_env):
        """Verify connection to local Supabase PostgreSQL."""
        from sqlalchemy import create_engine

        from src.storage.providers.supabase import SupabaseProvider

        provider = SupabaseProvider(local=True)
        engine = create_engine(
            provider.get_engine_url(),
            **provider.get_engine_options(),
        )

        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1 as value"))
                assert result.scalar() == 1
        finally:
            engine.dispose()

    def test_local_provider_is_local_property(self, local_supabase_env):
        """Verify provider identifies as local."""
        from src.storage.providers.supabase import SupabaseProvider

        provider = SupabaseProvider(local=True)
        assert provider.is_local is True
        assert provider.name == "supabase"

    def test_local_provider_engine_url(self, local_supabase_env):
        """Verify local provider returns correct URL."""
        from src.storage.providers.supabase import SupabaseProvider

        provider = SupabaseProvider(local=True)
        url = provider.get_engine_url()

        assert "127.0.0.1:54322" in url
        assert "postgres:postgres" in url

    def test_local_provider_direct_url(self, local_supabase_env):
        """Verify local provider returns correct direct URL."""
        from src.storage.providers.supabase import SupabaseProvider

        provider = SupabaseProvider(local=True)
        url = provider.get_direct_url()

        assert url is not None
        assert "127.0.0.1:54322" in url

    def test_local_provider_no_ssl(self, local_supabase_env):
        """Verify local provider doesn't require SSL."""
        from src.storage.providers.supabase import SupabaseProvider

        provider = SupabaseProvider(local=True)
        options = provider.get_engine_options()

        # Local mode should not have sslmode in connect_args
        connect_args = options.get("connect_args", {})
        assert "sslmode" not in connect_args

    def test_local_database_ddl_operations(self, local_supabase_env):
        """Verify DDL operations work on local database."""
        from sqlalchemy import create_engine

        from src.storage.providers.supabase import SupabaseProvider

        provider = SupabaseProvider(local=True)
        engine = create_engine(
            provider.get_engine_url(),
            **provider.get_engine_options(),
        )

        try:
            with engine.connect() as conn:
                # Create test table
                conn.execute(
                    text(
                        """
                    CREATE TABLE IF NOT EXISTS _test_local_supabase (
                        id SERIAL PRIMARY KEY,
                        value TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """
                    )
                )
                conn.commit()

                # Insert test data
                conn.execute(text("INSERT INTO _test_local_supabase (value) VALUES ('test')"))
                conn.commit()

                # Verify insert
                result = conn.execute(
                    text("SELECT value FROM _test_local_supabase WHERE value = 'test'")
                )
                assert result.scalar() == "test"

                # Clean up
                conn.execute(text("DROP TABLE IF EXISTS _test_local_supabase"))
                conn.commit()
        finally:
            engine.dispose()

    def test_local_health_check(self, local_supabase_env):
        """Verify health check passes on local database."""
        from sqlalchemy import create_engine

        from src.storage.providers.supabase import SupabaseProvider

        provider = SupabaseProvider(local=True)
        engine = create_engine(
            provider.get_engine_url(),
            **provider.get_engine_options(),
        )

        try:
            assert provider.health_check(engine) is True
        finally:
            engine.dispose()


@requires_local_supabase
class TestLocalSupabaseSettings:
    """Test settings integration with local Supabase."""

    def test_settings_auto_configures_for_local(self, local_supabase_env):
        """Verify settings auto-configure when SUPABASE_LOCAL=true."""
        from src.config.settings import Settings

        settings = Settings(_env_file=None)

        assert settings.supabase_local is True
        assert settings.is_local_supabase is True
        assert settings.supabase_url == "http://127.0.0.1:54321"
        assert "127.0.0.1:54322" in settings.get_effective_database_url()

    def test_settings_migration_url_for_local(self, local_supabase_env):
        """Verify migration URL is correct for local mode."""
        from src.config.settings import Settings

        settings = Settings(_env_file=None)

        migration_url = settings.get_migration_database_url()
        assert "127.0.0.1:54322" in migration_url

    def test_settings_storage_endpoint_for_local(self, local_supabase_env):
        """Verify storage endpoint is correct for local mode."""
        from src.config.settings import Settings

        settings = Settings(_env_file=None)

        endpoint = settings.get_supabase_storage_endpoint()
        assert endpoint == "http://127.0.0.1:54321/storage/v1/s3"


@requires_local_supabase
class TestLocalSupabaseStorage:
    """Test local Supabase storage connectivity.

    Note: These tests require the local Supabase storage service to be running
    and properly configured. Storage tests may need bucket creation first.
    """

    def test_storage_provider_initializes_for_local(self, local_supabase_env):
        """Verify storage provider initializes in local mode."""
        from src.services.file_storage import SupabaseFileStorage

        # Should not raise even without cloud credentials
        storage = SupabaseFileStorage(local=True, bucket="test-bucket")

        assert storage.provider_name == "supabase"
        assert storage._is_local is True

    def test_storage_url_format_for_local(self, local_supabase_env):
        """Verify storage URLs use local endpoint."""
        from src.services.file_storage import SupabaseFileStorage

        storage = SupabaseFileStorage(local=True, bucket="test-bucket")

        url = storage.get_url("test/path.png")
        assert "127.0.0.1:54321" in url
        assert "storage/v1/object" in url
