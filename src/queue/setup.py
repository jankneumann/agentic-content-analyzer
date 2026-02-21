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

import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
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

DEFAULT_STATUS_POLL_SECONDS = 1.0
DEFAULT_STALE_THRESHOLD_HOURS = 1
REQUIRED_PAYLOAD_FIELDS: dict[str, set[str]] = {
    "summarize_content": {"content_id"},
    "extract_url_content": {"content_id"},
    "ingest_content": {"source", "max_results", "days_back", "force_reprocess"},
}


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


async def _open_queue_connection() -> asyncpg.Connection:
    queue_url = get_queue_connection_string()
    asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)
    return await asyncpg.connect(asyncpg_url)


@asynccontextmanager
async def _queue_connection(
    conn: asyncpg.Connection | None = None,
) -> AsyncIterator[asyncpg.Connection]:
    if conn is not None:
        yield conn
        return
    if _connection is not None:
        yield _connection
        return
    temp = await _open_queue_connection()
    try:
        yield temp
    finally:
        await temp.close()


def _normalize_job_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized.setdefault("progress", 0)
    normalized.setdefault("message", "Queued")
    normalized.setdefault("schema_version", 1)
    return normalized


def _payload_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _validate_payload(entrypoint: str, payload: dict[str, Any]) -> None:
    required = REQUIRED_PAYLOAD_FIELDS.get(entrypoint)
    if not required:
        return
    missing = [field for field in required if payload.get(field) is None]
    if missing:
        raise ValueError(
            f"Invalid payload for '{entrypoint}': missing {', '.join(sorted(missing))}"
        )


def _build_idempotency_key(entrypoint: str, payload: dict[str, Any]) -> str | None:
    if entrypoint in {"summarize_content", "extract_url_content"}:
        content_id = _payload_int(payload, "content_id")
        return f"{entrypoint}:content_id:{content_id}" if content_id else None
    if entrypoint == "ingest_content":
        key_payload = {
            "source": payload.get("source"),
            "max_results": payload.get("max_results"),
            "days_back": payload.get("days_back"),
            "force_reprocess": payload.get("force_reprocess"),
        }
        digest = hashlib.sha256(
            json.dumps(key_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return f"ingest_content:{digest}"
    return None


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
                heartbeat_at TIMESTAMPTZ,
                parent_job_id BIGINT REFERENCES pgqueuer_jobs(id) ON DELETE SET NULL,
                idempotency_key TEXT,
                error TEXT,
                retry_count INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_pgqueuer_jobs_status
                ON pgqueuer_jobs(status, execute_after, priority DESC);

            CREATE INDEX IF NOT EXISTS idx_pgqueuer_jobs_entrypoint
                ON pgqueuer_jobs(entrypoint);

            CREATE INDEX IF NOT EXISTS idx_pgqueuer_jobs_parent_job_id
                ON pgqueuer_jobs(parent_job_id);

            CREATE INDEX IF NOT EXISTS idx_pgqueuer_jobs_heartbeat
                ON pgqueuer_jobs(status, heartbeat_at);

            CREATE UNIQUE INDEX IF NOT EXISTS uq_pgqueuer_jobs_active_dedupe
                ON pgqueuer_jobs(entrypoint, idempotency_key)
                WHERE status IN ('queued', 'in_progress') AND idempotency_key IS NOT NULL;
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


async def get_job_status(
    job_id: int,
    *,
    conn: asyncpg.Connection | None = None,
) -> JobRecord | None:
    """Fetch job status by ID.

    Used by SSE endpoints and CLI to query job progress.

    Args:
        job_id: The job ID to look up

    Returns:
        JobRecord if found, None if job doesn't exist
    """
    async with _queue_connection(conn) as query_conn:
        row = await query_conn.fetchrow(
            """
            SELECT
                id,
                entrypoint,
                status,
                payload,
                priority,
                error,
                retry_count,
                parent_job_id,
                heartbeat_at,
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
        parent_job_id = row.get("parent_job_id", None)
        heartbeat_at = row.get("heartbeat_at", None)

        return JobRecord(
            id=row["id"],
            entrypoint=row["entrypoint"],
            status=JobStatus(row["status"]),
            payload=payload,
            priority=row["priority"],
            error=row["error"],
            retry_count=row["retry_count"],
            parent_job_id=parent_job_id,
            heartbeat_at=heartbeat_at,
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )


async def update_job_progress(
    job_id: int,
    progress: int,
    message: str,
    *,
    conn: asyncpg.Connection | None = None,
) -> None:
    """Update job progress in the payload.

    Merges progress and message into the existing payload JSON,
    and refreshes updated_at timestamp for stale job detection.

    Args:
        job_id: The job ID to update
        progress: Completion percentage (0-100)
        message: Current status message
    """
    async with _queue_connection(conn) as query_conn:
        # Merge progress into existing payload
        progress_data = json.dumps({"progress": progress, "message": message})
        await query_conn.execute(
            """
            UPDATE pgqueuer_jobs
            SET payload = COALESCE(payload, '{}'::jsonb) || $1::jsonb
              , heartbeat_at = NOW()
            WHERE id = $2
            """,
            progress_data,
            job_id,
        )
        logger.debug(f"Updated job {job_id} progress: {progress}% - {message}")


async def touch_job_heartbeat(
    job_id: int,
    *,
    conn: asyncpg.Connection | None = None,
) -> None:
    async with _queue_connection(conn) as query_conn:
        try:
            await query_conn.execute(
                """
                UPDATE pgqueuer_jobs
                SET heartbeat_at = NOW()
                WHERE id = $1
                """,
                job_id,
            )
        except asyncpg.exceptions.UndefinedColumnError:
            # Backward compatibility for environments that have not applied
            # the heartbeat migration yet.
            return


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
    limit = min(limit, 100)

    async with _queue_connection() as conn:
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
                started_at,
                heartbeat_at
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
                    updated_at=row["heartbeat_at"] or row["started_at"] or row["created_at"],
                )
            )

        return jobs, total


async def retry_failed_job(job_id: int) -> JobRecord | None:
    """Re-enqueue a failed job for retry.

    Only works for jobs in 'failed' status.

    Args:
        job_id: The job ID to retry

    Returns:
        Updated JobRecord if successful, None if job not found or not retryable
    """
    async with _queue_connection() as conn:
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
                execute_after = NOW(),
                heartbeat_at = NOW()
            WHERE id = $1 AND status = 'failed'
            RETURNING id
            """,
            job_id,
        )

        if result is None:
            return None

        # Notify workers
        await conn.execute("SELECT pg_notify('pgqueuer', 'job_retry')")

        return await get_job_status(job_id, conn=conn)


async def cleanup_old_jobs(older_than_days: int = 30) -> int:
    """Delete old completed jobs.

    Only deletes jobs with status='completed'. Never deletes
    queued, in_progress, or failed jobs.

    Args:
        older_than_days: Delete completed jobs older than this many days

    Returns:
        Number of jobs deleted
    """
    async with _queue_connection() as conn:
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


async def mark_stale_jobs_failed(
    stale_threshold_hours: int = DEFAULT_STALE_THRESHOLD_HOURS,
) -> int:
    """Mark stale in_progress jobs as failed.

    Jobs stuck in 'in_progress' for longer than the threshold
    are assumed to have crashed and are marked failed.

    Args:
        stale_threshold_hours: Hours before a job is considered stale

    Returns:
        Number of jobs marked as failed
    """
    async with _queue_connection() as conn:
        cutoff = datetime.now(UTC) - timedelta(hours=stale_threshold_hours)

        result = await conn.execute(
            """
            UPDATE pgqueuer_jobs
            SET
                status = 'failed',
                error = 'stale_timeout',
                completed_at = NOW(),
                heartbeat_at = NOW()
            WHERE status = 'in_progress'
              AND COALESCE(heartbeat_at, started_at) < $1
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


async def enqueue_queue_job(
    entrypoint: str,
    payload: dict[str, Any],
    *,
    priority: int = 0,
    parent_job_id: int | None = None,
    conn: asyncpg.Connection | None = None,
) -> tuple[int, bool]:
    """Enqueue with canonical payload and active-job idempotency."""
    _validate_payload(entrypoint, payload)
    payload = _normalize_job_payload(payload)
    idempotency_key = _build_idempotency_key(entrypoint, payload)

    async with _queue_connection(conn) as query_conn:
        row = await query_conn.fetchrow(
            """
            INSERT INTO pgqueuer_jobs (
                entrypoint, payload, priority, status, created_at, execute_after,
                parent_job_id, heartbeat_at, idempotency_key
            )
            VALUES ($1, $2::jsonb, $3, 'queued', NOW(), NOW(), $4, NOW(), $5)
            ON CONFLICT (entrypoint, idempotency_key)
            WHERE status IN ('queued', 'in_progress') AND idempotency_key IS NOT NULL
            DO NOTHING
            RETURNING id
            """,
            entrypoint,
            json.dumps(payload),
            priority,
            parent_job_id,
            idempotency_key,
        )
        if row:
            job_id = int(row["id"])
            await query_conn.execute("SELECT pg_notify('pgqueuer', $1)", entrypoint)
            return job_id, True

        existing_id = await query_conn.fetchval(
            """
            SELECT id
            FROM pgqueuer_jobs
            WHERE entrypoint = $1
              AND idempotency_key = $2
              AND status IN ('queued', 'in_progress')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            entrypoint,
            idempotency_key,
        )
        if existing_id is None:
            raise RuntimeError(f"Unable to enqueue or locate duplicate job for '{entrypoint}'")
        return int(existing_id), False


async def enqueue_summarization_job(content_id: int) -> int | None:
    """Enqueue a content item for summarization.

    Implements idempotency: skips if the content_id is already
    queued or in_progress for summarization.

    Args:
        content_id: ID of the content to summarize

    Returns:
        Job ID if enqueued, None if already in queue
    """
    job_id, created = await enqueue_queue_job(
        "summarize_content",
        {"content_id": content_id},
    )
    if not created:
        logger.debug(f"Content {content_id} already in active queue (job {job_id})")
        return None
    logger.info(f"Enqueued summarization job {job_id} for content {content_id}")
    return job_id


async def enqueue_summarization_batch(
    content_ids: list[int],
    *,
    force: bool,
) -> tuple[int, int]:
    """Atomically enqueue parent batch and linked child jobs."""
    normalized_ids = list(dict.fromkeys(content_ids))
    parent_payload = _normalize_job_payload(
        {
            "content_ids": normalized_ids,
            "force": force,
            "requested_total": len(normalized_ids),
            "total": 0,
            "enqueued": 0,
            "completed": 0,
            "failed": 0,
            "message": "Queueing batch children",
        }
    )

    async with _queue_connection() as conn:
        async with conn.transaction():
            parent_id = await conn.fetchval(
                """
                INSERT INTO pgqueuer_jobs (
                    entrypoint, payload, status, created_at, execute_after, heartbeat_at
                )
                VALUES ('summarize_batch', $1::jsonb, 'in_progress', NOW(), NOW(), NOW())
                RETURNING id
                """,
                json.dumps(parent_payload),
            )
            assert parent_id is not None

            child_ids: list[int] = []
            duplicate_existing_ids: list[int] = []
            for content_id in normalized_ids:
                child_id, created = await enqueue_queue_job(
                    "summarize_content",
                    {"content_id": content_id},
                    parent_job_id=int(parent_id),
                    conn=conn,
                )
                if created:
                    child_ids.append(child_id)
                else:
                    duplicate_existing_ids.append(child_id)

            terminal_status = "in_progress"
            terminal_completed_at = None
            if not child_ids:
                terminal_status = "completed"
                terminal_completed_at = datetime.now(UTC)

            await conn.execute(
                """
                UPDATE pgqueuer_jobs
                SET payload = payload || $2::jsonb,
                    status = $3,
                    completed_at = $4,
                    heartbeat_at = NOW()
                WHERE id = $1
                """,
                int(parent_id),
                json.dumps(
                    {
                        "child_job_ids": child_ids,
                        "duplicate_existing_job_ids": duplicate_existing_ids,
                        "total": len(child_ids),
                        "enqueued": len(child_ids),
                        "message": (
                            "Batch complete: all work already active elsewhere"
                            if not child_ids
                            else f"Enqueued {len(child_ids)} child job(s)"
                        ),
                        "progress": 100 if not child_ids else 0,
                    }
                ),
                terminal_status,
                terminal_completed_at,
            )
        await conn.execute("SELECT pg_notify('pgqueuer', 'summarize_batch')")
        return int(parent_id), len(child_ids)


async def reconcile_batch_job_status(
    child_job_id: int,
    *,
    include_current_as_completed: bool = True,
) -> None:
    """Check and update batch job status after a child job completes.

    When a summarize_content job finishes, this function checks if it belongs
    to a summarize_batch parent job. If all child jobs are now complete,
    it marks the parent batch job as completed.

    This ensures batch jobs reach terminal state without requiring SSE polling.

    Args:
        child_job_id: The id of the just-completed child job
        include_current_as_completed: If True, count the current job as completed
            even if PGQueuer hasn't updated its status yet. Set to True when calling
            from within a task that's about to return successfully.
    """
    async with _queue_connection() as conn:
        batch_id = await conn.fetchval(
            """
            SELECT parent_job_id
            FROM pgqueuer_jobs
            WHERE id = $1
            """,
            child_job_id,
        )
        if batch_id is None:
            return

        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'completed')::int AS completed,
                COUNT(*) FILTER (WHERE status = 'failed')::int AS failed,
                COUNT(*)::int AS total
            FROM pgqueuer_jobs
            WHERE parent_job_id = $1
              AND entrypoint = 'summarize_content'
            """,
            int(batch_id),
        )
        if row is None:
            return

        completed = int(row["completed"] or 0)
        failed = int(row["failed"] or 0)
        total = int(row["total"] or 0)

        if include_current_as_completed:
            child_status = await conn.fetchval(
                """
                SELECT status
                FROM pgqueuer_jobs
                WHERE id = $1
                """,
                child_job_id,
            )
            if child_status == "in_progress":
                completed += 1

        processed = completed + failed
        progress = int((processed / total) * 100) if total > 0 else 100
        is_terminal = processed >= total

        await conn.execute(
            """
            UPDATE pgqueuer_jobs
            SET payload = COALESCE(payload, '{}'::jsonb) || $2::jsonb,
                status = CASE WHEN $3 THEN 'completed' ELSE status END,
                completed_at = CASE WHEN $3 THEN NOW() ELSE completed_at END,
                heartbeat_at = NOW()
            WHERE id = $1 AND status = 'in_progress'
            """,
            int(batch_id),
            json.dumps(
                {
                    "completed": completed,
                    "failed": failed,
                    "total": total,
                    "processed": processed,
                    "progress": progress,
                    "message": f"Processed {processed}/{total}",
                }
            ),
            is_terminal,
        )
        if is_terminal:
            logger.info(f"Batch job {batch_id} completed: {completed} succeeded, {failed} failed")


async def get_batch_child_counts(
    parent_job_id: int,
    *,
    conn: asyncpg.Connection | None = None,
) -> dict[str, int]:
    """Return summarize child status counts for a batch parent."""
    async with _queue_connection(conn) as query_conn:
        row = await query_conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'completed')::int AS completed,
                COUNT(*) FILTER (WHERE status = 'failed')::int AS failed,
                COUNT(*) FILTER (WHERE status = 'in_progress')::int AS in_progress,
                COUNT(*) FILTER (WHERE status = 'queued')::int AS queued,
                COUNT(*)::int AS total
            FROM pgqueuer_jobs
            WHERE parent_job_id = $1
              AND entrypoint = 'summarize_content'
            """,
            parent_job_id,
        )
        if row is None:
            return {"completed": 0, "failed": 0, "in_progress": 0, "queued": 0, "total": 0}
        return {
            "completed": int(row["completed"] or 0),
            "failed": int(row["failed"] or 0),
            "in_progress": int(row["in_progress"] or 0),
            "queued": int(row["queued"] or 0),
            "total": int(row["total"] or 0),
        }


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


async def get_queue_health_snapshot(
    *,
    stale_threshold_hours: int = DEFAULT_STALE_THRESHOLD_HOURS,
) -> dict[str, Any]:
    """Return queue reachability and worker activity snapshot."""
    async with _queue_connection() as conn:
        await conn.fetchval("SELECT 1")
        heartbeat_cutoff = datetime.now(UTC) - timedelta(hours=stale_threshold_hours)
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'queued')::int AS queued,
                COUNT(*) FILTER (WHERE status = 'in_progress')::int AS in_progress,
                COUNT(*) FILTER (
                    WHERE status = 'in_progress'
                      AND COALESCE(heartbeat_at, started_at, created_at) >= $1
                )::int AS active_workers
            FROM pgqueuer_jobs
            """,
            heartbeat_cutoff,
        )
        assert row is not None
        return {
            "queued": int(row["queued"] or 0),
            "in_progress": int(row["in_progress"] or 0),
            "active_workers": int(row["active_workers"] or 0),
        }
