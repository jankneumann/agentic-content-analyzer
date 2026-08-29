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

Legacy Job Payload Schema (version 1):
    {
        "content_id": int,      # ID of content being processed
        "progress": 0-100,      # Completion percentage
        "message": str          # Current status message
    }

Canonical operation submissions use schema version 2. Existing version-1
payloads remain unchanged so workers can drain them during the migration.
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
    "ingest_content": {"source"},  # max_results is optional (None = source config defaults)
    "execute_agent_task": {"task_id"},
}
REQUIRED_QUEUE_COLUMNS: set[str] = {
    "id",
    "entrypoint",
    "payload",
    "priority",
    "status",
    "created_at",
    "execute_after",
    "started_at",
    "completed_at",
    "heartbeat_at",
    "parent_job_id",
    "idempotency_key",
    "error",
    "retry_count",
    "claim_generation",
    "claim_protocol_version",
    "root_job_id",
    "submission_context",
    "submission_traceparent",
    "submission_tracestate",
    "trace_id",
    "submission_span_id",
}
REQUIRED_QUEUE_TABLES: set[str] = {
    "pgqueuer_jobs",
    "content_reconciliation_actions",
    "workflow_terminal_events",
    "workflow_alert_deliveries",
    "operation_observation_attempts",
    "telemetry_process_health",
    "environment_ownership",
}
REQUIRED_CORRELATION_COLUMNS: dict[str, set[str]] = {
    "audit_log": {
        "trace_id",
        "request_span_id",
        "submitted_operation_id",
        "service_name",
        "release_revision",
    },
    "workflow_terminal_events": {"trace_id"},
}
REQUIRED_QUEUE_TRIGGERS: set[tuple[str, str]] = {
    ("pgqueuer_jobs", "pgqueuer_jobs_capture_terminal_event"),
    (
        "content_reconciliation_actions",
        "content_reconciliation_actions_capture_terminal_event",
    ),
}

_WORKFLOW_ALERT_BOOTSTRAP_DDL = """
CREATE TABLE IF NOT EXISTS workflow_terminal_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_key VARCHAR(160) NOT NULL UNIQUE,
    source_kind VARCHAR(40) NOT NULL,
    operation_id BIGINT,
    claim_generation BIGINT,
    terminal_status VARCHAR(20),
    reconciliation_action_id BIGINT,
    reconciliation_run_id UUID,
    reconciliation_content_id BIGINT,
    classification_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    envelope JSONB,
    telemetry_emitted_at TIMESTAMPTZ,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_workflow_terminal_events_source_kind CHECK (
        source_kind IN ('operation','reconciliation_action','reconciliation_failure','system_check')
    ),
    CONSTRAINT ck_workflow_terminal_events_event_identity CHECK (
        (source_kind = 'operation' AND event_key =
          'operation:' || operation_id::text || ':claim:' ||
          claim_generation::text || ':status:' || terminal_status)
        OR
        (source_kind = 'reconciliation_action' AND event_key =
          'reconciliation-action:' || reconciliation_action_id::text)
        OR
        (source_kind = 'reconciliation_failure' AND event_key =
          'reconciliation-failure:' || reconciliation_run_id::text || ':content:' ||
          reconciliation_content_id::text || ':reason:apply_failed'
         AND event_key ~
          '^reconciliation-failure:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}:content:[1-9][0-9]*:reason:apply_failed$')
        OR
        (source_kind = 'system_check' AND event_key ~
          '^system_check:backup_freshness:[0-9]+$')
    ),
    CONSTRAINT ck_workflow_terminal_events_terminal_status CHECK (
        terminal_status IS NULL OR terminal_status IN ('completed','failed','cancelled')
    ),
    CONSTRAINT ck_workflow_terminal_events_classification_status CHECK (
        classification_status IN ('pending','ready','telemetry_only','rejected')
    ),
    CONSTRAINT ck_workflow_terminal_events_operation_id CHECK (
        operation_id IS NULL OR operation_id > 0
    ),
    CONSTRAINT ck_workflow_terminal_events_claim_generation CHECK (
        claim_generation IS NULL OR claim_generation >= 0
    ),
    CONSTRAINT ck_workflow_terminal_events_reconciliation_action_id CHECK (
        reconciliation_action_id IS NULL OR reconciliation_action_id > 0
    ),
    CONSTRAINT ck_workflow_terminal_events_reconciliation_content_id CHECK (
        reconciliation_content_id IS NULL OR reconciliation_content_id > 0
    ),
    CONSTRAINT ck_workflow_terminal_events_envelope_object CHECK (
        envelope IS NULL OR jsonb_typeof(envelope) = 'object'
    ),
    CONSTRAINT ck_workflow_terminal_events_source_shape CHECK (
        (source_kind = 'operation' AND operation_id IS NOT NULL
         AND claim_generation IS NOT NULL AND terminal_status IS NOT NULL
         AND reconciliation_action_id IS NULL AND reconciliation_run_id IS NULL
         AND reconciliation_content_id IS NULL)
        OR
        (source_kind = 'reconciliation_action' AND operation_id IS NULL
         AND claim_generation IS NULL AND terminal_status IS NULL
         AND reconciliation_action_id IS NOT NULL AND reconciliation_run_id IS NOT NULL
         AND reconciliation_content_id IS NOT NULL)
        OR
        (source_kind = 'reconciliation_failure' AND operation_id IS NULL
         AND claim_generation IS NULL AND terminal_status IS NULL
         AND reconciliation_action_id IS NULL AND reconciliation_run_id IS NOT NULL
         AND reconciliation_content_id IS NOT NULL)
        OR
        -- A system check reports on infrastructure, not on a workflow: no operation
        -- claim and no reconciliation identity. This arm is what makes the row
        -- insertable at all.
        (source_kind = 'system_check' AND operation_id IS NULL
         AND claim_generation IS NULL AND terminal_status IS NULL
         AND reconciliation_action_id IS NULL AND reconciliation_run_id IS NULL
         AND reconciliation_content_id IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS workflow_alert_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL,
    sink_name VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_expires_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    last_error_code VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_workflow_alert_deliveries_event
        FOREIGN KEY (event_id) REFERENCES workflow_terminal_events(id) ON DELETE RESTRICT,
    CONSTRAINT uq_workflow_alert_deliveries_event_sink UNIQUE (event_id, sink_name),
    CONSTRAINT ck_workflow_alert_deliveries_sink_name CHECK (
        sink_name ~ '^[a-z][a-z0-9_-]{0,63}$'
    ),
    CONSTRAINT ck_workflow_alert_deliveries_status CHECK (
        status IN ('pending','leased','delivered','permanent_failure','exhausted')
    ),
    CONSTRAINT ck_workflow_alert_deliveries_attempt_count CHECK (attempt_count >= 0),
    CONSTRAINT ck_workflow_alert_deliveries_last_error_code CHECK (
        last_error_code IS NULL OR last_error_code ~ '^[a-z][a-z0-9_.-]{0,79}$'
    ),
    CONSTRAINT ck_workflow_alert_deliveries_state CHECK (
        (status = 'pending'
         AND lease_expires_at IS NULL AND delivered_at IS NULL)
        OR
        (status = 'leased' AND attempt_count >= 1
         AND lease_expires_at IS NOT NULL AND delivered_at IS NULL)
        OR
        (status = 'delivered' AND attempt_count >= 1
         AND lease_expires_at IS NULL AND delivered_at IS NOT NULL
         AND last_error_code IS NULL)
        OR
        (status IN ('permanent_failure','exhausted') AND attempt_count >= 1
         AND lease_expires_at IS NULL AND delivered_at IS NULL
         AND last_error_code IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS ix_workflow_terminal_events_classification_due
    ON workflow_terminal_events (created_at, id)
    WHERE classification_status = 'pending';
CREATE INDEX IF NOT EXISTS ix_workflow_terminal_events_retention
    ON workflow_terminal_events (created_at, id)
    WHERE classification_status IN ('ready','telemetry_only','rejected');
CREATE INDEX IF NOT EXISTS ix_workflow_alert_deliveries_pending_due
    ON workflow_alert_deliveries (next_attempt_at, id)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS ix_workflow_alert_deliveries_lease_expiry
    ON workflow_alert_deliveries (lease_expires_at, id)
    WHERE status = 'leased';
CREATE INDEX IF NOT EXISTS ix_workflow_alert_deliveries_retention
    ON workflow_alert_deliveries (updated_at, id)
    WHERE status IN ('delivered','permanent_failure','exhausted');

CREATE OR REPLACE FUNCTION capture_pgqueuer_terminal_event()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    terminal_event_key TEXT;
    captured_event_id UUID;
BEGIN
    terminal_event_key := format(
        'operation:%s:claim:%s:status:%s',
        NEW.id,
        NEW.claim_generation,
        NEW.status
    );
    INSERT INTO workflow_terminal_events (
        event_key, source_kind, operation_id, claim_generation,
        terminal_status, occurred_at
    ) VALUES (
        terminal_event_key, 'operation', NEW.id, NEW.claim_generation,
        NEW.status, COALESCE(NEW.completed_at, NOW())
    ) ON CONFLICT (event_key) DO UPDATE
    SET event_key = EXCLUDED.event_key
    WHERE workflow_terminal_events.source_kind = EXCLUDED.source_kind
      AND workflow_terminal_events.operation_id = EXCLUDED.operation_id
      AND workflow_terminal_events.claim_generation = EXCLUDED.claim_generation
      AND workflow_terminal_events.terminal_status = EXCLUDED.terminal_status
    RETURNING id INTO captured_event_id;
    IF captured_event_id IS NULL THEN
        RAISE EXCEPTION 'workflow terminal event identity collision'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS pgqueuer_jobs_capture_terminal_event ON pgqueuer_jobs;
CREATE TRIGGER pgqueuer_jobs_capture_terminal_event
AFTER UPDATE OF status ON pgqueuer_jobs
FOR EACH ROW
WHEN (
    OLD.status IS DISTINCT FROM NEW.status
    AND NEW.status IN ('completed','failed','cancelled')
)
EXECUTE FUNCTION capture_pgqueuer_terminal_event();

CREATE OR REPLACE FUNCTION capture_content_reconciliation_terminal_event()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    captured_event_id UUID;
BEGIN
    INSERT INTO workflow_terminal_events (
        event_key, source_kind, reconciliation_action_id,
        reconciliation_run_id, reconciliation_content_id, occurred_at
    ) VALUES (
        format('reconciliation-action:%s', NEW.id), 'reconciliation_action',
        NEW.id, NEW.run_id, NEW.content_id, NEW.created_at
    ) ON CONFLICT (event_key) DO UPDATE
    SET event_key = EXCLUDED.event_key
    WHERE workflow_terminal_events.source_kind = EXCLUDED.source_kind
      AND workflow_terminal_events.reconciliation_action_id =
          EXCLUDED.reconciliation_action_id
      AND workflow_terminal_events.reconciliation_run_id =
          EXCLUDED.reconciliation_run_id
      AND workflow_terminal_events.reconciliation_content_id =
          EXCLUDED.reconciliation_content_id
    RETURNING id INTO captured_event_id;
    IF captured_event_id IS NULL THEN
        RAISE EXCEPTION 'workflow terminal event identity collision'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DO $$
BEGIN
    IF to_regclass('public.content_reconciliation_actions') IS NULL THEN
        RAISE EXCEPTION
            'workflow alert bootstrap requires content_reconciliation_actions; run migrations';
    END IF;
    EXECUTE 'DROP TRIGGER IF EXISTS content_reconciliation_actions_capture_terminal_event '
            'ON content_reconciliation_actions';
    EXECUTE 'CREATE TRIGGER content_reconciliation_actions_capture_terminal_event '
            'AFTER INSERT ON content_reconciliation_actions FOR EACH ROW '
            'EXECUTE FUNCTION capture_content_reconciliation_terminal_event()';
END;
$$;

CREATE OR REPLACE FUNCTION deny_workflow_terminal_event_identity_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF ROW(
        NEW.id, NEW.event_key, NEW.source_kind, NEW.operation_id,
        NEW.claim_generation, NEW.terminal_status, NEW.reconciliation_action_id,
        NEW.reconciliation_run_id, NEW.reconciliation_content_id,
        NEW.occurred_at, NEW.created_at
    ) IS DISTINCT FROM ROW(
        OLD.id, OLD.event_key, OLD.source_kind, OLD.operation_id,
        OLD.claim_generation, OLD.terminal_status, OLD.reconciliation_action_id,
        OLD.reconciliation_run_id, OLD.reconciliation_content_id,
        OLD.occurred_at, OLD.created_at
    ) THEN
        RAISE EXCEPTION 'workflow_terminal_events source identity is immutable'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS workflow_terminal_events_source_identity_immutable
    ON workflow_terminal_events;
CREATE TRIGGER workflow_terminal_events_source_identity_immutable
BEFORE UPDATE ON workflow_terminal_events
FOR EACH ROW EXECUTE FUNCTION deny_workflow_terminal_event_identity_mutation();
"""


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


async def ensure_queue_schema_compatible() -> None:
    """Fail fast if required queue schema migrations are missing."""
    async with _queue_connection() as conn:
        table_rows = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name = ANY($1::text[])
            """,
            sorted(REQUIRED_QUEUE_TABLES),
        )
        actual_tables = {str(row["table_name"]) for row in table_rows}
        missing_tables = sorted(REQUIRED_QUEUE_TABLES - actual_tables)
        if missing_tables:
            raise RuntimeError(
                "Queue schema is outdated. Missing required tables: "
                f"{', '.join(missing_tables)}. Run migrations first."
            )

        rows = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'pgqueuer_jobs'
            """
        )
        actual = {str(row["column_name"]) for row in rows}
        missing = sorted(REQUIRED_QUEUE_COLUMNS - actual)
        if missing:
            missing_csv = ", ".join(missing)
            raise RuntimeError(
                "Queue schema is outdated. Missing columns in 'pgqueuer_jobs': "
                f"{missing_csv}. Run migrations first."
            )

        for table_name, required_columns in REQUIRED_CORRELATION_COLUMNS.items():
            rows = await conn.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = $1
                """,
                table_name,
            )
            actual_columns = {str(row["column_name"]) for row in rows}
            missing_columns = sorted(required_columns - actual_columns)
            if missing_columns:
                missing_csv = ", ".join(missing_columns)
                raise RuntimeError(
                    "Queue schema is outdated. Missing columns in "
                    f"'{table_name}': {missing_csv}. Run migrations first."
                )

        trigger_rows = await conn.fetch(
            """
            SELECT relation.relname AS table_name, trigger.tgname AS trigger_name
            FROM pg_trigger AS trigger
            JOIN pg_class AS relation ON relation.oid = trigger.tgrelid
            JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
            WHERE NOT trigger.tgisinternal
              AND namespace.nspname = current_schema()
              AND (relation.relname, trigger.tgname) IN (
                ('pgqueuer_jobs', 'pgqueuer_jobs_capture_terminal_event'),
                ('content_reconciliation_actions',
                 'content_reconciliation_actions_capture_terminal_event')
              )
            """
        )
        actual_triggers = {
            (str(row["table_name"]), str(row["trigger_name"])) for row in trigger_rows
        }
        missing_triggers = sorted(REQUIRED_QUEUE_TRIGGERS - actual_triggers)
        if missing_triggers:
            missing_csv = ", ".join(trigger_name for _table, trigger_name in missing_triggers)
            raise RuntimeError(
                "Queue schema is outdated. Missing required terminal triggers: "
                f"{missing_csv}. Run migrations first."
            )


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
                retry_count INTEGER DEFAULT 0,
                claim_generation BIGINT NOT NULL DEFAULT 0,
                claim_protocol_version SMALLINT NOT NULL DEFAULT 1,
                CONSTRAINT ck_pgqueuer_jobs_claim_generation_nonnegative
                    CHECK (claim_generation >= 0),
                CONSTRAINT ck_pgqueuer_jobs_claim_protocol_positive
                    CHECK (claim_protocol_version >= 1)
            );

            ALTER TABLE pgqueuer_jobs
                ADD COLUMN IF NOT EXISTS claim_generation BIGINT NOT NULL DEFAULT 0,
                ADD COLUMN IF NOT EXISTS claim_protocol_version SMALLINT NOT NULL DEFAULT 1;

            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'ck_pgqueuer_jobs_claim_generation_nonnegative'
                      AND conrelid = 'pgqueuer_jobs'::regclass
                ) THEN
                    ALTER TABLE pgqueuer_jobs
                        ADD CONSTRAINT ck_pgqueuer_jobs_claim_generation_nonnegative
                        CHECK (claim_generation >= 0);
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'ck_pgqueuer_jobs_claim_protocol_positive'
                      AND conrelid = 'pgqueuer_jobs'::regclass
                ) THEN
                    ALTER TABLE pgqueuer_jobs
                        ADD CONSTRAINT ck_pgqueuer_jobs_claim_protocol_positive
                        CHECK (claim_protocol_version >= 1);
                END IF;
            END;
            $$;

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

            CREATE OR REPLACE FUNCTION advance_pgqueuer_claim_generation()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                NEW.claim_generation := OLD.claim_generation + 1;
                RETURN NEW;
            END;
            $$;

            DROP TRIGGER IF EXISTS pgqueuer_jobs_advance_claim_generation ON pgqueuer_jobs;
            CREATE TRIGGER pgqueuer_jobs_advance_claim_generation
            BEFORE UPDATE OF status ON pgqueuer_jobs
            FOR EACH ROW
            WHEN (OLD.status = 'queued' AND NEW.status = 'in_progress')
            EXECUTE FUNCTION advance_pgqueuer_claim_generation();

            CREATE OR REPLACE FUNCTION reset_pgqueuer_claim_protocol()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                NEW.claim_protocol_version := 1;
                RETURN NEW;
            END;
            $$;

            DROP TRIGGER IF EXISTS pgqueuer_jobs_reset_claim_protocol ON pgqueuer_jobs;
            CREATE TRIGGER pgqueuer_jobs_reset_claim_protocol
            BEFORE UPDATE OF status ON pgqueuer_jobs
            FOR EACH ROW
            WHEN (OLD.status IS DISTINCT FROM 'queued' AND NEW.status = 'queued')
            EXECUTE FUNCTION reset_pgqueuer_claim_protocol();
        """)

        await conn.execute(_WORKFLOW_ALERT_BOOTSTRAP_DDL)

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


async def _fetch_job_row(conn: asyncpg.Connection, job_id: int) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        SELECT
            id,
            entrypoint,
            status,
            payload,
            priority,
            error,
            retry_count,
            claim_generation,
            claim_protocol_version,
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
        row = await _fetch_job_row(query_conn, job_id)

        if row is None:
            return None

        # A failed child never reaches the legacy worker's success callback.
        # Reconcile on reads too so a fully terminal batch cannot remain stuck.
        if row["entrypoint"] == "summarize_batch" and row["status"] == "in_progress":
            await _reconcile_batch_parent_status(query_conn, job_id)
            row = await _fetch_job_row(query_conn, job_id)
            if row is None:
                return None

        # Parse payload from JSONB
        payload = row["payload"] if row["payload"] else {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        parent_job_id = row.get("parent_job_id", None)
        heartbeat_at = row.get("heartbeat_at", None)
        claim_generation = row.get("claim_generation", 0)
        claim_protocol_version = row.get("claim_protocol_version", 1)

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
            claim_generation=claim_generation,
            claim_protocol_version=claim_protocol_version,
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
    claim_generation: int | None = None,
) -> bool:
    """Update job progress in the payload.

    Merges progress and message into the existing payload JSON,
    and refreshes updated_at timestamp for stale job detection.

    Args:
        job_id: The job ID to update
        progress: Completion percentage (0-100)
        message: Current status message
    """
    if claim_generation is None:
        from src.queue.execution_claim import claim_generation_for

        claim_generation = claim_generation_for(job_id)
    if claim_generation is None:
        return False

    async with _queue_connection(conn) as query_conn:
        # Merge progress into existing payload
        progress_data = json.dumps({"progress": progress, "message": message})
        updated_id = await query_conn.fetchval(
            """
            UPDATE pgqueuer_jobs
            SET payload = COALESCE(payload, '{}'::jsonb) || $1::jsonb
              , heartbeat_at = NOW()
            WHERE id = $2
              AND status = 'in_progress'
              AND claim_generation = $3
            RETURNING id
            """,
            progress_data,
            job_id,
            claim_generation,
        )
        if updated_id is not None:
            logger.debug(f"Updated job {job_id} progress: {progress}% - {message}")
        return updated_id is not None


async def touch_job_heartbeat(
    job_id: int,
    *,
    conn: asyncpg.Connection | None = None,
    claim_generation: int | None = None,
) -> bool:
    if claim_generation is None:
        from src.queue.execution_claim import claim_generation_for

        claim_generation = claim_generation_for(job_id)
    if claim_generation is None:
        return False

    async with _queue_connection(conn) as query_conn:
        updated_id = await query_conn.fetchval(
            """
            UPDATE pgqueuer_jobs
            SET heartbeat_at = NOW()
            WHERE id = $1
              AND status = 'in_progress'
              AND claim_generation = $2
            RETURNING id
            """,
            job_id,
            claim_generation,
        )
        return updated_id is not None


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
                payload = COALESCE(payload, '{}'::jsonb) ||
                    '{
                        "progress": 0,
                        "message": "Queued",
                        "cancel_requested": false,
                        "resource": null,
                        "result": null,
                        "problem": null
                    }'::jsonb,
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


_OPERATION_GRAPH_LOCK_SQL = (
    "SELECT pg_advisory_xact_lock("
    "hashtextextended('aca:operation-graph:' || ($1::bigint)::text, 0))"
)


async def _resolve_operation_graph_root(
    conn: asyncpg.Connection,
    job_id: int,
) -> int | None:
    """Resolve a live job's root while rejecting broken or cyclic lineage."""

    root_id = await conn.fetchval(
        """
        WITH RECURSIVE lineage AS (
            SELECT job.id, job.parent_job_id, ARRAY[job.id] AS visited
            FROM pgqueuer_jobs AS job
            WHERE job.id = $1
            UNION ALL
            SELECT parent.id,
                   parent.parent_job_id,
                   lineage.visited || parent.id
            FROM pgqueuer_jobs AS parent
            JOIN lineage ON parent.id = lineage.parent_job_id
            WHERE NOT parent.id = ANY(lineage.visited)
        )
        SELECT id
        FROM lineage
        WHERE parent_job_id IS NULL
        LIMIT 1
        """,
        job_id,
    )
    return int(root_id) if root_id is not None else None


async def _acquire_operation_graph_lock(
    conn: asyncpg.Connection,
    root_id: int,
) -> None:
    """Serialize graph membership changes and retention for one root."""

    await conn.fetchval(_OPERATION_GRAPH_LOCK_SQL, root_id)


async def cleanup_old_jobs(
    older_than_days: int = 30,
    *,
    failed_older_than_days: int = 90,
    batch_size: int = 100,
    conn: asyncpg.Connection | None = None,
) -> int:
    """Delete a bounded batch of fully terminal operation graphs.

    Candidate roots are selected by the graph's newest completion timestamp.
    The selected graphs are locked and re-read in the same transaction before
    descendants are removed ahead of roots, so active or newly retried work is
    never detached by ``ON DELETE SET NULL``.
    """

    if not 1 <= older_than_days <= 3650:
        raise ValueError("older_than_days must be between 1 and 3650")
    if not older_than_days <= failed_older_than_days <= 3650:
        raise ValueError("failed_older_than_days must be between older_than_days and 3650")
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be between 1 and 1000")

    candidate_sql = """
        WITH RECURSIVE graph AS (
            SELECT root.id, root.id AS root_id, root.status, root.completed_at
            FROM pgqueuer_jobs AS root
            WHERE root.parent_job_id IS NULL
            UNION ALL
            SELECT child.id, graph.root_id, child.status, child.completed_at
            FROM pgqueuer_jobs AS child
            JOIN graph ON child.parent_job_id = graph.id
        ),
        rollup AS (
            SELECT root_id,
                   MAX(completed_at) AS newest_completion,
                   BOOL_OR(status = 'failed') AS has_failed,
                   COUNT(*) FILTER (
                       WHERE status NOT IN ('completed', 'failed', 'cancelled')
                   ) AS active_count,
                   COUNT(*) FILTER (WHERE completed_at IS NULL) AS null_completion_count
            FROM graph
            GROUP BY root_id
        )
        SELECT root_id
        FROM rollup
        WHERE active_count = 0
          AND null_completion_count = 0
          AND CASE
              WHEN has_failed
                  THEN newest_completion < CURRENT_TIMESTAMP
                       - ($2::int * INTERVAL '1 day')
              ELSE newest_completion < CURRENT_TIMESTAMP
                       - ($1::int * INTERVAL '1 day')
          END
        ORDER BY newest_completion, root_id
        LIMIT $3
    """
    graph_lock_sql = """
        WITH RECURSIVE graph_ids AS (
            SELECT root.id
            FROM pgqueuer_jobs AS root
            WHERE root.id = ANY($1::bigint[])
            UNION ALL
            SELECT child.id
            FROM pgqueuer_jobs AS child
            JOIN graph_ids ON child.parent_job_id = graph_ids.id
        )
        SELECT jobs.id
        FROM pgqueuer_jobs AS jobs
        JOIN graph_ids ON graph_ids.id = jobs.id
        ORDER BY jobs.id
        FOR UPDATE OF jobs
    """
    recheck_sql = """
        WITH RECURSIVE graph AS (
            SELECT root.id, root.id AS root_id, root.status, root.completed_at
            FROM pgqueuer_jobs AS root
            WHERE root.id = ANY($1::bigint[])
              AND root.parent_job_id IS NULL
            UNION ALL
            SELECT child.id, graph.root_id, child.status, child.completed_at
            FROM pgqueuer_jobs AS child
            JOIN graph ON child.parent_job_id = graph.id
        )
        SELECT root_id
        FROM graph
        GROUP BY root_id
        HAVING COUNT(*) FILTER (
                   WHERE status NOT IN ('completed', 'failed', 'cancelled')
               ) = 0
           AND COUNT(*) FILTER (WHERE completed_at IS NULL) = 0
           AND CASE
               WHEN BOOL_OR(status = 'failed')
                   THEN MAX(completed_at) < CURRENT_TIMESTAMP
                        - ($3::int * INTERVAL '1 day')
               ELSE MAX(completed_at) < CURRENT_TIMESTAMP
                        - ($2::int * INTERVAL '1 day')
           END
        ORDER BY root_id
    """
    delete_descendants_sql = """
        WITH RECURSIVE graph_ids AS (
            SELECT root.id, root.id AS root_id
            FROM pgqueuer_jobs AS root
            WHERE root.id = ANY($1::bigint[])
            UNION ALL
            SELECT child.id, graph_ids.root_id
            FROM pgqueuer_jobs AS child
            JOIN graph_ids ON child.parent_job_id = graph_ids.id
        )
        DELETE FROM pgqueuer_jobs AS jobs
        USING graph_ids
        WHERE jobs.id = graph_ids.id
          AND jobs.id <> graph_ids.root_id
        RETURNING jobs.id
    """

    async with _queue_connection(conn) as query_conn, query_conn.transaction():
        await query_conn.execute("SET LOCAL lock_timeout = '5s'")
        await query_conn.execute("SET LOCAL statement_timeout = '30s'")
        candidates = await query_conn.fetch(
            candidate_sql,
            older_than_days,
            failed_older_than_days,
            batch_size,
        )
        root_ids = sorted(int(row["root_id"]) for row in candidates)
        if not root_ids:
            return 0

        # Child insertion takes the same root-scoped transaction lock. Once
        # these locks are held, graph membership is stable through recheck and
        # deletion. Sorted acquisition prevents cleanup workers deadlocking.
        for root_id in root_ids:
            await _acquire_operation_graph_lock(query_conn, root_id)

        # Retain one row-lock pass so lifecycle mutations cannot race the
        # terminal-state recheck. Membership no longer relies on repeated
        # recursive snapshots because the advisory lock owns that invariant.
        await query_conn.fetch(graph_lock_sql, root_ids)
        rechecked = await query_conn.fetch(
            recheck_sql,
            root_ids,
            older_than_days,
            failed_older_than_days,
        )
        eligible_root_ids = [int(row["root_id"]) for row in rechecked]
        if not eligible_root_ids:
            return 0

        descendants = await query_conn.fetch(
            delete_descendants_sql,
            eligible_root_ids,
        )
        roots = await query_conn.fetch(
            """
                DELETE FROM pgqueuer_jobs
                WHERE id = ANY($1::bigint[])
                  AND parent_job_id IS NULL
                RETURNING id
                """,
            eligible_root_ids,
        )

    deleted_count = len(descendants) + len(roots)
    logger.info(
        "operation retention deleted %s jobs across %s root graphs",
        deleted_count,
        len(roots),
    )
    return deleted_count


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
    idempotency_key: str | None = None,
) -> tuple[int, bool]:
    """Enqueue with versioned payload and active-job idempotency.

    Legacy callers omit ``idempotency_key`` and retain their established
    entrypoint-specific key derivation. Canonical operation callers supply a
    key derived from normalized input or the external Idempotency-Key header.
    """
    _validate_payload(entrypoint, payload)
    payload = _normalize_job_payload(payload)
    effective_idempotency_key = idempotency_key or _build_idempotency_key(entrypoint, payload)

    async with _queue_connection(conn) as query_conn, query_conn.transaction():
        if parent_job_id is not None:
            root_id = await _resolve_operation_graph_root(query_conn, parent_job_id)
            if root_id is None:
                raise RuntimeError("Parent job does not belong to a live operation graph")
            await _acquire_operation_graph_lock(query_conn, root_id)
            confirmed_root_id = await _resolve_operation_graph_root(query_conn, parent_job_id)
            if confirmed_root_id != root_id:
                raise RuntimeError("Parent job does not belong to a live operation graph")

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
            effective_idempotency_key,
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
            effective_idempotency_key,
        )
        if existing_id is None:
            raise RuntimeError(f"Unable to enqueue or locate duplicate job for '{entrypoint}'")
        return int(existing_id), False


async def get_child_job_by_idempotency_key(
    parent_job_id: int,
    entrypoint: str,
    idempotency_key: str,
    *,
    conn: asyncpg.Connection | None = None,
) -> JobRecord | None:
    """Find a parent-owned child in any lifecycle state for durable resume."""

    async with _queue_connection(conn) as query_conn:
        job_id = await query_conn.fetchval(
            """
            SELECT id
            FROM pgqueuer_jobs
            WHERE parent_job_id = $1
              AND entrypoint = $2
              AND idempotency_key = $3
            ORDER BY id ASC
            LIMIT 1
            """,
            parent_job_id,
            entrypoint,
            idempotency_key,
        )
        if job_id is None:
            return None
        return await get_job_status(int(job_id), conn=query_conn)


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

        await _reconcile_batch_parent_status(
            conn,
            int(batch_id),
            current_child_id=child_job_id,
            include_current_as_completed=include_current_as_completed,
        )


async def _reconcile_batch_parent_status(
    conn: asyncpg.Connection,
    parent_job_id: int,
    *,
    current_child_id: int | None = None,
    include_current_as_completed: bool = False,
) -> None:
    """Persist aggregate state once all summarize children are terminal."""

    row = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'completed')::int AS completed,
            COUNT(*) FILTER (WHERE status = 'failed')::int AS failed,
            COUNT(*) FILTER (WHERE status = 'cancelled')::int AS cancelled,
            COUNT(*)::int AS total,
            (
                SELECT parent.claim_generation
                FROM pgqueuer_jobs AS parent
                WHERE parent.id = $1 AND parent.status = 'in_progress'
            ) AS parent_claim_generation
        FROM pgqueuer_jobs
        WHERE parent_job_id = $1
          AND entrypoint = 'summarize_content'
        """,
        parent_job_id,
    )
    if row is None:
        return
    parent_claim_generation = row.get("parent_claim_generation")
    if parent_claim_generation is None:
        return

    completed = int(row["completed"] or 0)
    failed = int(row["failed"] or 0)
    cancelled = int(row["cancelled"] or 0)
    total = int(row["total"] or 0)

    if include_current_as_completed and current_child_id is not None:
        child_status = await conn.fetchval(
            """
            SELECT status
            FROM pgqueuer_jobs
            WHERE id = $1
            """,
            current_child_id,
        )
        if child_status == "in_progress":
            completed += 1

    processed = completed + failed + cancelled
    progress = int((processed / total) * 100) if total > 0 else 100
    is_terminal = total > 0 and processed >= total

    await conn.execute(
        """
        UPDATE pgqueuer_jobs
        SET payload = COALESCE(payload, '{}'::jsonb) || $2::jsonb,
            status = CASE
                WHEN $3
                    AND payload->>'operation_type' = 'summarization.run'
                    AND payload->'result'->'child_operation_ids' IS NOT NULL
                THEN 'queued'
                WHEN $3 AND payload->>'operation_type' = 'summarization.run' THEN status
                WHEN $3 THEN 'completed'
                ELSE status
            END,
            execute_after = CASE
                WHEN $3
                    AND payload->>'operation_type' = 'summarization.run'
                    AND payload->'result'->'child_operation_ids' IS NOT NULL
                THEN NOW()
                ELSE execute_after
            END,
            started_at = CASE
                WHEN $3
                    AND payload->>'operation_type' = 'summarization.run'
                    AND payload->'result'->'child_operation_ids' IS NOT NULL
                THEN NULL
                ELSE started_at
            END,
            completed_at = CASE
                WHEN $3 AND payload->>'operation_type' = 'summarization.run' THEN NULL
                WHEN $3 THEN NOW()
                ELSE completed_at
            END,
            heartbeat_at = NOW()
        WHERE id = $1
          AND status = 'in_progress'
          AND claim_generation = $4
        """,
        parent_job_id,
        json.dumps(
            {
                "completed": completed,
                "failed": failed,
                "cancelled": cancelled,
                "total": total,
                "processed": processed,
                "progress": progress,
                "message": f"Processed {processed}/{total}",
            }
        ),
        is_terminal,
        int(parent_claim_generation),
    )
    if is_terminal:
        logger.info(
            f"Batch job {parent_job_id} children terminal: {completed} succeeded, "
            f"{failed} failed, {cancelled} cancelled"
        )


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
