"""Embedded queue worker that processes jobs from pgqueuer_jobs table.

Uses SELECT FOR UPDATE SKIP LOCKED to claim jobs from our custom
pgqueuer_jobs table and dispatch them to registered task handlers.

This is a lightweight alternative to PGQueuer's run() which expects
its own native schema. Our custom table has additional features like
progress tracking and batch reconciliation.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import secrets
import socket
from collections.abc import Awaitable, Callable, Coroutine, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any, Literal

import asyncpg

from src.storage.database import get_queue_connection_string
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TelemetryLifecycle:
    """One bounded telemetry lifecycle shared by every long/short-lived process."""

    def __init__(
        self,
        *,
        settings: Any,
        service_name: str,
        lifecycle_kind: Literal["long_running", "short_lived"],
        service_instance_id: str | None = None,
    ) -> None:
        self.settings = settings
        self.service_name = service_name[:100]
        self.lifecycle_kind = lifecycle_kind
        configured_instance = getattr(settings, "telemetry_service_instance_id", None)
        self.service_instance_id = (
            service_instance_id
            or configured_instance
            or os.environ.get("ACA_SERVICE_INSTANCE_ID")
            or f"{socket.gethostname()}-{os.getpid()}-{secrets.token_hex(4)}"
        )[:128]
        self.release_revision = (
            getattr(settings, "telemetry_release_revision", None)
            or os.environ.get("RELEASE_REVISION")
            or os.environ.get("RAILWAY_GIT_COMMIT_SHA")
            or "unknown"
        )[:64]
        self.required = bool(getattr(settings, "observability_required", False))
        self.initialized = False
        self.status: Literal["healthy", "degraded", "disabled", "stale"] = "disabled"
        self.last_success_at: datetime | None = None
        self.last_error_at: datetime | None = None
        self.last_error_code: str | None = None
        self.buffered_count = 0
        self.buffered_bytes = 0
        self.buffer_capacity = min(
            int(getattr(settings, "telemetry_buffer_capacity", 10_000)), 10_000
        )
        self.buffer_capacity_bytes = min(
            int(getattr(settings, "telemetry_buffer_capacity_bytes", 268_435_456)),
            268_435_456,
        )
        self.dropped_count = 0
        self.last_flush_at: datetime | None = None
        self.last_flush_succeeded: bool | None = None

    @property
    def export_target(self) -> Literal["local_langfuse", "remote_langfuse", "other_otlp", "none"]:
        provider = str(getattr(self.settings, "observability_provider", "noop"))
        if provider == "langfuse":
            base_url = str(getattr(self.settings, "langfuse_base_url", ""))
            return (
                "local_langfuse"
                if "localhost" in base_url or "127.0.0.1" in base_url
                else "remote_langfuse"
            )
        if getattr(self.settings, "otel_exporter_otlp_endpoint", None):
            return "other_otlp"
        return "none"

    def initialize(
        self,
        *,
        app: Any | None = None,
        setup: Callable[[Any | None], None] | None = None,
    ) -> None:
        """Initialize before instrumented clients and enforce required readiness."""

        provider = str(getattr(self.settings, "observability_provider", "noop"))
        if self.required and (provider == "noop" or self.export_target == "none"):
            self.status = "degraded"
            self.last_error_at = datetime.now(UTC)
            self.last_error_code = "telemetry.required_configuration_missing"
            raise RuntimeError("required observability has no configured export target")
        if setup is None:
            from src.telemetry import setup_telemetry

            setup = setup_telemetry
        setup(app)
        self.initialized = True
        self.status = "disabled" if self.export_target == "none" else "healthy"

    def record_buffered(self, count: int, *, buffered_bytes: int = 0) -> None:
        """Apply the bounded process buffer and expose deterministic overflow."""

        if count < 0 or buffered_bytes < 0:
            raise ValueError("buffered count and bytes must be non-negative")
        accepted = min(count, self.buffer_capacity)
        accepted_bytes = min(buffered_bytes, self.buffer_capacity_bytes)
        self.buffered_count = accepted
        self.buffered_bytes = accepted_bytes
        overflow = count - accepted
        byte_overflow = buffered_bytes - accepted_bytes
        if byte_overflow and not overflow:
            overflow = 1
        if overflow:
            self.dropped_count += overflow
            self.status = "degraded"
            self.last_error_at = datetime.now(UTC)
            self.last_error_code = "telemetry.buffer_overflow"

    def record_export_success(self, *, buffered_count: int = 0, buffered_bytes: int = 0) -> None:
        self.buffered_count = min(max(buffered_count, 0), self.buffer_capacity)
        self.buffered_bytes = min(max(buffered_bytes, 0), self.buffer_capacity_bytes)
        self.last_success_at = datetime.now(UTC)
        self.last_error_code = None
        self.status = "healthy"

    def record_export_failure(self, error_code: str) -> None:
        self.last_error_at = datetime.now(UTC)
        self.last_error_code = error_code[:80]
        self.status = "degraded"

    async def heartbeat(self, conn: Any) -> Any:
        from src.repositories.telemetry_process_health import (
            ProcessHealthHeartbeat,
            upsert_process_health,
        )

        return await upsert_process_health(
            conn,
            ProcessHealthHeartbeat(
                environment=str(self.settings.environment),
                service_name=self.service_name,
                service_instance_id=self.service_instance_id,
                release_revision=self.release_revision,
                lifecycle_kind=self.lifecycle_kind,
                required_observability=self.required,
                initialized=self.initialized,
                status=self.status,
                export_target=self.export_target,
                last_heartbeat_at=datetime.now(UTC),
                last_success_at=self.last_success_at,
                last_error_at=self.last_error_at,
                last_error_code=self.last_error_code,
                buffered_count=self.buffered_count,
                buffer_capacity=self.buffer_capacity,
                dropped_count=self.dropped_count,
                last_flush_at=self.last_flush_at,
                last_flush_succeeded=self.last_flush_succeeded,
            ),
        )

    async def shutdown(
        self,
        conn: Any | None,
        *,
        flush: Callable[[], Awaitable[None]] | None = None,
    ) -> bool:
        """Bound shutdown flush and persist terminal evidence when possible."""

        if flush is None:
            from src.telemetry import shutdown_telemetry

            async def flush() -> None:
                await asyncio.to_thread(shutdown_telemetry)

        succeeded = True
        try:
            await asyncio.wait_for(
                flush(),
                timeout=float(getattr(self.settings, "telemetry_flush_timeout_seconds", 5.0)),
            )
        except (TimeoutError, Exception):
            succeeded = False
            self.record_export_failure("telemetry.flush_failed")
        self.last_flush_at = datetime.now(UTC)
        self.last_flush_succeeded = succeeded
        if conn is not None:
            await self.heartbeat(conn)
        return succeeded


def create_telemetry_lifecycle(
    *, service_name: str, lifecycle_kind: Literal["long_running", "short_lived"]
) -> TelemetryLifecycle:
    from src.config.settings import get_settings

    return TelemetryLifecycle(
        settings=get_settings(), service_name=service_name, lifecycle_kind=lifecycle_kind
    )


async def run_telemetry_heartbeat(lifecycle: TelemetryLifecycle) -> None:
    """Persist bounded process health until the owning process cancels the task."""

    from src.queue.setup import _queue_connection

    interval = float(getattr(lifecycle.settings, "telemetry_heartbeat_interval_seconds", 30))
    while True:
        try:
            async with _queue_connection() as conn:
                await lifecycle.heartbeat(conn)
        except asyncio.CancelledError:
            raise
        except Exception:
            lifecycle.record_export_failure("telemetry.health_write_failed")
            logger.warning("Telemetry process-health heartbeat failed", exc_info=True)
        await asyncio.sleep(interval)


async def shutdown_process_telemetry(lifecycle: TelemetryLifecycle) -> bool:
    from src.queue.setup import _queue_connection

    try:
        async with _queue_connection() as conn:
            return await lifecycle.shutdown(conn)
    except Exception:
        return await lifecycle.shutdown(None)


# Registry of entrypoint → async handler functions
_handlers: dict[str, Callable[..., Coroutine[Any, Any, None]]] = {}

# Internal maintenance is deliberately not a queue entrypoint: canonical
# operations remain the only user-submittable workflow mutations.
_BATCH_MAINTENANCE_ADVISORY_LOCK = 2_104_711_915
_BATCH_MAINTENANCE_INTERVAL_SECONDS = 60.0
_RETENTION_MAINTENANCE_ADVISORY_LOCK = 2_104_711_916
_WORKFLOW_ALERT_MAINTENANCE_ADVISORY_LOCK = 2_104_711_917
_WORKFLOW_ALERT_MAINTENANCE_INTERVAL_SECONDS = 5.0
_WORKFLOW_ALERT_MAX_CONCURRENT_DELIVERIES = 8

_WORKFLOW_ALERT_PENDING_EVENT_QUERY = """
    WITH root_cohort AS (
        SELECT event.id, event.created_at, 0 AS cohort
        FROM workflow_terminal_events AS event
        LEFT JOIN pgqueuer_jobs AS job ON job.id = event.operation_id
        WHERE event.classification_status = 'pending'
          AND (
              event.source_kind <> 'operation'
              OR job.id IS NULL
              OR job.parent_job_id IS NULL
          )
        ORDER BY event.created_at, event.id
        LIMIT $1
    ), child_cohort AS (
        SELECT event.id, event.created_at, 1 AS cohort
        FROM workflow_terminal_events AS event
        JOIN pgqueuer_jobs AS job ON job.id = event.operation_id
        WHERE event.classification_status = 'pending'
          AND event.source_kind = 'operation'
          AND job.parent_job_id IS NOT NULL
        ORDER BY event.created_at, event.id
        LIMIT $2
    )
    SELECT id
    FROM (
        SELECT * FROM root_cohort
        UNION ALL
        SELECT * FROM child_cohort
    ) AS fair_cohorts
    ORDER BY cohort, created_at, id
"""

_WORKFLOW_ALERT_ORPHAN_EVENT_CLEANUP_QUERY = """
    WITH candidates AS (
        SELECT event.id
        FROM workflow_terminal_events AS event
        WHERE event.classification_status IN ('telemetry_only', 'rejected')
          AND event.created_at < NOW() - make_interval(days => $1)
          AND NOT EXISTS (
              SELECT 1 FROM workflow_alert_deliveries AS delivery
              WHERE delivery.event_id = event.id
          )
        ORDER BY event.created_at, event.id
        LIMIT $2
    )
    DELETE FROM workflow_terminal_events
    WHERE id IN (SELECT id FROM candidates)
"""


def _sqlalchemy_url_to_asyncpg(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgres://", 1)
    return url


def register_handler(entrypoint: str) -> Callable:
    """Decorator to register an async handler for a job entrypoint."""

    def decorator(func: Callable[..., Coroutine[Any, Any, None]]) -> Callable:
        _handlers[entrypoint] = func
        return func

    return decorator


async def _claim_jobs(
    conn: asyncpg.Connection,
    *,
    batch_size: int = 5,
) -> list[dict[str, Any]]:
    """Claim available jobs using SELECT FOR UPDATE SKIP LOCKED."""
    rows = await conn.fetch(
        """
        UPDATE pgqueuer_jobs
        SET status = 'in_progress',
            started_at = COALESCE(started_at, NOW()),
            heartbeat_at = NOW(),
            claim_protocol_version = 2
        WHERE id IN (
            SELECT id FROM pgqueuer_jobs
            WHERE status = 'queued'
              AND execute_after <= NOW()
            ORDER BY priority DESC, created_at ASC
            LIMIT $1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, entrypoint, payload, claim_generation, claim_protocol_version,
                  root_operation_id, submission_context, submission_traceparent,
                  submission_tracestate, trace_id, created_at
        """,
        batch_size,
    )
    return [dict(row) for row in rows]


async def _complete_job(
    conn: asyncpg.Connection,
    job_id: int,
    claim_generation: int,
) -> bool:
    """Mark uncancelled active work completed without overwriting terminal state."""
    completed_id = await conn.fetchval(
        """
        UPDATE pgqueuer_jobs
        SET status = 'completed', completed_at = NOW(), heartbeat_at = NOW()
        WHERE id = $1
          AND status = 'in_progress'
          AND claim_generation = $2
          AND NOT COALESCE((payload->>'cancel_requested')::boolean, FALSE)
        RETURNING id
        """,
        job_id,
        claim_generation,
    )
    return completed_id is not None


async def _checkpoint_job_cancellation(
    conn: asyncpg.Connection,
    job_id: int,
    claim_generation: int,
) -> bool:
    """Resolve a cancellation that raced the handler's final safe checkpoint."""

    row = await conn.fetchrow(
        """
        UPDATE pgqueuer_jobs
        SET status = 'cancelled',
            payload = COALESCE(payload, '{}'::jsonb) || '{"message":"Cancelled"}'::jsonb,
            completed_at = NOW(),
            heartbeat_at = NOW()
        WHERE id = $1
          AND status = 'in_progress'
          AND claim_generation = $2
          AND COALESCE((payload->>'cancel_requested')::boolean, FALSE)
        RETURNING id
        """,
        job_id,
        claim_generation,
    )
    return row is not None


async def _fail_job(
    conn: asyncpg.Connection,
    job_id: int,
    claim_generation: int,
    error: str,
) -> bool:
    """Mark an active job failed without overwriting a terminal state."""
    failed_id = await conn.fetchval(
        """
        UPDATE pgqueuer_jobs
        SET status = 'failed', error = $3, completed_at = NOW(), heartbeat_at = NOW()
        WHERE id = $1
          AND status = 'in_progress'
          AND claim_generation = $2
          AND NOT COALESCE((payload->>'cancel_requested')::boolean, FALSE)
        RETURNING id
        """,
        job_id,
        claim_generation,
        error[:1000],  # Truncate long error messages
    )
    return failed_id is not None


async def _emit_job_notification(
    job_id: int,
    entrypoint: str,
    payload: dict[str, Any],
    *,
    error: str | None = None,
) -> None:
    """Emit a notification event for a completed or failed job.

    Maps entrypoints to notification event types and generates
    human-readable titles and summaries.
    """
    try:
        from src.models.notification import NotificationEventType
        from src.services.notification_service import get_dispatcher

        dispatcher = get_dispatcher()

        if error:
            await dispatcher.emit(
                event_type=NotificationEventType.JOB_FAILURE,
                title=f"Job failed: {entrypoint}",
                summary=error[:200],
                payload={
                    "job_id": job_id,
                    "entrypoint": entrypoint,
                    "error": error[:500],
                    "url": "/jobs",
                },
            )
            return

        # Map entrypoints to event types
        entrypoint_event_map: dict[str, tuple[NotificationEventType, str]] = {
            "summarize_content": (
                NotificationEventType.BATCH_SUMMARY,
                "Content summarized",
            ),
            "process_content": (
                NotificationEventType.BATCH_SUMMARY,
                "Content processed",
            ),
            "ingest_content": (
                NotificationEventType.BATCH_SUMMARY,
                "Content ingested",
            ),
            "scan_newsletters": (
                NotificationEventType.BATCH_SUMMARY,
                "Newsletter scan complete",
            ),
            "extract_url_content": (
                NotificationEventType.BATCH_SUMMARY,
                "URL content extracted",
            ),
        }

        event_type, default_title = entrypoint_event_map.get(
            entrypoint,
            (NotificationEventType.BATCH_SUMMARY, f"Job completed: {entrypoint}"),
        )

        content_id = payload.get("content_id")
        source = payload.get("source", "")
        url = "/jobs"
        if content_id:
            url = f"/content/{content_id}"

        await dispatcher.emit(
            event_type=event_type,
            title=default_title,
            summary=f"Job {job_id} ({entrypoint}) completed successfully"
            + (f" for source '{source}'" if source else ""),
            payload={
                "job_id": job_id,
                "entrypoint": entrypoint,
                "content_id": content_id,
                "url": url,
            },
        )
    except Exception:
        # Notification emission is best-effort — never fail the job
        logger.debug("Failed to emit job notification", exc_info=True)


def _queue_wait_milliseconds(job: dict[str, Any], *, now: datetime | None = None) -> int:
    """Return a non-negative bounded queue-wait duration from durable timestamps."""

    created_at = job.get("created_at")
    if not isinstance(created_at, datetime):
        return 0
    elapsed = ((now or datetime.now(UTC)) - created_at).total_seconds() * 1000
    return min(max(int(elapsed), 0), 2_147_483_647)


def _attempt_context_from_job(job: dict[str, Any]):
    """Reconstruct one claim attempt strictly from persisted queue context."""

    from src.config.settings import get_settings
    from src.contracts.operation_context import (
        OperationContext,
        OperationStage,
        parse_operation_context,
    )

    raw = job.get("submission_context")
    if isinstance(raw, str):
        raw = json.loads(raw)
    settings = get_settings()
    if raw is None:
        trace_id = secrets.token_hex(16)
        submission_span_id = secrets.token_hex(8)
        operation_id = str(job["id"])
        submission = OperationContext(
            schema_version=1,
            operation_id=operation_id,
            root_operation_id=str(job.get("root_operation_id") or operation_id),
            parent_operation_id=None,
            traceparent=f"00-{trace_id}-{submission_span_id}-01",
            tracestate=None,
            trace_id=trace_id,
            span_id=submission_span_id,
            claim_generation="0",
            attempt_number=None,
            entrypoint=str(job["entrypoint"]),
            service_name=settings.otel_service_name[:100] or "newsletter-aggregator",
            service_instance_id="legacy-submission",
            environment=settings.environment,
            release_revision="legacy",
            stage=OperationStage.SUBMIT,
            resource_kind=None,
            resource_key=None,
        )
    else:
        submission = parse_operation_context(raw)
        if (
            submission.operation_id != str(job["id"])
            or submission.root_operation_id != str(job["root_operation_id"])
            or submission.traceparent != job["submission_traceparent"]
            or submission.tracestate != job.get("submission_tracestate")
            or submission.trace_id != job["trace_id"]
        ):
            raise ValueError("queue observation context fields do not match")

    claim_generation = int(job["claim_generation"])
    span_id = secrets.token_hex(8)
    instance = os.environ.get("ACA_SERVICE_INSTANCE_ID", socket.gethostname())[:128] or "unknown"
    release = os.environ.get(
        "RELEASE_REVISION", os.environ.get("RAILWAY_GIT_COMMIT_SHA", "unknown")
    )
    values = submission.model_dump(mode="python")
    values.update(
        traceparent=f"00-{submission.trace_id}-{span_id}-{submission.traceparent[-2:]}",
        span_id=span_id,
        claim_generation=str(claim_generation),
        attempt_number=str(claim_generation + 1),
        service_name=settings.otel_service_name[:100] or "newsletter-aggregator",
        service_instance_id=instance,
        environment=settings.environment,
        release_revision=release[:64] or "unknown",
        stage=OperationStage.CLAIM,
    )
    return OperationContext.model_validate(values)


@contextmanager
def _bind_submission_parent(job: dict[str, Any]) -> Iterator[None]:
    """Install the validated persisted W3C carrier as the OTel remote parent."""

    raw = job.get("submission_context")
    if isinstance(raw, str):
        raw = json.loads(raw)
    if raw is None:
        yield
        return
    from src.contracts.operation_context import parse_operation_context

    submission = parse_operation_context(raw)
    carrier = {"traceparent": submission.traceparent}
    if submission.tracestate is not None:
        carrier["tracestate"] = submission.tracestate
    try:
        from opentelemetry.context import attach, detach
        from opentelemetry.propagate import extract

        token = attach(extract(carrier))
    except Exception:
        yield
        return
    try:
        yield
    finally:
        detach(token)


def _actual_attempt_context(context: Any, span: Any) -> Any:
    """Replace provisional identifiers with the actual provider span when exposed."""

    try:
        span_context = span.get_span_context()
        if not span_context.is_valid:
            return context
        trace_id = format(span_context.trace_id, "032x")
        span_id = format(span_context.span_id, "016x")
        trace_flags = format(int(span_context.trace_flags), "02x")
    except (AttributeError, TypeError, ValueError):
        return context
    values = context.model_dump(mode="python")
    values.update(
        trace_id=trace_id,
        span_id=span_id,
        traceparent=f"00-{trace_id}-{span_id}-{trace_flags}",
    )
    return type(context).model_validate(values)


@contextmanager
def _attempt_trace(job: dict[str, Any], context: Any) -> Iterator[Any]:
    from src.contracts.operation_context import bind_operation_context
    from src.telemetry import get_provider
    from src.telemetry.operation_spans import operation_span

    generation = int(context.claim_generation)
    with (
        _bind_submission_parent(job),
        operation_span(
            get_provider(),
            f"operation.{job['entrypoint']}.attempt",
            context=context,
            attributes={
                "queue.retry": generation > 0,
                "queue.retry_from_claim_generation": generation - 1 if generation > 0 else None,
                "queue.wait_ms": _queue_wait_milliseconds(job),
            },
        ) as span,
    ):
        actual = _actual_attempt_context(context, span)
        with bind_operation_context(actual):
            yield actual


async def _start_attempt_evidence(conn: asyncpg.Connection, context: Any) -> bool:
    """Fence and append the durable attempt row before handler side effects."""

    from src.repositories.operation_observation_attempts import AttemptStart, start_attempt

    return await start_attempt(
        conn,
        AttemptStart(
            operation_id=int(context.operation_id),
            claim_generation=int(context.claim_generation),
            trace_id=context.trace_id,
            root_span_id=context.span_id,
            langfuse_observation_id=None,
            service_name=context.service_name,
            service_instance_id=context.service_instance_id,
            environment=context.environment,
            release_revision=context.release_revision,
            started_at=datetime.now(UTC),
        ),
    )


class _AttemptFinalizationError(RuntimeError):
    """Abort a canonical transition when matching attempt evidence cannot be fenced."""


async def _complete_attempt_evidence(
    conn: asyncpg.Connection,
    context: Any,
    *,
    outcome: str,
    retryable: bool,
    diagnostic_codes: tuple[str, ...] = (),
) -> bool:
    """Complete evidence only when the same claim is canonically terminal."""

    completed_id = await conn.fetchval(
        """
        WITH canonical_terminal AS (
            SELECT id, claim_generation, status
            FROM pgqueuer_jobs
            WHERE id = $1
              AND claim_generation = $2::bigint
              AND status IN ('completed', 'failed', 'cancelled')
            FOR UPDATE
        )
        UPDATE operation_observation_attempts AS attempt
        SET completed_at = $3,
            terminal_stage = 'claim',
            outcome = $4,
            retryable = $5,
            telemetry_delivery_state = 'delivered',
            diagnostic_codes = $6::operation_diagnostic_code[],
            diagnostics_omitted = 0
        FROM canonical_terminal AS job
        WHERE attempt.operation_id = $1
          AND attempt.claim_generation = $2
          AND job.id = attempt.operation_id
          AND job.status::text = CASE $4::text
              WHEN 'succeeded' THEN 'completed'
              WHEN 'permanent_failure' THEN 'failed'
              WHEN 'cancelled' THEN 'cancelled'
              ELSE ''
          END
        RETURNING attempt.operation_id
        """,
        int(context.operation_id),
        int(context.claim_generation),
        datetime.now(UTC),
        outcome,
        retryable,
        list(diagnostic_codes),
    )
    return completed_id is not None


async def _terminal_job_status(
    conn: asyncpg.Connection,
    job_id: int,
    claim_generation: int,
) -> Literal["completed", "failed", "cancelled"] | None:
    status = await conn.fetchval(
        """
        SELECT status::text
        FROM pgqueuer_jobs
        WHERE id = $1
          AND claim_generation = $2
          AND status IN ('completed', 'failed', 'cancelled')
        FOR UPDATE
        """,
        job_id,
        claim_generation,
    )
    if status in {"completed", "failed", "cancelled"}:
        return status
    return None


async def _finalize_attempt_transition(
    conn: asyncpg.Connection,
    context: Any,
    *,
    target_status: Literal["completed", "failed", "cancelled"],
    error: str | None = None,
    diagnostic_codes: tuple[str, ...] = (),
) -> tuple[Literal["completed", "failed", "cancelled"] | None, bool]:
    """Atomically resolve canonical state and matching fenced attempt evidence."""

    job_id = int(context.operation_id)
    claim_generation = int(context.claim_generation)
    transitioned = False
    terminal_status: Literal["completed", "failed", "cancelled"] | None = None
    transaction: Any = conn.transaction()
    if inspect.isawaitable(transaction):
        transaction = await transaction
    async with transaction:
        if target_status == "completed":
            transitioned = await _complete_job(conn, job_id, claim_generation)
        elif target_status == "failed":
            if error is None:
                raise ValueError("failed terminal transition requires an error")
            transitioned = await _fail_job(conn, job_id, claim_generation, error)
        else:
            transitioned = await _checkpoint_job_cancellation(conn, job_id, claim_generation)

        if transitioned:
            terminal_status = target_status
        elif target_status != "cancelled" and await _checkpoint_job_cancellation(
            conn, job_id, claim_generation
        ):
            terminal_status = "cancelled"
            transitioned = True
        else:
            terminal_status = await _terminal_job_status(conn, job_id, claim_generation)

        if terminal_status is None:
            return None, False

        outcomes = {
            "completed": "succeeded",
            "failed": "permanent_failure",
            "cancelled": "cancelled",
        }
        completed = await _complete_attempt_evidence(
            conn,
            context,
            outcome=outcomes[terminal_status],
            retryable=False,
            diagnostic_codes=(diagnostic_codes if terminal_status == target_status else ()),
        )
        if not completed:
            raise _AttemptFinalizationError(
                f"Attempt evidence for operation {job_id} generation "
                f"{claim_generation} did not match canonical {terminal_status}"
            )
    return terminal_status, transitioned


async def _record_stale_attempt(conn: asyncpg.Connection, context: Any) -> bool:
    from src.repositories.operation_observation_attempts import record_stale_claim_diagnostic

    return await record_stale_claim_diagnostic(
        conn, int(context.operation_id), int(context.claim_generation)
    )


async def _process_job(
    conn: asyncpg.Connection,
    job: dict[str, Any],
) -> None:
    """Process a single job by dispatching to its registered handler."""
    job_id = job["id"]
    entrypoint = job["entrypoint"]
    claim_generation = int(job["claim_generation"])
    claim_protocol_version = int(job["claim_protocol_version"])
    payload = job["payload"] or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    try:
        attempt_context = _attempt_context_from_job(job)
    except (TypeError, ValueError, json.JSONDecodeError):
        logger.error("Job %s has invalid persisted observation context", job_id)
        await _fail_job(conn, job_id, claim_generation, "Invalid operation observation context")
        return

    from src.queue.execution_claim import ExecutionClaim, bind_execution_claim
    from src.queue.setup import touch_job_heartbeat

    claim = ExecutionClaim(
        job_id=job_id,
        claim_generation=claim_generation,
        claim_protocol_version=claim_protocol_version,
    )

    with bind_execution_claim(claim), _attempt_trace(job, attempt_context) as attempt_context:
        if await _checkpoint_job_cancellation(conn, job_id, claim_generation):
            logger.info(f"Job {job_id} ({entrypoint}) cancelled before handler invocation")
            return
        if not await touch_job_heartbeat(
            job_id,
            conn=conn,
            claim_generation=claim_generation,
        ):
            logger.info(f"Job {job_id} ({entrypoint}) lost its execution claim")
            return

        if not await _start_attempt_evidence(conn, attempt_context):
            logger.info(f"Job {job_id} ({entrypoint}) lost its attempt start fence")
            return

        handler = _handlers.get(entrypoint)
        if handler is None:
            logger.warning(f"No handler for entrypoint {entrypoint!r}, failing job {job_id}")
            try:
                status, transitioned = await _finalize_attempt_transition(
                    conn,
                    attempt_context,
                    target_status="failed",
                    error=f"Unknown entrypoint: {entrypoint}",
                    diagnostic_codes=("workflow.unknown_entrypoint",),
                )
            except _AttemptFinalizationError:
                logger.error(
                    "Job %s (%s) terminal evidence could not be finalized",
                    job_id,
                    entrypoint,
                    exc_info=True,
                )
                return
            if status == "failed" and transitioned:
                await _emit_job_notification(
                    job_id,
                    entrypoint,
                    payload,
                    error=f"Unknown entrypoint: {entrypoint}",
                )
            elif status == "cancelled":
                logger.info(f"Job {job_id} ({entrypoint}) cancelled before failure")
            return

        async def _heartbeat_loop() -> None:
            while True:
                await asyncio.sleep(15)
                if not await touch_job_heartbeat(
                    job_id,
                    claim_generation=claim_generation,
                ):
                    return

        heartbeat_task = asyncio.create_task(_heartbeat_loop())
        try:
            await handler(job_id, payload)
            status, transitioned = await _finalize_attempt_transition(
                conn,
                attempt_context,
                target_status="completed",
            )
            if status == "completed" and transitioned:
                logger.info(f"Job {job_id} ({entrypoint}) completed")
                await _emit_job_notification(job_id, entrypoint, payload)
            elif status == "cancelled":
                logger.info(f"Job {job_id} ({entrypoint}) cancelled before completion")
            elif status is not None:
                logger.info(f"Job {job_id} ({entrypoint}) reached {status} in its handler")
            else:
                logger.info(f"Job {job_id} ({entrypoint}) lost its completion claim")
        except Exception as e:
            from src.queue.execution_claim import ClaimCancelled, ClaimSuperseded

            if isinstance(e, _AttemptFinalizationError):
                logger.error(
                    "Job %s (%s) terminal evidence could not be finalized",
                    job_id,
                    entrypoint,
                    exc_info=True,
                )
                return
            if isinstance(e, ClaimCancelled):
                status, _transitioned = await _finalize_attempt_transition(
                    conn,
                    attempt_context,
                    target_status="cancelled",
                )
                if status == "cancelled":
                    logger.info(f"Job {job_id} ({entrypoint}) cancelled at domain commit")
                else:
                    logger.info(f"Job {job_id} ({entrypoint}) lost cancellation claim")
                return
            if isinstance(e, ClaimSuperseded):
                await _record_stale_attempt(conn, attempt_context)
                logger.info(f"Job {job_id} ({entrypoint}) dropped superseded domain result")
                return
            logger.error(f"Job {job_id} ({entrypoint}) failed: {e}", exc_info=True)
            from src.queue.workflow_handlers import WorkflowHandlerError

            persisted_error = (
                str(e)
                if isinstance(e, WorkflowHandlerError)
                else "Job failed due to an internal error"
            )
            status, transitioned = await _finalize_attempt_transition(
                conn,
                attempt_context,
                target_status="failed",
                error=persisted_error,
                diagnostic_codes=("workflow.internal_error",),
            )
            if status == "failed" and transitioned:
                await _emit_job_notification(
                    job_id,
                    entrypoint,
                    payload,
                    error=persisted_error,
                )
            elif status == "cancelled":
                logger.info(f"Job {job_id} ({entrypoint}) cancelled after handler failure")
            elif status is not None:
                logger.info(f"Job {job_id} ({entrypoint}) reached {status} in its handler")
        finally:
            heartbeat_task.cancel()
            await asyncio.gather(heartbeat_task, return_exceptions=True)


async def _process_claimed_job(
    asyncpg_url: str,
    job: dict[str, Any],
) -> None:
    """Process one claim on a connection not shared with polling or sibling jobs."""

    conn = await asyncpg.connect(asyncpg_url)
    try:
        await _process_job(conn, job)
    finally:
        await conn.close()


async def _run_batch_maintenance_tick(conn: asyncpg.Connection) -> bool:
    """Run one internal batch cycle when this worker wins leader election."""
    from src.config.models import get_model_config

    model_config = get_model_config()
    config = model_config.batch_config
    if not config.get("enabled", False):
        return False

    acquired = await conn.fetchval(
        "SELECT pg_try_advisory_lock($1::bigint)",
        _BATCH_MAINTENANCE_ADVISORY_LOCK,
    )
    if not acquired:
        logger.debug("batch maintenance tick skipped; advisory lock held")
        return False

    try:
        from src.services.batch.workers import run_batch_maintenance
        from src.services.llm_router import LLMRouter
        from src.storage.database import get_db

        with get_db() as db:
            await run_batch_maintenance(
                db,
                LLMRouter(model_config),
                flush_max_requests=config["flush_max_requests"],
                flush_max_wait_minutes=config["flush_max_wait_minutes"],
                fallback_max_attempts=config["fallback_max_attempts"],
            )
        return True
    finally:
        await conn.execute(
            "SELECT pg_advisory_unlock($1::bigint)",
            _BATCH_MAINTENANCE_ADVISORY_LOCK,
        )


def _retention_tick_due(
    *,
    now: float,
    last_run_at: float | None,
    interval_seconds: float,
) -> bool:
    """Return whether startup or the configured process-local interval is due."""

    return last_run_at is None or now - last_run_at >= interval_seconds


def _record_retention_metrics(*, deleted_count: int, duration_seconds: float) -> None:
    """Emit bounded structured maintenance metrics without requiring telemetry."""

    logger.info(
        "operation retention maintenance completed",
        extra={
            "retention_deleted_count": deleted_count,
            "retention_duration_seconds": duration_seconds,
        },
    )


async def _run_retention_maintenance_tick(
    conn: asyncpg.Connection,
    *,
    retention_settings: Any,
) -> bool:
    """Run one graph-retention cycle when this worker wins leader election."""

    acquired = await conn.fetchval(
        "SELECT pg_try_advisory_lock($1::bigint)",
        _RETENTION_MAINTENANCE_ADVISORY_LOCK,
    )
    if not acquired:
        logger.debug("operation retention tick skipped; advisory lock held")
        return False

    started_at = monotonic()
    try:
        from src.queue.setup import cleanup_old_jobs

        deleted_count = await cleanup_old_jobs(
            older_than_days=retention_settings.job_retention_days,
            failed_older_than_days=retention_settings.failed_job_retention_days,
            batch_size=retention_settings.job_retention_batch_size,
            conn=conn,
        )
        _record_retention_metrics(
            deleted_count=deleted_count,
            duration_seconds=max(monotonic() - started_at, 0.0),
        )
        return True
    finally:
        await conn.execute(
            "SELECT pg_advisory_unlock($1::bigint)",
            _RETENTION_MAINTENANCE_ADVISORY_LOCK,
        )


def _build_workflow_alert_sink(alert_settings: Any) -> Any:
    """Construct the configured safe sink from validated process settings."""

    from src.services.alert_sinks import NoopAlertSink, WebhookAlertSink

    if alert_settings.workflow_alert_sink == "noop":
        return NoopAlertSink()
    secret = alert_settings.workflow_alert_webhook_secret
    return WebhookAlertSink(
        endpoint=alert_settings.workflow_alert_webhook_endpoint,
        allowed_hosts=alert_settings.get_workflow_alert_allowed_hosts(),
        secret=secret.get_secret_value() if secret is not None else None,
        timeout_seconds=alert_settings.workflow_alert_timeout_seconds,
        max_retry_after_seconds=alert_settings.workflow_alert_max_retry_after_seconds,
        allow_private_addresses=alert_settings.is_development,
    )


def _workflow_alert_cohort_sizes(batch_size: int) -> tuple[int, int]:
    """Reserve bounded root and child progress in every classification tick."""

    bounded_size = max(1, min(int(batch_size), 500))
    child_limit = max(1, bounded_size // 4)
    root_limit = max(1, bounded_size - child_limit)
    return root_limit, child_limit


def _workflow_alert_retry_policy(alert_settings: Any) -> Any:
    from src.services.workflow_alert_delivery import DeliveryRetryPolicy

    return DeliveryRetryPolicy(
        max_attempts=alert_settings.workflow_alert_max_attempts,
        base_backoff_seconds=alert_settings.workflow_alert_base_backoff_seconds,
        max_backoff_seconds=alert_settings.workflow_alert_max_backoff_seconds,
        max_retry_after_seconds=alert_settings.workflow_alert_max_retry_after_seconds,
        max_age_seconds=alert_settings.workflow_alert_delivery_max_age_seconds,
    )


async def _deliver_workflow_alert_claim(
    sink: Any,
    claim: Any,
    *,
    timeout_seconds: int,
) -> tuple[Any, Any]:
    """Run the complete sink coroutine inside the lease-backed wall-clock bound."""

    from src.services.alert_sinks import SinkDeliveryResult
    from src.services.workflow_alert_delivery import delivery_idempotency_key

    try:
        async with asyncio.timeout(timeout_seconds):
            result = await sink.deliver(
                claim.envelope,
                idempotency_key=delivery_idempotency_key(claim),
            )
    except TimeoutError:
        result = SinkDeliveryResult(disposition="retry", error_code="timeout")
    except Exception:
        logger.warning(
            "workflow alert sink failed delivery_id=%s event_id=%s",
            claim.delivery_id,
            claim.event_id,
        )
        result = SinkDeliveryResult(disposition="retry", error_code="sink_failure")
    return claim, result


async def _drain_workflow_alert_deliveries(*, alert_settings: Any) -> int:
    """Claim one tight window and persist each result as soon as it completes."""

    from src.services.workflow_alert_delivery import (
        claim_due_deliveries,
        mark_delivery_succeeded,
        record_delivery_failure,
    )
    from src.storage.database import get_db

    policy = _workflow_alert_retry_policy(alert_settings)
    window_size = min(
        int(alert_settings.workflow_alert_batch_size),
        _WORKFLOW_ALERT_MAX_CONCURRENT_DELIVERIES,
    )
    with get_db() as db:
        claims = claim_due_deliveries(
            db,
            now=datetime.now(UTC),
            lease_seconds=alert_settings.workflow_alert_lease_seconds,
            batch_size=window_size,
            policy=policy,
        )
    if not claims:
        return 0

    sink = _build_workflow_alert_sink(alert_settings)
    tasks = [
        asyncio.create_task(
            _deliver_workflow_alert_claim(
                sink,
                claim,
                timeout_seconds=alert_settings.workflow_alert_timeout_seconds,
            )
        )
        for claim in claims
    ]
    persisted = 0
    try:
        for completed in asyncio.as_completed(tasks):
            claim, result = await completed
            completed_at = datetime.now(UTC)
            with get_db() as db:
                if result.disposition == "success":
                    matched = mark_delivery_succeeded(db, claim=claim, now=completed_at)
                    if not matched:
                        logger.warning(
                            "workflow alert result missed lease delivery_id=%s event_id=%s",
                            claim.delivery_id,
                            claim.event_id,
                        )
                    else:
                        persisted += 1
                    continue
                failure_status = record_delivery_failure(
                    db,
                    claim=claim,
                    now=completed_at,
                    error_code=result.error_code or "sink_failure",
                    retryable=result.disposition == "retry",
                    retry_after_seconds=result.retry_after_seconds,
                    policy=policy,
                )
                if failure_status is not None:
                    persisted += 1
                if failure_status == "exhausted":
                    logger.error(
                        "workflow alert delivery exhausted delivery_id=%s event_id=%s",
                        claim.delivery_id,
                        claim.event_id,
                    )
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return persisted


def _cleanup_terminal_workflow_alert_records(
    db: Any,
    *,
    now: datetime,
    retention_days: int,
    exhausted_retention_days: int,
    batch_size: int,
) -> int:
    """Atomically remove retained terminal deliveries with their ready intent."""

    from sqlalchemy import and_, delete, exists, not_, or_, select

    from src.models.workflow_alert import WorkflowAlertDelivery, WorkflowTerminalEvent

    regular_cutoff = now - timedelta(days=retention_days)
    exhausted_cutoff = now - timedelta(days=exhausted_retention_days)
    terminal_retained = or_(
        and_(
            WorkflowAlertDelivery.status.in_(("delivered", "permanent_failure")),
            WorkflowAlertDelivery.updated_at < regular_cutoff,
        ),
        and_(
            WorkflowAlertDelivery.status == "exhausted",
            WorkflowAlertDelivery.updated_at < exhausted_cutoff,
        ),
    )
    has_delivery = exists(
        select(WorkflowAlertDelivery.id).where(
            WorkflowAlertDelivery.event_id == WorkflowTerminalEvent.id
        )
    )
    has_unretained_delivery = exists(
        select(WorkflowAlertDelivery.id).where(
            WorkflowAlertDelivery.event_id == WorkflowTerminalEvent.id,
            not_(terminal_retained),
        )
    )
    candidate_ids = list(
        db.scalars(
            select(WorkflowTerminalEvent.id)
            .where(
                WorkflowTerminalEvent.classification_status == "ready",
                has_delivery,
                not_(has_unretained_delivery),
            )
            .order_by(WorkflowTerminalEvent.created_at, WorkflowTerminalEvent.id)
            .limit(max(1, min(int(batch_size), 500)))
            .with_for_update(skip_locked=True)
        )
    )
    if not candidate_ids:
        return 0
    try:
        db.execute(
            delete(WorkflowAlertDelivery).where(WorkflowAlertDelivery.event_id.in_(candidate_ids))
        )
        db.flush()
        db.execute(delete(WorkflowTerminalEvent).where(WorkflowTerminalEvent.id.in_(candidate_ids)))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return len(candidate_ids)


async def _emit_backup_freshness_alert(conn: asyncpg.Connection, *, alert_settings: Any) -> None:
    """Evaluate backup freshness once per tick and enqueue at most one alert.

    Kept as a named seam so a test can assert the readiness path never reaches it,
    and so the emission itself can be exercised without standing up a worker loop.
    """
    from src.config.settings import get_settings
    from src.services.backup_freshness_alert import emit_backup_freshness_alert

    settings = getattr(alert_settings, "backup_monitoring_enabled", None)
    resolved = alert_settings if settings is not None else get_settings()
    await emit_backup_freshness_alert(conn, settings=resolved)


async def _run_workflow_alert_maintenance_tick(
    conn: asyncpg.Connection,
    *,
    alert_settings: Any,
) -> bool:
    """Classify, claim, deliver, and retain one bounded alert batch."""

    acquired = False
    async with conn.transaction():
        acquired = await conn.fetchval(
            "SELECT pg_try_advisory_xact_lock($1::bigint)",
            _WORKFLOW_ALERT_MAINTENANCE_ADVISORY_LOCK,
        )
        if not acquired:
            logger.debug("workflow alert maintenance tick skipped; advisory lock held")
        else:
            from src.services.workflow_alert_delivery import ensure_delivery
            from src.services.workflow_terminal_event_service import (
                WorkflowTerminalEventService,
            )
            from src.storage.database import get_db

            batch_size = alert_settings.workflow_alert_batch_size
            root_limit, child_limit = _workflow_alert_cohort_sizes(batch_size)
            event_rows = await conn.fetch(
                _WORKFLOW_ALERT_PENDING_EVENT_QUERY,
                root_limit,
                child_limit,
            )
            processor = WorkflowTerminalEventService(
                conn,
                diagnostic_origin=alert_settings.workflow_alert_diagnostic_origin,
                external_delivery_enabled=alert_settings.workflow_alert_sink == "webhook",
            )
            for row in event_rows:
                await processor.process_pending_event(row["id"])

            # Backup freshness is evaluated HERE and never from /ready: the
            # readiness endpoint is polled many times a minute, so emitting there
            # would produce one alert per probe. This tick holds the leader lock,
            # and the event key is keyed on the check window, so a sustained
            # outage produces exactly one alert per staleness period.
            #
            # Failure to evaluate freshness must not abort the alert tick that
            # delivers every other alert — including, in the worst case, the ones
            # explaining why the backup target is unreachable.
            try:
                await _emit_backup_freshness_alert(conn, alert_settings=alert_settings)
            except Exception:
                logger.exception("backup freshness alert emission failed")

    # Classification commits with the transaction-scoped leader lock before
    # synchronous sessions create delivery intents. The unique event/sink key
    # and delivery leases keep these post-election operations idempotent.
    if acquired and alert_settings.workflow_alert_sink == "webhook":
        ready_rows = await conn.fetch(
            """
            SELECT event.id
            FROM workflow_terminal_events AS event
            WHERE event.classification_status = 'ready'
              AND event.envelope IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM workflow_alert_deliveries AS delivery
                  WHERE delivery.event_id = event.id AND delivery.sink_name = 'webhook'
              )
            ORDER BY event.created_at, event.id
            LIMIT $1
            """,
            batch_size,
        )
        for row in ready_rows:
            with get_db() as db:
                ensure_delivery(
                    db,
                    event_id=row["id"],
                    sink_name="webhook",
                    now=datetime.now(UTC),
                )

    if acquired:
        with get_db() as db:
            _cleanup_terminal_workflow_alert_records(
                db,
                now=datetime.now(UTC),
                retention_days=alert_settings.workflow_alert_retention_days,
                exhausted_retention_days=(alert_settings.workflow_alert_exhausted_retention_days),
                batch_size=batch_size,
            )
        await conn.execute(
            _WORKFLOW_ALERT_ORPHAN_EVENT_CLEANUP_QUERY,
            alert_settings.workflow_alert_retention_days,
            batch_size,
        )

    delivered = 0
    if alert_settings.workflow_alert_sink == "webhook":
        delivered = await _drain_workflow_alert_deliveries(alert_settings=alert_settings)
    return bool(acquired or delivered)


async def run_worker(
    *,
    concurrency: int = 5,
    poll_interval: float = 5.0,
) -> None:
    """Run the embedded queue worker loop.

    Continuously polls pgqueuer_jobs for queued jobs, claims them
    using SELECT FOR UPDATE SKIP LOCKED, and processes them
    concurrently up to the given limit.

    Also listens on pg_notify('pgqueuer', ...) for immediate wakeup
    when new jobs are enqueued.

    Args:
        concurrency: Max concurrent job tasks
        poll_interval: Seconds between polls when no jobs found
    """
    queue_url = get_queue_connection_string()
    asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)
    from src.queue.setup import ensure_queue_schema_compatible

    await ensure_queue_schema_compatible()

    conn = await asyncpg.connect(asyncpg_url)
    maintenance_conn = await asyncpg.connect(asyncpg_url)
    retention_conn = await asyncpg.connect(asyncpg_url)
    alert_conn = await asyncpg.connect(asyncpg_url)
    from src.config.settings import get_settings

    retention_settings = get_settings()

    # Set up LISTEN for immediate job notification
    notify_event = asyncio.Event()

    def _on_notify(
        connection: asyncpg.Connection,
        pid: int,
        channel: str,
        payload: str,
    ) -> None:
        notify_event.set()

    await conn.add_listener("pgqueuer", _on_notify)

    active_tasks: set[asyncio.Task] = set()
    maintenance_task: asyncio.Task[bool] | None = None
    retention_task: asyncio.Task[bool] | None = None
    alert_task: asyncio.Task[bool] | None = None
    last_maintenance_at = float("-inf")
    last_retention_at: float | None = None
    last_alert_at = float("-inf")
    loop = asyncio.get_running_loop()
    logger.info(f"Embedded worker started (concurrency={concurrency})")

    try:
        while True:
            if maintenance_task is not None and maintenance_task.done():
                try:
                    maintenance_task.result()
                except Exception:
                    logger.exception("batch maintenance tick failed")
                maintenance_task = None

            if retention_task is not None and retention_task.done():
                try:
                    retention_task.result()
                except Exception:
                    logger.exception("operation retention maintenance tick failed")
                retention_task = None

            if alert_task is not None and alert_task.done():
                try:
                    alert_task.result()
                except Exception:
                    logger.exception("workflow alert maintenance tick failed")
                alert_task = None

            if (
                maintenance_task is None
                and loop.time() - last_maintenance_at >= _BATCH_MAINTENANCE_INTERVAL_SECONDS
            ):
                maintenance_task = asyncio.create_task(
                    _run_batch_maintenance_tick(maintenance_conn)
                )
                last_maintenance_at = loop.time()

            if retention_task is None and _retention_tick_due(
                now=loop.time(),
                last_run_at=last_retention_at,
                interval_seconds=retention_settings.job_retention_interval_seconds,
            ):
                retention_task = asyncio.create_task(
                    _run_retention_maintenance_tick(
                        retention_conn,
                        retention_settings=retention_settings,
                    )
                )
                last_retention_at = loop.time()

            if (
                alert_task is None
                and loop.time() - last_alert_at >= _WORKFLOW_ALERT_MAINTENANCE_INTERVAL_SECONDS
            ):
                alert_task = asyncio.create_task(
                    _run_workflow_alert_maintenance_tick(
                        alert_conn,
                        alert_settings=retention_settings,
                    )
                )
                last_alert_at = loop.time()

            # Clean up completed tasks
            done = {t for t in active_tasks if t.done()}
            for t in done:
                # Re-raise exceptions from tasks so they get logged
                try:
                    t.result()
                except Exception:
                    pass  # Already logged in _process_job
            active_tasks -= done

            # How many slots available?
            available = concurrency - len(active_tasks)
            if available > 0:
                jobs = await _claim_jobs(conn, batch_size=available)
                for job in jobs:
                    task = asyncio.create_task(_process_claimed_job(asyncpg_url, job))
                    active_tasks.add(task)

                if jobs:
                    # Found work — immediately loop to check for more
                    continue

            # No work found — wait for notification or poll timeout
            notify_event.clear()
            try:
                await asyncio.wait_for(notify_event.wait(), timeout=poll_interval)
            except TimeoutError:
                pass

    except asyncio.CancelledError:
        logger.info("Embedded worker shutting down...")
        # Wait for active tasks to complete
        if active_tasks:
            logger.info(f"Waiting for {len(active_tasks)} active tasks...")
            await asyncio.gather(*active_tasks, return_exceptions=True)
        raise
    finally:
        if maintenance_task is not None:
            maintenance_task.cancel()
            await asyncio.gather(maintenance_task, return_exceptions=True)
        if retention_task is not None:
            retention_task.cancel()
            await asyncio.gather(retention_task, return_exceptions=True)
        if alert_task is not None:
            alert_task.cancel()
            await asyncio.gather(alert_task, return_exceptions=True)
        await conn.remove_listener("pgqueuer", _on_notify)
        await conn.close()
        await maintenance_conn.close()
        await retention_conn.close()
        await alert_conn.close()


def _prepare_forced_summary(content_id: int) -> None:
    """Remove an existing summary so the item processor performs fresh work."""

    from src.models.content import Content, ContentStatus
    from src.models.summary import Summary
    from src.storage.database import get_db

    with get_db() as db:
        content = db.get(Content, content_id)
        if content is None:
            raise ValueError(f"Content {content_id} not found")
        db.query(Summary).filter(Summary.content_id == content_id).delete(synchronize_session=False)
        content.status = ContentStatus.PARSED
        content.error_message = None
        content.processed_at = None
        db.commit()


def register_all_handlers() -> None:
    """Register all job handlers.

    This imports and registers handlers for all known entrypoints.
    """
    # Import here to avoid circular imports — these modules register
    # handlers via the @register_handler decorator or direct assignment.
    _register_content_handlers()
    _register_reference_handlers()
    _register_agent_handlers()
    from src.queue.workflow_handlers import register_canonical_workflow_handlers

    register_canonical_workflow_handlers(register_handler)
    logger.info(f"Registered {len(_handlers)} job handlers: {list(_handlers.keys())}")


def _register_content_handlers() -> None:
    """Register content processing handlers."""
    import asyncio as _asyncio

    from src.queue.setup import reconcile_batch_job_status, update_job_progress

    @register_handler("extract_url_content")
    async def extract_url_content(job_id: int, payload: dict) -> None:
        from src.services.url_extractor import URLExtractor
        from src.storage.database import get_db

        content_id = payload.get("content_id")
        if not content_id:
            raise ValueError("Missing content_id")

        with get_db() as db:
            extractor = URLExtractor(db)
            await extractor.extract_content(content_id)

    @register_handler("process_content")
    async def process_content(job_id: int, payload: dict) -> None:
        content_id = payload.get("content_id")
        task_type = payload.get("task_type", "summarize")
        if not content_id:
            raise ValueError("Missing content_id")

        if task_type == "summarize":
            from src.processors.summarizer import ContentSummarizer

            summarizer = ContentSummarizer()
            await _asyncio.to_thread(summarizer.summarize_content, content_id)
        else:
            raise ValueError(f"Unknown task_type: {task_type}")

    @register_handler("scan_newsletters")
    async def scan_newsletters(job_id: int, payload: dict) -> None:
        from src.ingestion.gmail import GmailContentIngestionService

        service = GmailContentIngestionService()
        labels = payload.get("labels")
        if labels is None:
            # Keep scheduler defaults aligned with Gmail ingestion defaults.
            service.ingest_content()
        else:
            label_query = " OR ".join(f"label:{label}" for label in labels) if labels else ""
            service.ingest_content(query=label_query)

    @register_handler("summarize_content")
    async def summarize_content(job_id: int, payload: dict) -> None:
        from anthropic import RateLimitError

        from src.processors.summarizer import ContentSummarizer

        content_id = payload.get("content_id")
        if not content_id:
            raise ValueError("Missing content_id")
        force_reprocess = bool(payload.get("force_reprocess", payload.get("force", False)))

        await update_job_progress(job_id, 10, "Starting summarization")

        if force_reprocess:
            await _asyncio.to_thread(_prepare_forced_summary, content_id)

        RATE_LIMIT_BACKOFF_DELAYS = [5, 10, 20]
        last_error: Exception | None = None

        for attempt, delay in enumerate([*RATE_LIMIT_BACKOFF_DELAYS, None], start=1):
            try:
                summarizer = ContentSummarizer()
                success = await _asyncio.to_thread(summarizer.summarize_content, content_id)

                if success:
                    await update_job_progress(job_id, 100, "Completed")
                    await reconcile_batch_job_status(job_id)
                    return
                else:
                    raise RuntimeError(
                        f"Summarization returned failure for content_id={content_id}"
                    )

            except RateLimitError as e:
                last_error = e
                if delay is not None:
                    logger.warning(
                        f"Rate limited on attempt {attempt} for content_id={content_id}, "
                        f"retrying in {delay}s"
                    )
                    await update_job_progress(
                        job_id, 10, f"Rate limited, retrying in {delay}s (attempt {attempt})"
                    )
                    await _asyncio.sleep(delay)
                else:
                    raise

            except Exception:
                raise

        if last_error:
            raise last_error

    @register_handler("ingest_content")
    async def ingest_content(job_id: int, payload: dict) -> None:
        from datetime import timedelta

        from src.ingestion.orchestrator import (
            ingest_arxiv,
            ingest_arxiv_paper,
            ingest_blog,
            ingest_gmail,
            ingest_huggingface_papers,
            ingest_perplexity_search,
            ingest_podcast,
            ingest_readwise,
            ingest_rss,
            ingest_scholar,
            ingest_scholar_paper,
            ingest_scholar_refs,
            ingest_substack,
            ingest_url,
            ingest_xsearch,
            ingest_youtube,
            ingest_youtube_playlist,
            ingest_youtube_rss,
        )

        source = payload.get("source", "gmail")
        # max_results=None means "use sources.d config defaults"
        max_results = payload.get("max_results")
        days_back = payload.get("days_back", 7)
        force_reprocess = payload.get("force_reprocess", False)

        await update_job_progress(job_id, 10, f"Starting {source} ingestion")

        after_date = datetime.now(UTC) - timedelta(days=days_back)

        # Build source-specific kwargs — only include max_results if explicitly set
        source_map: dict[str, tuple] = {
            "gmail": (
                ingest_gmail,
                {
                    **({"max_results": max_results} if max_results is not None else {}),
                    **({"query": payload["query"]} if "query" in payload else {}),
                },
            ),
            "rss": (
                ingest_rss,
                {**({"max_entries_per_feed": max_results} if max_results is not None else {})},
            ),
            "youtube": (
                ingest_youtube,
                {
                    **({"max_videos": max_results} if max_results is not None else {}),
                    "use_oauth": not payload.get("public_only"),
                },
            ),
            "youtube-playlist": (
                ingest_youtube_playlist,
                {**({"max_videos": max_results} if max_results is not None else {})},
            ),
            "youtube-rss": (
                ingest_youtube_rss,
                {**({"max_videos": max_results} if max_results is not None else {})},
            ),
            "podcast": (
                ingest_podcast,
                {**({"max_entries_per_feed": max_results} if max_results is not None else {})},
            ),
            "substack": (
                ingest_substack,
                {
                    **({"max_entries_per_source": max_results} if max_results is not None else {}),
                    **(
                        {"session_cookie": payload["session_cookie"]}
                        if "session_cookie" in payload
                        else {}
                    ),
                },
            ),
            "xsearch": (
                ingest_xsearch,
                {
                    **({"prompt": payload["prompt"]} if "prompt" in payload else {}),
                    **({"max_threads": payload["max_threads"]} if "max_threads" in payload else {}),
                },
            ),
            "perplexity": (
                ingest_perplexity_search,
                {
                    **({"prompt": payload["prompt"]} if "prompt" in payload else {}),
                    **({"max_results": max_results} if max_results is not None else {}),
                    **(
                        {"recency_filter": payload["recency_filter"]}
                        if "recency_filter" in payload
                        else {}
                    ),
                    **(
                        {"context_size": payload["context_size"]}
                        if "context_size" in payload
                        else {}
                    ),
                },
            ),
            "url": (
                ingest_url,
                {
                    "url": payload.get("url", ""),
                    **({"title": payload["title"]} if "title" in payload else {}),
                    **({"tags": payload["tags"]} if "tags" in payload else {}),
                    **({"notes": payload["notes"]} if "notes" in payload else {}),
                    **({"auto_route": payload["auto_route"]} if "auto_route" in payload else {}),
                },
            ),
            "huggingface_papers": (
                ingest_huggingface_papers,
                {**({"max_papers": max_results} if max_results is not None else {})},
            ),
            "blog": (
                ingest_blog,
                {**({"max_entries_per_source": max_results} if max_results is not None else {})},
            ),
            "arxiv": (
                ingest_arxiv,
                {
                    **({"max_results": max_results} if max_results is not None else {}),
                    **({"no_pdf": payload["no_pdf"]} if "no_pdf" in payload else {}),
                },
            ),
            "scholar": (
                ingest_scholar,
                {**({"max_entries": max_results} if max_results is not None else {})},
            ),
            "scholar-paper": (
                ingest_scholar_paper,
                {
                    "identifier": payload.get("identifier", ""),
                    **({"with_refs": payload["with_refs"]} if "with_refs" in payload else {}),
                },
            ),
            "scholar-refs": (
                ingest_scholar_refs,
                {
                    **({"after": payload["after"]} if "after" in payload else {}),
                    **({"before": payload["before"]} if "before" in payload else {}),
                    **(
                        {"source_types": payload["source_types"]}
                        if "source_types" in payload
                        else {}
                    ),
                    **({"dry_run": payload["dry_run"]} if "dry_run" in payload else {}),
                    **({"limit": payload["limit"]} if "limit" in payload else {}),
                },
            ),
            "arxiv-paper": (
                ingest_arxiv_paper,
                {
                    "identifier": payload.get("identifier", ""),
                    "pdf_extraction": not payload.get("no_pdf"),
                    **(
                        {"force_reprocess": payload["force_reprocess"]}
                        if "force_reprocess" in payload
                        else {}
                    ),
                },
            ),
            "readwise": (
                ingest_readwise,
                {
                    "force_reprocess": force_reprocess,
                    # Readwise uses `updated_after`, not the standard `after_date`.
                    # Only narrow the window when the caller passed days_back;
                    # otherwise sync everything (parity with direct mode).
                    **({"updated_after": after_date} if "days_back" in payload else {}),
                    **(
                        {"source_types": payload["source_types"]}
                        if "source_types" in payload
                        else {}
                    ),
                    **(
                        {"include_deleted": payload["include_deleted"]}
                        if "include_deleted" in payload
                        else {}
                    ),
                    **({"max_books": payload["max_books"]} if "max_books" in payload else {}),
                },
            ),
        }

        if source not in source_map:
            raise ValueError(f"Unsupported source: {source}")

        ingest_func, kwargs = source_map[source]

        # Sources that don't take the standard after_date/force_reprocess kwargs
        # — either they have no time-window concept (single-identifier ingest)
        # or they use differently-named params (scholar-refs uses after/before).
        no_default_kwargs = {
            "url",
            "scholar",
            "scholar-paper",
            "scholar-refs",
            "arxiv-paper",
            "readwise",
        }
        if source in no_default_kwargs:
            result = await _asyncio.to_thread(lambda: ingest_func(**kwargs))
        else:
            result = await _asyncio.to_thread(
                lambda: ingest_func(
                    after_date=after_date,
                    force_reprocess=force_reprocess,
                    **kwargs,
                )
            )

        # Most sources return IngestionResponse post round-4 harmonization
        # (2026-05-08); a few legacy paths still return a plain int. Accept
        # both shapes so the partial-migration window doesn't break the worker
        # and so test mocks can keep returning ints without rebuilding the
        # full envelope. URL duplicates surface as items_skipped=1 so a
        # re-saved URL reports "Ingested 0 items" — semantically accurate.
        count = result if isinstance(result, int) else result.items_ingested

        await update_job_progress(job_id, 100, f"Ingested {count} items from {source}")

    @register_handler("run_pipeline")
    async def run_pipeline_handler(job_id: int, payload: dict) -> None:
        from src.pipeline.runner import run_pipeline

        pipeline_type = payload.get("pipeline_type", "daily")
        date = payload.get("date")
        sources = payload.get("sources")

        async def _on_progress(data: dict) -> None:
            stage = data.get("stage", "")
            status = data.get("status", "")
            message = data.get("message", f"{stage} {status}")
            progress_map = {
                ("ingestion", "started"): 10,
                ("ingestion", "completed"): 30,
                ("summarization", "started"): 35,
                ("summarization", "completed"): 70,
                ("digest", "started"): 75,
                ("digest", "completed"): 100,
            }
            pct = progress_map.get((stage, status), 50)
            await update_job_progress(job_id, pct, message)

        def _sync_progress(data: dict) -> None:
            _asyncio.get_event_loop().create_task(_on_progress(data))

        await run_pipeline(
            pipeline_type=pipeline_type,
            date=date,
            sources=sources,
            on_progress=_sync_progress,
        )


def _register_reference_handlers() -> None:
    """Register reference resolution handlers."""

    @register_handler("resolve_references")
    async def _handle_resolve_references(job_id: int, payload: dict) -> None:
        from src.services.reference_resolver import ReferenceResolver
        from src.storage.database import get_db

        content_id = payload.get("content_id")
        batch_size = payload.get("batch_size", 100)

        with get_db() as db:
            resolver = ReferenceResolver(db)
            if content_id:
                resolved = resolver.resolve_for_content(content_id)
            else:
                resolved = resolver.resolve_batch(batch_size)

        logger.info("Resolved %d references (job_id=%d)", resolved, job_id)


def _register_agent_handlers() -> None:
    """Register handlers for agent task execution."""

    @register_handler("execute_agent_task")
    async def execute_agent_task(job_id: int, payload: dict) -> None:
        """Execute an agent task through the conductor lifecycle."""
        from src.agents.approval.gates import ApprovalGate
        from src.agents.conductor import Conductor
        from src.agents.memory.provider import MemoryProvider
        from src.agents.registry import SpecialistRegistry
        from src.services.agent_service import AgentInsightService, AgentTaskService
        from src.services.llm_router import LLMRouter
        from src.storage.database import get_db

        task_id = payload["task_id"]
        task_type = payload.get("task_type", "research")
        persona = payload.get("persona", "default")
        prompt = payload.get("prompt", "")

        # Update task to PLANNING
        with get_db() as db:
            svc = AgentTaskService(db)
            svc.update_task_status(task_id, "planning")

        try:
            # Build conductor with real dependencies
            from src.config import get_model_config

            llm_router = LLMRouter(get_model_config())
            registry = SpecialistRegistry.create_default(llm_router)
            memory_provider = MemoryProvider(
                strategies={}
            )  # Empty until memory backends configured
            approval_gate = ApprovalGate()
            conductor = Conductor(
                registry=registry,
                memory_provider=memory_provider,
                approval_gate=approval_gate,
                llm_router=llm_router,
            )

            result = await conductor.execute_task(
                task_id=task_id,
                task_type=task_type,
                prompt=prompt,
                persona=persona,
            )

            # Persist results
            with get_db() as db:
                task_svc = AgentTaskService(db)
                task_svc.update_task_status(
                    task_id,
                    status=result.status,
                    result=result.result,
                    error=result.error,
                    cost=result.cost_total,
                    tokens=result.tokens_total,
                    persona_config=result.persona_snapshot,
                )

                # Store insights
                insight_svc = AgentInsightService(db)
                for insight in result.insights:
                    insight_svc.create_insight(
                        task_id=task_id,
                        insight_type=insight.get("type", "summary"),
                        title=insight.get("title", "Untitled"),
                        content=insight.get("content", ""),
                        confidence=insight.get("confidence", 0.0),
                        tags=[insight.get("type", "summary")],
                    )

            logger.info(
                "Agent task %s completed: status=%s, insights=%d, cost=$%.4f",
                task_id,
                result.status,
                len(result.insights),
                result.cost_total,
            )

        except Exception as e:
            logger.exception("Agent task %s failed: %s", task_id, e)
            with get_db() as db:
                svc = AgentTaskService(db)
                svc.update_task_status(task_id, "failed", error="Failed due to an internal error")
            raise
