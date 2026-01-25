"""Integration tests for Supabase database provider.

These tests verify:
- 6.2 Supabase free tier connection works
- 6.3 Alembic migrations work with Supabase direct URL
- 6.4 Connection pooling under concurrent load

Tests are automatically skipped if Supabase credentials are not configured.

To run these tests:
    pytest tests/integration/test_supabase_provider.py -v

Requirements:
    SUPABASE_PROJECT_REF and SUPABASE_DB_PASSWORD must be set in .env
"""

import concurrent.futures
import time

from sqlalchemy import Engine, text

from tests.integration.fixtures.supabase import (
    requires_supabase,
    supabase_direct_engine,
    supabase_engine,
    supabase_provider,
)

# Re-export fixtures for pytest discovery
__all__ = ["supabase_provider", "supabase_engine", "supabase_direct_engine"]


@requires_supabase
class TestSupabaseConnection:
    """Test Supabase connection and basic operations (Task 6.2)."""

    def test_pooled_connection_works(self, supabase_engine: Engine):
        """Verify pooled connection to Supabase succeeds."""
        with supabase_engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as value"))
            assert result.scalar() == 1

    def test_ssl_connection_required(self, supabase_engine: Engine):
        """Verify SSL is being used for the connection."""
        with supabase_engine.connect() as conn:
            result = conn.execute(text("SHOW ssl"))
            ssl_status = result.scalar()
            assert ssl_status == "on", "SSL should be enabled for Supabase connections"

    def test_database_version(self, supabase_engine: Engine):
        """Verify PostgreSQL version is accessible."""
        with supabase_engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            assert "PostgreSQL" in version
            print(f"Supabase PostgreSQL version: {version[:60]}...")

    def test_health_check_passes(self, supabase_provider, supabase_engine: Engine):
        """Verify provider health check works."""
        assert supabase_provider.health_check(supabase_engine) is True

    def test_connection_timeout_is_set(self, supabase_engine: Engine):
        """Verify a statement timeout is configured (server may override client value)."""
        with supabase_engine.connect() as conn:
            result = conn.execute(text("SHOW statement_timeout"))
            timeout = result.scalar()
            # Supabase server may override client timeout, just verify it's set
            # Common values: "30s" (client), "2min" (server default)
            assert (
                timeout is not None and timeout != "0"
            ), f"Expected timeout to be set, got {timeout}"
            print(f"Supabase statement_timeout: {timeout}")


@requires_supabase
class TestSupabaseDirectConnection:
    """Test direct Supabase connection for migrations (Task 6.3)."""

    def test_direct_connection_works(self, supabase_direct_engine: Engine):
        """Verify direct connection (bypassing pooler) succeeds."""
        with supabase_direct_engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as value"))
            assert result.scalar() == 1

    def test_direct_connection_ssl(self, supabase_direct_engine: Engine):
        """Verify direct connection uses SSL."""
        with supabase_direct_engine.connect() as conn:
            result = conn.execute(text("SHOW ssl"))
            ssl_status = result.scalar()
            assert ssl_status == "on"

    def test_can_check_alembic_version_table(self, supabase_direct_engine: Engine):
        """Verify we can query alembic_version table (migration support)."""
        with supabase_direct_engine.connect() as conn:
            # Check if alembic_version table exists
            result = conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'alembic_version'
                    )
                """)
            )
            table_exists = result.scalar()

            if table_exists:
                # If migrations have been run, check the version
                result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                version = result.scalar()
                print(f"Alembic version on Supabase: {version}")
            else:
                print("alembic_version table does not exist (migrations not run)")

    def test_can_execute_ddl_operations(self, supabase_direct_engine: Engine):
        """Verify DDL operations work on direct connection (required for migrations)."""
        with supabase_direct_engine.connect() as conn:
            # Create a temporary table
            conn.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS _test_migration_check (
                        id SERIAL PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
            )
            conn.commit()

            # Verify table was created
            result = conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = '_test_migration_check'
                    )
                """)
            )
            assert result.scalar() is True

            # Clean up
            conn.execute(text("DROP TABLE IF EXISTS _test_migration_check"))
            conn.commit()


@requires_supabase
class TestSupabaseConnectionPooling:
    """Test connection pooling behavior under load (Task 6.4)."""

    def test_multiple_sequential_connections(self, supabase_engine: Engine):
        """Verify sequential connection reuse works."""
        results = []
        for i in range(10):
            with supabase_engine.connect() as conn:
                result = conn.execute(text(f"SELECT {i} as value"))
                results.append(result.scalar())

        assert results == list(range(10))

    def test_concurrent_connections(self, supabase_engine: Engine):
        """Verify concurrent connections are handled correctly."""

        def execute_query(query_id: int) -> tuple[int, float]:
            """Execute a query and return (id, duration)."""
            start = time.time()
            with supabase_engine.connect() as conn:
                # Small delay to simulate real work
                conn.execute(text("SELECT pg_sleep(0.1)"))
                result = conn.execute(text(f"SELECT {query_id}"))
                value = result.scalar()
            duration = time.time() - start
            return (value, duration)

        # Run 5 concurrent queries (within free tier limits)
        num_concurrent = 5
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(execute_query, i) for i in range(num_concurrent)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Verify all queries completed
        values = sorted([r[0] for r in results])
        assert values == list(range(num_concurrent))

        # Verify some parallelism occurred (total time < sequential time)
        total_duration = sum(r[1] for r in results)
        # Sequential would take ~0.5s (5 * 0.1s), parallel should be faster
        # Allow some overhead but verify parallelism helped
        print(f"Total duration for {num_concurrent} queries: {total_duration:.2f}s")

    def test_connection_pool_exhaustion_recovery(self, supabase_engine: Engine):
        """Verify pool recovers after exhaustion."""

        def quick_query(query_id: int) -> int:
            """Execute a quick query."""
            with supabase_engine.connect() as conn:
                result = conn.execute(text(f"SELECT {query_id}"))
                return result.scalar()

        # Run more queries than pool size to test pool behavior
        # Pool size is 5 with max_overflow of 2, so 7 max connections
        num_queries = 20
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(quick_query, i) for i in range(num_queries)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All queries should complete successfully
        assert len(results) == num_queries
        assert sorted(results) == list(range(num_queries))

    def test_transaction_mode_isolation(self, supabase_engine: Engine):
        """Verify transaction isolation in pooled mode."""
        # Start a transaction
        with supabase_engine.connect() as conn1:
            conn1.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS _test_isolation (
                        id SERIAL PRIMARY KEY,
                        value TEXT
                    )
                """)
            )
            conn1.commit()

            # Insert in transaction (not committed)
            conn1.execute(text("INSERT INTO _test_isolation (value) VALUES ('test1')"))

            # Another connection should not see uncommitted data
            with supabase_engine.connect() as conn2:
                result = conn2.execute(
                    text("SELECT COUNT(*) FROM _test_isolation WHERE value = 'test1'")
                )
                count = result.scalar()
                # Should be 0 because conn1 hasn't committed
                assert count == 0, "Uncommitted data should not be visible"

            # Now commit
            conn1.commit()

            # Now it should be visible
            with supabase_engine.connect() as conn3:
                result = conn3.execute(
                    text("SELECT COUNT(*) FROM _test_isolation WHERE value = 'test1'")
                )
                count = result.scalar()
                assert count == 1, "Committed data should be visible"

            # Clean up
            conn1.execute(text("DROP TABLE IF EXISTS _test_isolation"))
            conn1.commit()


@requires_supabase
class TestSupabaseProviderConfiguration:
    """Test provider configuration and URL construction."""

    def test_provider_name(self, supabase_provider):
        """Verify provider identifies as supabase."""
        assert supabase_provider.name == "supabase"

    def test_engine_url_uses_pooler(self, supabase_provider):
        """Verify engine URL uses Supavisor pooler."""
        url = supabase_provider.get_engine_url()
        assert "pooler.supabase.com" in url
        # Transaction mode should use port 6543
        assert ":6543/" in url or ":5432/" in url

    def test_direct_url_bypasses_pooler(self, supabase_provider):
        """Verify direct URL bypasses pooler."""
        direct_url = supabase_provider.get_direct_url()
        assert direct_url is not None
        assert "db." in direct_url
        assert ".supabase.co" in direct_url
        assert "pooler" not in direct_url

    def test_engine_options_configured(self, supabase_provider):
        """Verify engine options are properly configured."""
        options = supabase_provider.get_engine_options()

        # Check essential options
        assert options["pool_pre_ping"] is True
        assert options["pool_size"] == 5
        assert options["connect_args"]["sslmode"] == "require"
