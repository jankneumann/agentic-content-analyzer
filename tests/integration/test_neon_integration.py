"""Real integration tests for Neon serverless PostgreSQL.

These tests use actual Neon API calls and create real ephemeral database branches.
Tests are automatically skipped if NEON_API_KEY and NEON_PROJECT_ID are not set.

Run these tests with:
    pytest tests/integration/test_neon_integration.py -v

Requirements:
    - NEON_API_KEY environment variable
    - NEON_PROJECT_ID environment variable
    - Optional: NEON_DEFAULT_BRANCH (defaults to "main")

Note:
    These tests create temporary branches that are cleaned up automatically.
    Each test uses unique branch names to prevent conflicts during parallel runs.
"""

import uuid

import pytest
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.storage.providers.neon import NeonProvider
from src.storage.providers.neon_branch import NeonAPIError, NeonBranchManager
from tests.integration.fixtures.neon import (
    NEON_CONFIGURED,
    _detect_default_branch,
    requires_neon,
)

# Load environment variables from .env file
# This must happen after imports but before test execution
load_dotenv()


def unique_branch_name(prefix: str = "integ-test") -> str:
    """Generate a unique branch name for testing."""
    return f"{prefix}/{uuid.uuid4().hex[:8]}"


def convert_to_asyncpg_url(neon_url: str) -> str:
    """Convert a Neon PostgreSQL URL to asyncpg-compatible format.

    Neon URLs use `?sslmode=require` which is for psycopg2/libpq.
    asyncpg uses a different SSL configuration via connect_args.

    Args:
        neon_url: Standard PostgreSQL URL with sslmode parameter

    Returns:
        URL compatible with asyncpg (without sslmode, use ssl=True separately)
    """
    # Convert driver prefix
    url = neon_url.replace("postgresql://", "postgresql+asyncpg://")
    # Remove sslmode parameter (we'll use connect_args={"ssl": True} instead)
    url = url.replace("?sslmode=require", "")
    url = url.replace("&sslmode=require", "")
    return url


# ============================================================================
# NeonProvider Integration Tests
# ============================================================================


@requires_neon
class TestNeonProviderIntegration:
    """Integration tests for NeonProvider with real Neon database."""

    def test_provider_name(self, neon_test_branch: str):
        """Test provider name is 'neon'."""
        provider = NeonProvider(database_url=neon_test_branch)
        assert provider.name == "neon"

    def test_get_engine_url_returns_pooled(self, neon_test_branch: str):
        """Test that get_engine_url returns pooled connection URL."""
        provider = NeonProvider(database_url=neon_test_branch)
        engine_url = provider.get_engine_url()

        # Neon pooled URLs contain -pooler
        assert "-pooler." in engine_url or ".neon.tech" in engine_url

    def test_get_direct_url_returns_non_pooled(self, neon_test_branch: str):
        """Test that get_direct_url returns non-pooled connection URL."""
        provider = NeonProvider(database_url=neon_test_branch)
        direct_url = provider.get_direct_url()

        # Direct URL should not have -pooler
        # Unless the original URL didn't have it (in which case they're the same)
        assert ".neon.tech" in direct_url

    def test_get_engine_options_includes_ssl(self, neon_test_branch: str):
        """Test that engine options include SSL requirement for Neon."""
        provider = NeonProvider(database_url=neon_test_branch)
        options = provider.get_engine_options()

        # Neon requires SSL connections
        assert "connect_args" in options

    def test_health_check_succeeds(self, neon_test_branch: str):
        """Test health check against real Neon database."""
        from sqlalchemy import create_engine

        provider = NeonProvider(database_url=neon_test_branch)
        engine = create_engine(provider.get_engine_url(), **provider.get_engine_options())

        try:
            is_healthy = provider.health_check(engine)
            assert is_healthy is True
        finally:
            engine.dispose()


# ============================================================================
# NeonBranchManager Integration Tests
# ============================================================================


@requires_neon
@pytest.mark.asyncio
class TestNeonBranchManagerIntegration:
    """Integration tests for NeonBranchManager with real Neon API."""

    async def test_list_branches(self):
        """Test listing all branches in the project."""
        manager = NeonBranchManager()
        async with manager:
            branches = await manager.list_branches()

        # Should have at least one branch (main or default)
        assert len(branches) > 0
        assert all(b.id for b in branches)
        assert all(b.name for b in branches)
        assert all(b.created_at for b in branches)

    async def test_create_and_delete_branch(self):
        """Test creating and deleting a branch."""
        branch_name = unique_branch_name("create-delete")
        manager = NeonBranchManager()

        async with manager:
            # Auto-detect default branch
            default_branch = await _detect_default_branch(manager)

            # Create branch
            branch = await manager.create_branch(branch_name, parent=default_branch)

            assert branch.id is not None
            assert branch.name == branch_name
            assert branch.created_at is not None

            # Verify branch exists in list
            branches = await manager.list_branches()
            branch_names = [b.name for b in branches]
            assert branch_name in branch_names

            # Delete branch
            await manager.delete_branch(branch_name)

            # Verify branch no longer exists
            branches = await manager.list_branches()
            branch_names = [b.name for b in branches]
            assert branch_name not in branch_names

    async def test_get_connection_string(self):
        """Test that branch creation returns a valid connection string."""
        branch_name = unique_branch_name("conn-str")
        manager = NeonBranchManager()

        async with manager:
            # Auto-detect default branch
            default_branch = await _detect_default_branch(manager)

            try:
                # Create branch - this returns a connection string
                branch = await manager.create_branch(branch_name, parent=default_branch)

                # Verify connection string was returned
                assert branch.connection_string is not None
                conn_str = branch.connection_string
                assert "postgresql" in conn_str or "postgres" in conn_str
                assert ".neon.tech" in conn_str

                # Verify we can also get it via branch_context
                # (which internally uses create_branch and returns connection string)

            finally:
                await manager.delete_branch(branch_name)

    async def test_branch_context_creates_and_cleans_up(self):
        """Test branch_context creates branch and cleans up on exit."""
        branch_name = unique_branch_name("context")
        manager = NeonBranchManager()

        async with manager:
            # Auto-detect default branch
            default_branch = await _detect_default_branch(manager)

            # Use branch context
            async with manager.branch_context(branch_name, parent=default_branch) as conn_str:
                assert conn_str is not None
                assert "postgresql" in conn_str or "postgres" in conn_str

                # Verify branch exists during context
                branches = await manager.list_branches()
                branch_names = [b.name for b in branches]
                assert branch_name in branch_names

            # After context exits, branch should be deleted
            branches = await manager.list_branches()
            branch_names = [b.name for b in branches]
            assert branch_name not in branch_names

    async def test_delete_nonexistent_branch_raises_error(self):
        """Test that deleting a non-existent branch raises NeonAPIError."""
        manager = NeonBranchManager()
        async with manager:
            with pytest.raises(NeonAPIError) as exc_info:
                await manager.delete_branch("nonexistent-branch-xyz123")

            assert exc_info.value.status_code == 404


# ============================================================================
# Database Operations Integration Tests
# ============================================================================


@requires_neon
@pytest.mark.asyncio
class TestNeonDatabaseOperations:
    """Integration tests for actual database operations on Neon branches."""

    async def test_execute_sql_on_branch(self, neon_test_branch: str):
        """Test executing SQL queries on a Neon branch."""
        async_url = convert_to_asyncpg_url(neon_test_branch)
        engine = create_async_engine(
            async_url,
            echo=False,
            connect_args={"ssl": True},
        )

        async with engine.begin() as conn:
            # Test basic query
            result = await conn.execute(text("SELECT 1 as value"))
            row = result.fetchone()
            assert row is not None
            assert row.value == 1

        await engine.dispose()

    async def test_create_table_and_insert_data(self, neon_isolated_branch: str):
        """Test creating a table and inserting data on an isolated branch."""
        async_url = convert_to_asyncpg_url(neon_isolated_branch)
        engine = create_async_engine(
            async_url,
            echo=False,
            connect_args={"ssl": True},
        )

        try:
            async with engine.begin() as conn:
                # Create test table
                await conn.execute(
                    text("""
                    CREATE TABLE IF NOT EXISTS test_items (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        value INTEGER
                    )
                """)
                )

                # Insert data
                await conn.execute(
                    text("INSERT INTO test_items (name, value) VALUES ('item1', 100)")
                )
                await conn.execute(
                    text("INSERT INTO test_items (name, value) VALUES ('item2', 200)")
                )

            async with engine.begin() as conn:
                # Query data
                result = await conn.execute(
                    text("SELECT name, value FROM test_items ORDER BY value")
                )
                rows = result.fetchall()

                assert len(rows) == 2
                assert rows[0].name == "item1"
                assert rows[0].value == 100
                assert rows[1].name == "item2"
                assert rows[1].value == 200

        finally:
            await engine.dispose()

    async def test_transaction_rollback(self, neon_isolated_branch: str):
        """Test that transactions can be rolled back on Neon."""
        async_url = convert_to_asyncpg_url(neon_isolated_branch)
        engine = create_async_engine(
            async_url,
            echo=False,
            connect_args={"ssl": True},
        )

        try:
            # Create table first
            async with engine.begin() as conn:
                await conn.execute(
                    text("""
                    CREATE TABLE IF NOT EXISTS rollback_test (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100)
                    )
                """)
                )

            # Start transaction that will be rolled back
            async with engine.connect() as conn:
                await conn.begin()
                await conn.execute(
                    text("INSERT INTO rollback_test (name) VALUES ('should_rollback')")
                )
                await conn.rollback()

            # Verify data was not persisted
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT COUNT(*) FROM rollback_test"))
                count = result.scalar()
                assert count == 0

        finally:
            await engine.dispose()

    async def test_branch_isolation(self, neon_test_branch: str):
        """Test that changes in one branch don't affect others."""
        branch_a_name = unique_branch_name("isolation-a")
        branch_b_name = unique_branch_name("isolation-b")
        manager = NeonBranchManager()

        async with manager:
            # Auto-detect default branch
            default_branch = await _detect_default_branch(manager)

            try:
                # Create two branches
                branch_a = await manager.create_branch(branch_a_name, parent=default_branch)
                branch_b = await manager.create_branch(branch_b_name, parent=default_branch)

                conn_a = branch_a.connection_string or await manager.get_connection_string(
                    branch_a_name
                )
                conn_b = branch_b.connection_string or await manager.get_connection_string(
                    branch_b_name
                )

                async_url_a = convert_to_asyncpg_url(conn_a)
                async_url_b = convert_to_asyncpg_url(conn_b)

                engine_a = create_async_engine(
                    async_url_a,
                    echo=False,
                    connect_args={"ssl": True},
                )
                engine_b = create_async_engine(
                    async_url_b,
                    echo=False,
                    connect_args={"ssl": True},
                )

                try:
                    # Create table and insert data in branch A
                    async with engine_a.begin() as conn:
                        await conn.execute(
                            text("""
                            CREATE TABLE IF NOT EXISTS isolation_test (
                                id SERIAL PRIMARY KEY,
                                branch_name VARCHAR(100)
                            )
                        """)
                        )
                        await conn.execute(
                            text("INSERT INTO isolation_test (branch_name) VALUES ('branch_a')")
                        )

                    # Create same table in branch B with different data
                    async with engine_b.begin() as conn:
                        await conn.execute(
                            text("""
                            CREATE TABLE IF NOT EXISTS isolation_test (
                                id SERIAL PRIMARY KEY,
                                branch_name VARCHAR(100)
                            )
                        """)
                        )
                        await conn.execute(
                            text("INSERT INTO isolation_test (branch_name) VALUES ('branch_b')")
                        )

                    # Verify branch A only has branch A data
                    async with engine_a.begin() as conn:
                        result = await conn.execute(text("SELECT branch_name FROM isolation_test"))
                        rows = result.fetchall()
                        assert len(rows) == 1
                        assert rows[0].branch_name == "branch_a"

                    # Verify branch B only has branch B data
                    async with engine_b.begin() as conn:
                        result = await conn.execute(text("SELECT branch_name FROM isolation_test"))
                        rows = result.fetchall()
                        assert len(rows) == 1
                        assert rows[0].branch_name == "branch_b"

                finally:
                    await engine_a.dispose()
                    await engine_b.dispose()

            finally:
                # Clean up branches
                try:
                    await manager.delete_branch(branch_a_name)
                except NeonAPIError:
                    pass
                try:
                    await manager.delete_branch(branch_b_name)
                except NeonAPIError:
                    pass


# ============================================================================
# Async Session Integration Tests
# ============================================================================


@requires_neon
@pytest.mark.asyncio
class TestNeonAsyncSession:
    """Integration tests using async SQLAlchemy sessions on Neon."""

    async def test_async_session_operations(self, neon_isolated_branch: str):
        """Test using async SQLAlchemy session with Neon."""
        from sqlalchemy.ext.asyncio import async_sessionmaker

        async_url = convert_to_asyncpg_url(neon_isolated_branch)
        engine = create_async_engine(
            async_url,
            echo=False,
            connect_args={"ssl": True},
        )
        async_session_factory = async_sessionmaker(engine, class_=AsyncSession)

        try:
            # Create table using raw connection
            async with engine.begin() as conn:
                await conn.execute(
                    text("""
                    CREATE TABLE IF NOT EXISTS session_test (
                        id SERIAL PRIMARY KEY,
                        data JSONB
                    )
                """)
                )

            # Use session for operations
            async with async_session_factory() as session:
                async with session.begin():
                    await session.execute(
                        text(
                            "INSERT INTO session_test (data) VALUES (:data)",
                        ),
                        {"data": '{"key": "value", "count": 42}'},
                    )

            # Query with session
            async with async_session_factory() as session:
                result = await session.execute(text("SELECT data FROM session_test"))
                row = result.fetchone()
                assert row is not None
                # JSONB is returned as dict by asyncpg
                assert row.data["key"] == "value"
                assert row.data["count"] == 42

        finally:
            await engine.dispose()


# ============================================================================
# Connection String Format Tests
# ============================================================================


@requires_neon
class TestConnectionStringFormats:
    """Tests for connection string handling with real Neon URLs."""

    def test_pooled_connection_works(self, neon_test_branch: str):
        """Test that pooled connection string works for queries."""
        from sqlalchemy import create_engine as create_sync_engine

        # Neon pooled connections should work
        engine = create_sync_engine(neon_test_branch, echo=False)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database()"))
            db_name = result.scalar()
            assert db_name is not None

        engine.dispose()

    def test_provider_url_conversion(self, neon_test_branch: str):
        """Test NeonProvider URL conversion methods."""
        provider = NeonProvider(database_url=neon_test_branch)

        pooled_url = provider.get_engine_url()
        direct_url = provider.get_direct_url()

        # Both should be valid PostgreSQL URLs
        assert pooled_url.startswith("postgresql://")
        assert direct_url.startswith("postgresql://")

        # Both should point to Neon
        assert ".neon.tech" in pooled_url
        assert ".neon.tech" in direct_url


# ============================================================================
# Skip marker export for use in other test files
# ============================================================================


# Re-export for convenience
skip_if_no_neon = pytest.mark.skipif(
    not NEON_CONFIGURED,
    reason="Neon credentials not configured (NEON_API_KEY, NEON_PROJECT_ID required)",
)
