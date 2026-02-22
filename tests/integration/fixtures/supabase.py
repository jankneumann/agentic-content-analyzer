"""Supabase integration test fixtures.

These fixtures provide Supabase database connections for integration testing.
Tests are automatically skipped if Supabase credentials are not configured.

Usage:
    def test_with_supabase(supabase_engine):
        with supabase_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

Requirements (via Settings / env vars):
    - SUPABASE_PROJECT_REF must be set
    - SUPABASE_DB_PASSWORD must be set
    - Optional: SUPABASE_REGION, SUPABASE_AZ, SUPABASE_POOLER_MODE

Note:
    These fixtures are skipped if Supabase credentials are not configured.
    This allows running other tests without Supabase access.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine

from src.config.settings import get_settings
from src.storage.providers.supabase import SupabaseProvider


def _supabase_is_configured() -> bool:
    """Check if Supabase credentials are configured via Settings."""
    settings = get_settings()
    return bool(settings.supabase_project_ref and settings.supabase_db_password)


# Check if Supabase is configured (evaluated at import time via Settings)
SUPABASE_CONFIGURED = _supabase_is_configured()

# Skip reason for when Supabase is not configured
SKIP_REASON = (
    "Supabase credentials not configured (SUPABASE_PROJECT_REF, SUPABASE_DB_PASSWORD required)"
)


@pytest.fixture(scope="session")
def supabase_provider() -> SupabaseProvider | None:
    """Create a SupabaseProvider configured from Settings.

    Returns None if Supabase is not configured, allowing tests to be skipped.

    Configuration is read from Settings (env vars):
    - SUPABASE_PROJECT_REF: Project reference ID
    - SUPABASE_DB_PASSWORD: Database password
    - SUPABASE_REGION: AWS region (default: us-east-1)
    - SUPABASE_AZ: Availability zone (default: 0)
    - SUPABASE_POOLER_MODE: transaction or session (default: transaction)
    """
    if not SUPABASE_CONFIGURED:
        return None

    settings = get_settings()
    return SupabaseProvider(
        project_ref=settings.supabase_project_ref,  # type: ignore[arg-type]
        db_password=settings.supabase_db_password,  # type: ignore[arg-type]
        region=settings.supabase_region,
        az=settings.supabase_az,
        pooler_mode=settings.supabase_pooler_mode,  # type: ignore[arg-type]
    )


@pytest.fixture(scope="session")
def supabase_engine(supabase_provider: SupabaseProvider | None) -> Iterator[Engine]:
    """Create a SQLAlchemy engine connected to Supabase.

    This fixture creates a pooled connection engine using the Supabase
    connection pooler (Supavisor). The engine is configured for optimal
    performance with Supabase's free tier.

    Yields:
        SQLAlchemy Engine connected to Supabase

    Skip:
        Skipped if SUPABASE_PROJECT_REF or SUPABASE_DB_PASSWORD are not set
    """
    if supabase_provider is None:
        pytest.skip(SKIP_REASON)

    engine = create_engine(
        supabase_provider.get_engine_url(),
        **supabase_provider.get_engine_options(),
    )

    yield engine

    engine.dispose()


@pytest.fixture(scope="session")
def supabase_direct_engine(supabase_provider: SupabaseProvider | None) -> Iterator[Engine]:
    """Create a SQLAlchemy engine with direct Supabase connection.

    This fixture creates a direct connection (bypassing Supavisor pooler)
    suitable for migrations and DDL operations.

    Yields:
        SQLAlchemy Engine with direct Supabase connection

    Skip:
        Skipped if Supabase credentials are not set
    """
    if supabase_provider is None:
        pytest.skip(SKIP_REASON)

    direct_url = supabase_provider.get_direct_url()
    if not direct_url:
        pytest.skip("Supabase direct URL not available")

    engine = create_engine(
        direct_url,
        pool_pre_ping=True,
        pool_size=2,  # Minimal pool for direct connection
        connect_args={
            "sslmode": "require",
            "connect_timeout": 30,
        },
    )

    yield engine

    engine.dispose()


@pytest.fixture(scope="session")
def supabase_available() -> bool:
    """Check if Supabase is available for testing.

    Use this fixture to conditionally skip tests:

        @pytest.mark.skipif(not supabase_available, reason="Supabase not configured")
        def test_something():
            ...
    """
    return SUPABASE_CONFIGURED


# Marker for tests that require Supabase
requires_supabase = pytest.mark.skipif(not SUPABASE_CONFIGURED, reason=SKIP_REASON)
