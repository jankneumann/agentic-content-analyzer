"""PGQueuer setup and configuration.

This module provides the queue infrastructure using PGQueuer,
a PostgreSQL-based task queue that uses SELECT FOR UPDATE SKIP LOCKED
for efficient job distribution.

Key features:
- Durable jobs that survive restarts
- Priority-based execution
- Retry logic with backoff
- Direct database connections (bypasses pooler)
- Job progress tracking via payload JSON

Job Payload Schema:
    {
        "content_id": int,      # ID of content being processed
        "progress": 0-100,      # Completion percentage
        "message": str          # Current status message
    }
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import asyncpg
from pgqueuer import PgQueuer
from pgqueuer.db import AsyncpgDriver
from pgqueuer.queries import Queries

from src.models.jobs import ENTRYPOINT_LABELS, JobHistoryItem, JobListItem, JobRecord, JobStatus
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
    return Queries(pgq.connection)


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


# ============================================================================
# Job Status Helpers (Tasks 2.1, 2.2, 2.3)
# ============================================================================


async def get_job_status(job_id: int) -> JobRecord | None:
    """Fetch job status by ID.

    Used by SSE endpoints and CLI to query job progress.

    Args:
        job_id: The job ID to look up

    Returns:
        JobRecord if found, None if job doesn't exist
    """
    global _connection

    if _connection is None:
        # Get a temporary connection for the query
        queue_url = get_queue_connection_string()
        asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)
        conn = await asyncpg.connect(asyncpg_url)
        should_close = True
    else:
        conn = _connection
        should_close = False

    try:
        row = await conn.fetchrow(
            """
            SELECT
                id,
                entrypoint,
                status,
                payload,
                priority,
                error,
                retry_count,
                created_at,
                started_at,
                completed_at
            FROM pgqueuer_jobs
            WHERE id = $1
            """,
            job_id,
        )

        if row is None:
            return None

        # Parse payload from JSONB
        payload = row["payload"] if row["payload"] else {}
        if isinstance(payload, str):
            payload = json.loads(payload)

        return JobRecord(
            id=row["id"],
            entrypoint=row["entrypoint"],
            status=JobStatus(row["status"]),
            payload=payload,
            priority=row["priority"],
            error=row["error"],
            retry_count=row["retry_count"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    finally:
        if should_close:
            await conn.close()


async def update_job_progress(
    job_id: int,
    progress: int,
    message: str,
) -> None:
    """Update job progress in the payload.

    Merges progress and message into the existing payload JSON,
    and refreshes updated_at timestamp for stale job detection.

    Args:
        job_id: The job ID to update
        progress: Completion percentage (0-100)
        message: Current status message
    """
    global _connection

    if _connection is None:
        queue_url = get_queue_connection_string()
        asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)
        conn = await asyncpg.connect(asyncpg_url)
        should_close = True
    else:
        conn = _connection
        should_close = False

    try:
        # Merge progress into existing payload
        progress_data = json.dumps({"progress": progress, "message": message})
        await conn.execute(
            """
            UPDATE pgqueuer_jobs
            SET payload = COALESCE(payload, '{}'::jsonb) || $1::jsonb
            WHERE id = $2
            """,
            progress_data,
            job_id,
        )
        logger.debug(f"Updated job {job_id} progress: {progress}% - {message}")

    finally:
        if should_close:
            await conn.close()


async def list_jobs(
    *,
    status: JobStatus | None = None,
    entrypoint: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[JobListItem], int]:
    """List jobs with optional filters.

    Args:
        status: Filter by job status
        entrypoint: Filter by task entrypoint
        limit: Maximum jobs to return (default 20, max 100)
        offset: Pagination offset

    Returns:
        Tuple of (jobs list, total count)
    """
    global _connection

    if _connection is None:
        queue_url = get_queue_connection_string()
        asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)
        conn = await asyncpg.connect(asyncpg_url)
        should_close = True
    else:
        conn = _connection
        should_close = False

    # Clamp limit
    limit = min(limit, 100)

    try:
        # Build WHERE clause
        conditions = []
        params: list[Any] = []
        param_idx = 1

        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status.value)
            param_idx += 1

        if entrypoint:
            conditions.append(f"entrypoint = ${param_idx}")
            params.append(entrypoint)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Get total count
        # Note: where_clause is built from controlled inputs (status/entrypoint enum values)
        # not user input, so this is safe from SQL injection
        count_query = f"SELECT COUNT(*) FROM pgqueuer_jobs WHERE {where_clause}"  # noqa: S608
        total = await conn.fetchval(count_query, *params)

        # Get jobs
        params.extend([limit, offset])
        # Note: where_clause is built from controlled inputs, not user input
        query = f"""
            SELECT
                id,
                entrypoint,
                status,
                payload,
                error,
                created_at,
                started_at
            FROM pgqueuer_jobs
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """  # noqa: S608

        rows = await conn.fetch(query, *params)

        jobs = []
        for row in rows:
            payload = row["payload"] if row["payload"] else {}
            if isinstance(payload, str):
                payload = json.loads(payload)

            jobs.append(
                JobListItem(
                    id=row["id"],
                    entrypoint=row["entrypoint"],
                    status=JobStatus(row["status"]),
                    progress=payload.get("progress", 0),
                    error=row["error"],
                    created_at=row["created_at"],
                    updated_at=row["started_at"],
                )
            )

        return jobs, total

    finally:
        if should_close:
            await conn.close()


async def retry_failed_job(job_id: int) -> JobRecord | None:
    """Re-enqueue a failed job for retry.

    Only works for jobs in 'failed' status.

    Args:
        job_id: The job ID to retry

    Returns:
        Updated JobRecord if successful, None if job not found or not retryable
    """
    global _connection

    if _connection is None:
        queue_url = get_queue_connection_string()
        asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)
        conn = await asyncpg.connect(asyncpg_url)
        should_close = True
    else:
        conn = _connection
        should_close = False

    try:
        # Only retry failed jobs
        result = await conn.fetchrow(
            """
            UPDATE pgqueuer_jobs
            SET
                status = 'queued',
                error = NULL,
                retry_count = retry_count + 1,
                started_at = NULL,
                completed_at = NULL,
                execute_after = NOW()
            WHERE id = $1 AND status = 'failed'
            RETURNING id
            """,
            job_id,
        )

        if result is None:
            return None

        # Notify workers
        await conn.execute("SELECT pg_notify('pgqueuer', 'job_retry')")

        return await get_job_status(job_id)

    finally:
        if should_close:
            await conn.close()


async def cleanup_old_jobs(older_than_days: int = 30) -> int:
    """Delete old completed jobs.

    Only deletes jobs with status='completed'. Never deletes
    queued, in_progress, or failed jobs.

    Args:
        older_than_days: Delete completed jobs older than this many days

    Returns:
        Number of jobs deleted
    """
    global _connection

    if _connection is None:
        queue_url = get_queue_connection_string()
        asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)
        conn = await asyncpg.connect(asyncpg_url)
        should_close = True
    else:
        conn = _connection
        should_close = False

    try:
        cutoff = datetime.now(UTC) - timedelta(days=older_than_days)

        result = await conn.execute(
            """
            DELETE FROM pgqueuer_jobs
            WHERE status = 'completed'
              AND completed_at < $1
            """,
            cutoff,
        )

        # Parse "DELETE N" result
        count = int(result.split()[-1]) if result else 0
        logger.info(f"Cleaned up {count} old completed jobs (older than {older_than_days} days)")
        return count

    finally:
        if should_close:
            await conn.close()


async def mark_stale_jobs_failed(stale_threshold_hours: int = 1) -> int:
    """Mark stale in_progress jobs as failed.

    Jobs stuck in 'in_progress' for longer than the threshold
    are assumed to have crashed and are marked failed.

    Args:
        stale_threshold_hours: Hours before a job is considered stale

    Returns:
        Number of jobs marked as failed
    """
    global _connection

    if _connection is None:
        queue_url = get_queue_connection_string()
        asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)
        conn = await asyncpg.connect(asyncpg_url)
        should_close = True
    else:
        conn = _connection
        should_close = False

    try:
        cutoff = datetime.now(UTC) - timedelta(hours=stale_threshold_hours)

        result = await conn.execute(
            """
            UPDATE pgqueuer_jobs
            SET
                status = 'failed',
                error = 'stale_timeout',
                completed_at = NOW()
            WHERE status = 'in_progress'
              AND started_at < $1
            """,
            cutoff,
        )

        # Parse "UPDATE N" result
        count = int(result.split()[-1]) if result else 0
        if count > 0:
            logger.warning(
                f"Marked {count} stale jobs as failed (threshold: {stale_threshold_hours}h)"
            )
        return count

    finally:
        if should_close:
            await conn.close()


async def enqueue_summarization_job(content_id: int) -> int | None:
    """Enqueue a content item for summarization.

    Implements idempotency: skips if the content_id is already
    queued or in_progress for summarization.

    Args:
        content_id: ID of the content to summarize

    Returns:
        Job ID if enqueued, None if already in queue
    """
    global _connection

    if _connection is None:
        queue_url = get_queue_connection_string()
        asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)
        conn = await asyncpg.connect(asyncpg_url)
        should_close = True
    else:
        conn = _connection
        should_close = False

    try:
        # Check if already queued or in_progress
        existing = await conn.fetchval(
            """
            SELECT id FROM pgqueuer_jobs
            WHERE entrypoint = 'summarize_content'
              AND (payload->>'content_id')::int = $1
              AND status IN ('queued', 'in_progress')
            """,
            content_id,
        )

        if existing:
            logger.debug(f"Content {content_id} already in queue (job {existing})")
            return None

        # Enqueue new job
        payload = json.dumps({"content_id": content_id, "progress": 0, "message": "Queued"})
        job_id: int | None = await conn.fetchval(
            """
            INSERT INTO pgqueuer_jobs (entrypoint, payload, status, created_at, execute_after)
            VALUES ('summarize_content', $1::jsonb, 'queued', NOW(), NOW())
            RETURNING id
            """,
            payload,
        )

        # Notify workers
        await conn.execute("SELECT pg_notify('pgqueuer', 'summarize_content')")

        logger.info(f"Enqueued summarization job {job_id} for content {content_id}")
        return job_id

    finally:
        if should_close:
            await conn.close()


async def reconcile_batch_job_status(
    content_id: int,
    *,
    include_current_as_completed: bool = True,
) -> None:
    """Check and update batch job status after a child job completes.

    When a summarize_content job finishes, this function checks if it belongs
    to a summarize_batch parent job. If all child jobs are now complete,
    it marks the parent batch job as completed.

    This ensures batch jobs reach terminal state without requiring SSE polling.

    Args:
        content_id: The content_id of the just-completed child job
        include_current_as_completed: If True, count the current job as completed
            even if PGQueuer hasn't updated its status yet. Set to True when calling
            from within a task that's about to return successfully.
    """
    global _connection

    if _connection is None:
        queue_url = get_queue_connection_string()
        asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)
        conn = await asyncpg.connect(asyncpg_url)
        should_close = True
    else:
        conn = _connection
        should_close = False

    try:
        # Find any in_progress batch jobs that include this content_id
        batch_jobs = await conn.fetch(
            """
            SELECT id, payload
            FROM pgqueuer_jobs
            WHERE entrypoint = 'summarize_batch'
              AND status = 'in_progress'
              AND payload->'content_ids' @> $1::jsonb
            """,
            json.dumps([content_id]),
        )

        for batch_job in batch_jobs:
            batch_id = batch_job["id"]
            payload = batch_job["payload"] or {}
            if isinstance(payload, str):
                payload = json.loads(payload)

            content_ids = payload.get("content_ids", [])
            if not content_ids:
                continue

            # Count completed and failed child jobs for this batch
            result = await conn.fetch(
                """
                SELECT status, COUNT(*) as cnt
                FROM pgqueuer_jobs
                WHERE entrypoint = 'summarize_content'
                  AND (payload->>'content_id')::int = ANY($1)
                  AND status IN ('completed', 'failed')
                GROUP BY status
                """,
                content_ids,
            )

            completed = 0
            failed = 0
            for row in result:
                if row["status"] == "completed":
                    completed = row["cnt"]
                elif row["status"] == "failed":
                    failed = row["cnt"]

            # If called from within a completing task, check if the current job
            # is still 'in_progress' and count it as completing
            if include_current_as_completed:
                current_job_status = await conn.fetchval(
                    """
                    SELECT status FROM pgqueuer_jobs
                    WHERE entrypoint = 'summarize_content'
                      AND (payload->>'content_id')::int = $1
                      AND status = 'in_progress'
                    """,
                    content_id,
                )
                if current_job_status:
                    # Current job is still in_progress but about to complete
                    completed += 1

            total = len(content_ids)
            processed = completed + failed

            # If all child jobs are done, mark the batch as completed
            if processed >= total:
                await conn.execute(
                    """
                    UPDATE pgqueuer_jobs
                    SET status = 'completed', completed_at = NOW()
                    WHERE id = $1 AND status = 'in_progress'
                    """,
                    batch_id,
                )
                logger.info(
                    f"Batch job {batch_id} completed: {completed} succeeded, {failed} failed"
                )

    finally:
        if should_close:
            await conn.close()


def _build_description(
    entrypoint: str,
    payload: dict[str, Any],
    content_title: str | None,
) -> str | None:
    """Build a context-aware description from job data.

    Resolution strategy:
    1. content_id present → content title from DB
    2. source present → "{source} ingestion"
    3. content_ids present → "Batch of {N} items"
    4. message present → last progress message
    5. else None
    """
    if content_title:
        task_type = payload.get("task_type")
        if task_type and entrypoint == "process_content":
            return f"{task_type.capitalize()}: {content_title}"
        return content_title

    source = payload.get("source")
    if source:
        return f"{source.capitalize()} ingestion"

    content_ids = payload.get("content_ids")
    if content_ids and isinstance(content_ids, list):
        return f"Batch of {len(content_ids)} items"

    message = payload.get("message")
    if message and message != "Queued":
        return str(message)

    return None


async def list_job_history(
    *,
    since: datetime | None = None,
    status: JobStatus | None = None,
    entrypoint: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[JobHistoryItem], int]:
    """List job history with enriched descriptions.

    Joins pgqueuer_jobs with the content table to provide human-readable
    context for each job. Uses LEFT JOIN so jobs without content_id
    still appear.

    Args:
        since: Only include jobs created after this time
        status: Filter by job status
        entrypoint: Filter by task entrypoint
        limit: Maximum jobs to return (default 50, max 100)
        offset: Pagination offset

    Returns:
        Tuple of (history items, total count)
    """
    global _connection

    if _connection is None:
        queue_url = get_queue_connection_string()
        asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)
        conn = await asyncpg.connect(asyncpg_url)
        should_close = True
    else:
        conn = _connection
        should_close = False

    limit = min(limit, 100)

    try:
        conditions = []
        params: list[Any] = []
        param_idx = 1

        if since:
            conditions.append(f"j.created_at >= ${param_idx}")
            params.append(since)
            param_idx += 1

        if status:
            conditions.append(f"j.status = ${param_idx}")
            params.append(status.value)
            param_idx += 1

        if entrypoint:
            conditions.append(f"j.entrypoint = ${param_idx}")
            params.append(entrypoint)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Note: where_clause is built from controlled inputs, not user input
        count_query = f"""
            SELECT COUNT(*) FROM pgqueuer_jobs j WHERE {where_clause}
        """  # noqa: S608
        total = await conn.fetchval(count_query, *params)

        params.extend([limit, offset])
        # Note: where_clause is built from controlled inputs, not user input
        query = f"""
            SELECT j.id, j.entrypoint, j.status, j.payload, j.error,
                   j.created_at, j.started_at, j.completed_at,
                   c.id AS content_id, c.title AS content_title
            FROM pgqueuer_jobs j
            LEFT JOIN contents c
              ON j.payload ? 'content_id'
              AND (j.payload->>'content_id')::int = c.id
            WHERE {where_clause}
            ORDER BY j.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """  # noqa: S608

        rows = await conn.fetch(query, *params)

        items = []
        for row in rows:
            payload = row["payload"] if row["payload"] else {}
            if isinstance(payload, str):
                payload = json.loads(payload)

            ep = row["entrypoint"]
            items.append(
                JobHistoryItem(
                    id=row["id"],
                    entrypoint=ep,
                    task_label=ENTRYPOINT_LABELS.get(ep, ep),
                    status=JobStatus(row["status"]),
                    content_id=row["content_id"],
                    description=_build_description(ep, payload, row["content_title"]),
                    error=row["error"],
                    created_at=row["created_at"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                )
            )

        return items, total

    finally:
        if should_close:
            await conn.close()
