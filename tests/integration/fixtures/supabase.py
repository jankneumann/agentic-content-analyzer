"""Supabase integration test fixtures.

These fixtures provide Supabase database connections for integration testing.
Tests are automatically skipped if Supabase credentials are not configured.

Usage:
    def test_with_supabase(supabase_engine):
        with supabase_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

Requirements:
    - SUPABASE_PROJECT_REF environment variable must be set
    - SUPABASE_DB_PASSWORD environment variable must be set
    - Optional: SUPABASE_REGION, SUPABASE_AZ, SUPABASE_POOLER_MODE

Note:
    These fixtures are skipped if Supabase credentials are not configured.
    This allows running other tests without Supabase access.
"""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine

# Load environment variables from .env file for tests
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv not installed, rely on environment variables

from src.storage.providers.supabase import SupabaseProvider

# Check if Supabase is configured (after loading .env)
SUPABASE_CONFIGURED = bool(
    os.environ.get("SUPABASE_PROJECT_REF") and os.environ.get("SUPABASE_DB_PASSWORD")
)

# Skip reason for when Supabase is not configured
SKIP_REASON = (
    "Supabase credentials not configured (SUPABASE_PROJECT_REF, SUPABASE_DB_PASSWORD required)"
)


@pytest.fixture(scope="session")
def supabase_provider() -> SupabaseProvider | None:
    """Create a SupabaseProvider configured from environment.

    Returns None if Supabase is not configured, allowing tests to be skipped.

    The provider uses environment variables:
    - SUPABASE_PROJECT_REF: Project reference ID
    - SUPABASE_DB_PASSWORD: Database password
    - SUPABASE_REGION: AWS region (default: us-east-1)
    - SUPABASE_AZ: Availability zone (default: 0)
    - SUPABASE_POOLER_MODE: transaction or session (default: transaction)
    """
    if not SUPABASE_CONFIGURED:
        return None

    return SupabaseProvider(
        project_ref=os.environ["SUPABASE_PROJECT_REF"],
        db_password=os.environ["SUPABASE_DB_PASSWORD"],
        region=os.environ.get("SUPABASE_REGION", "us-east-1"),
        az=os.environ.get("SUPABASE_AZ", "0"),
        pooler_mode=os.environ.get("SUPABASE_POOLER_MODE", "transaction"),  # type: ignore
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
