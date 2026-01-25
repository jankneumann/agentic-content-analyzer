"""PGQueuer setup and configuration.

This module provides the queue infrastructure using PGQueuer,
a PostgreSQL-based task queue that uses SELECT FOR UPDATE SKIP LOCKED
for efficient job distribution.

Key features:
- Durable jobs that survive restarts
- Priority-based execution
- Retry logic with backoff
- Direct database connections (bypasses pooler)
"""

from typing import TYPE_CHECKING

import asyncpg
from pgqueuer import PgQueuer
from pgqueuer.db import AsyncpgDriver
from pgqueuer.queries import Queries

from src.storage.database import get_queue_connection_string
from src.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Global queue instance
_queue: PgQueuer | None = None
_connection: asyncpg.Connection | None = None


def _sqlalchemy_url_to_asyncpg(url: str) -> str:
    """Convert SQLAlchemy URL format to asyncpg format.

    SQLAlchemy uses: postgresql://user:pass@host/db
    asyncpg expects: postgres://user:pass@host/db

    Args:
        url: SQLAlchemy-style database URL

    Returns:
        asyncpg-compatible URL
    """
    # asyncpg accepts both postgresql:// and postgres://
    # but we normalize to postgres:// for consistency
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgres://", 1)
    return url


async def get_queue() -> PgQueuer:
    """Get or create the PGQueuer instance.

    Uses the DatabaseProvider abstraction to get the appropriate
    direct connection URL for the current database provider.

    Returns:
        Configured PGQueuer instance
    """
    global _queue, _connection

    if _queue is None:
        # Get queue URL from provider (direct connection, not pooled)
        queue_url = get_queue_connection_string()
        asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)

        logger.info("Creating PGQueuer connection...")

        # Create asyncpg connection
        _connection = await asyncpg.connect(asyncpg_url)

        # Create PGQueuer instance
        driver = AsyncpgDriver(_connection)
        _queue = PgQueuer(driver)

        logger.info("PGQueuer initialized successfully")

    return _queue


async def get_queue_queries() -> Queries:
    """Get Queries instance for enqueuing jobs.

    This is used by the web application to enqueue jobs
    without needing the full PGQueuer worker setup.

    Returns:
        Queries instance for enqueue operations
    """
    pgq = await get_queue()
    return Queries(pgq.driver)


async def close_queue() -> None:
    """Close the queue connection.

    Should be called during application shutdown.
    """
    global _queue, _connection

    if _connection is not None:
        await _connection.close()
        _connection = None
        _queue = None
        logger.info("PGQueuer connection closed")


async def init_queue_schema() -> None:
    """Initialize the PGQueuer database schema.

    Creates the required tables if they don't exist.
    This should be run during deployment or migration.
    """
    queue_url = get_queue_connection_string()
    asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)

    conn = await asyncpg.connect(asyncpg_url)
    try:
        # Create the pgqueuer_jobs table if it doesn't exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pgqueuer_jobs (
                id BIGSERIAL PRIMARY KEY,
                entrypoint TEXT NOT NULL,
                payload JSONB DEFAULT '{}'::jsonb,
                priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'queued',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                execute_after TIMESTAMPTZ DEFAULT NOW(),
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ,
                error TEXT,
                retry_count INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_pgqueuer_jobs_status
                ON pgqueuer_jobs(status, execute_after, priority DESC);

            CREATE INDEX IF NOT EXISTS idx_pgqueuer_jobs_entrypoint
                ON pgqueuer_jobs(entrypoint);
        """)

        # Create helper function for pg_cron to enqueue jobs
        await conn.execute("""
            CREATE OR REPLACE FUNCTION pgqueuer_enqueue(
                p_entrypoint TEXT,
                p_payload JSONB DEFAULT '{}'::jsonb,
                p_priority INTEGER DEFAULT 0
            ) RETURNS BIGINT AS $$
            DECLARE
                v_job_id BIGINT;
            BEGIN
                INSERT INTO pgqueuer_jobs (entrypoint, payload, priority, status, created_at, execute_after)
                VALUES (p_entrypoint, p_payload, p_priority, 'queued', NOW(), NOW())
                RETURNING id INTO v_job_id;

                -- Notify workers (PGQueuer listens on this channel)
                PERFORM pg_notify('pgqueuer', p_entrypoint);

                RETURN v_job_id;
            END;
            $$ LANGUAGE plpgsql;
        """)

        logger.info("PGQueuer schema initialized successfully")

    finally:
        await conn.close()
