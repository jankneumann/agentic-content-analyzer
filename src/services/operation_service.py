"""Durable operation projection and controls over ``pgqueuer_jobs``."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
from datetime import UTC, datetime
from time import monotonic
from typing import Any

import asyncpg

from src.models.jobs import (
    LEGACY_OPERATION_TYPES,
    JobRecord,
    JobStatus,
    OperationEvent,
    OperationHandle,
    OperationPage,
    OperationPayloadV2,
    OperationProblem,
    OperationStatus,
    OperationType,
    ResourceReference,
    normalize_operation_payload,
)
from src.queue import setup as queue_setup


class OperationError(RuntimeError):
    """Base class for errors exposed by operation adapters."""


class OperationNotFoundError(OperationError):
    """Raised when an operation ID does not exist."""


class OperationConflictError(OperationError):
    """Raised when a control is invalid for the durable operation state."""


class OperationService:
    """Application boundary for submission, observation, and safe controls."""

    def __init__(
        self,
        *,
        connection: asyncpg.Connection | None = None,
        poll_interval: float = queue_setup.DEFAULT_STATUS_POLL_SECONDS,
        max_wait_seconds: float = 30,
    ) -> None:
        if poll_interval < 0:
            raise ValueError("poll_interval must be non-negative")
        if max_wait_seconds < 0:
            raise ValueError("max_wait_seconds must be non-negative")
        self._connection = connection
        self._poll_interval = poll_interval
        self._max_wait_seconds = max_wait_seconds

    @staticmethod
    def project(job: JobRecord) -> OperationHandle:
        """Project a queue record into the shared OpenAPI operation shape."""

        payload = normalize_operation_payload(job.entrypoint, job.payload)
        problem = payload.problem
        if job.status is JobStatus.FAILED and problem is None:
            detail = job.error or "Operation failed"
            problem = OperationProblem(
                title="Operation failed",
                status=500,
                detail=detail,
                instance=f"/api/v1/operations/{job.id}",
                code="operation_failed",
            )

        active = job.status in {JobStatus.QUEUED, JobStatus.IN_PROGRESS}
        cancellable = active and payload.cancellable and not payload.cancel_requested
        return OperationHandle(
            operation_id=str(job.id),
            operation_type=payload.operation_type,
            status=OperationStatus(job.status.value),
            progress=payload.progress,
            message=payload.message,
            cancellable=cancellable,
            retry_count=job.retry_count,
            status_url=f"/api/v1/operations/{job.id}",
            events_url=f"/api/v1/operations/{job.id}/events",
            resource=payload.resource,
            result=payload.result,
            problem=problem,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )

    @staticmethod
    def event(
        handle: OperationHandle,
        *,
        sequence: int = 0,
        occurred_at: datetime | None = None,
    ) -> OperationEvent:
        """Encode the latest operation snapshot as a progress event."""

        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        return OperationEvent(
            event_id=f"{handle.operation_id}:{sequence}",
            operation_id=handle.operation_id,
            operation_type=handle.operation_type,
            status=handle.status,
            progress=handle.progress,
            message=handle.message,
            resource=handle.resource,
            problem=handle.problem,
            occurred_at=occurred_at or datetime.now(UTC),
        )

    async def submit(
        self,
        operation_type: OperationType,
        normalized_input: dict[str, Any],
        *,
        entrypoint: str | None = None,
        idempotency_key: str | None = None,
        priority: int = 0,
        parent_job_id: int | None = None,
        cancellable: bool = True,
    ) -> OperationHandle:
        """Submit a schema-v2 operation or return its active duplicate."""

        payload_model = OperationPayloadV2(
            operation_type=operation_type,
            input=normalized_input,
            cancellable=cancellable,
        )
        payload = payload_model.model_dump(mode="json")
        key = idempotency_key or self._derive_idempotency_key(
            operation_type,
            payload["input"],
        )
        job_id, _created = await queue_setup.enqueue_queue_job(
            entrypoint or operation_type.value,
            payload,
            priority=priority,
            parent_job_id=parent_job_id,
            conn=self._connection,
            idempotency_key=key,
        )
        return await self.get(str(job_id))

    async def get(self, operation_id: str | int) -> OperationHandle:
        job_id = self._parse_operation_id(operation_id)
        return self.project(await self._get_job(job_id))

    async def wait(
        self,
        operation_id: str | int,
        *,
        timeout_seconds: float,
    ) -> OperationHandle:
        """Wait up to the configured bound, returning the latest state on timeout."""

        timeout = min(max(timeout_seconds, 0), self._max_wait_seconds)
        deadline = monotonic() + timeout
        latest = await self.get(operation_id)
        while not latest.is_terminal and monotonic() < deadline:
            remaining = deadline - monotonic()
            await asyncio.sleep(min(self._poll_interval, max(remaining, 0)))
            latest = await self.get(operation_id)
        return latest

    async def list(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> OperationPage:
        """List canonical operations with a stable, opaque keyset cursor."""

        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        before_created_at, before_id = self._decode_cursor(cursor)
        async with queue_setup._queue_connection(self._connection) as conn:
            rows = await conn.fetch(
                """
                SELECT id, entrypoint, status, payload, priority, error,
                       retry_count, parent_job_id, heartbeat_at, created_at,
                       started_at, completed_at
                FROM pgqueuer_jobs
                WHERE (
                    ($1::timestamptz IS NULL)
                    OR (created_at, id) < ($1::timestamptz, $2::bigint)
                )
                  AND (
                    payload->>'schema_version' = '2'
                    OR entrypoint = ANY($3::text[])
                  )
                ORDER BY created_at DESC, id DESC
                LIMIT $4
                """,
                before_created_at,
                before_id,
                list(LEGACY_OPERATION_TYPES),
                limit + 1,
            )

        jobs = [self._job_from_row(row) for row in rows[:limit]]
        handles = [self.project(job) for job in jobs]
        next_cursor = None
        if len(rows) > limit and jobs:
            last = jobs[-1]
            next_cursor = self._encode_cursor(last.created_at, last.id)
        return OperationPage(data=handles, next_cursor=next_cursor)

    async def update_progress(
        self,
        operation_id: str | int,
        progress: int,
        message: str,
    ) -> OperationHandle:
        if progress < 0 or progress > 100:
            raise ValueError("progress must be between 0 and 100")
        job_id = self._parse_operation_id(operation_id)
        row = await self._update_returning(
            """
            UPDATE pgqueuer_jobs
            SET payload = COALESCE(payload, '{}'::jsonb) || $1::jsonb,
                heartbeat_at = NOW()
            WHERE id = $2 AND status = 'in_progress'
            RETURNING id, entrypoint, status, payload, priority, error,
                      retry_count, parent_job_id, heartbeat_at, created_at,
                      started_at, completed_at
            """,
            json.dumps({"progress": progress, "message": message}),
            job_id,
        )
        return self._require_updated(row, operation_id, "cannot accept progress updates")

    async def attach_resource(
        self,
        operation_id: str | int,
        resource: ResourceReference,
    ) -> OperationHandle:
        return await self._attach_payload(
            operation_id,
            {"resource": resource.model_dump(mode="json")},
            action="cannot attach a resource",
        )

    async def attach_result(
        self,
        operation_id: str | int,
        result: dict[str, Any],
    ) -> OperationHandle:
        return await self._attach_payload(
            operation_id,
            {"result": result},
            action="cannot attach a result",
        )

    async def cancel(self, operation_id: str | int) -> OperationHandle:
        """Cancel queued work or request cancellation of running work atomically."""

        job_id = self._parse_operation_id(operation_id)
        row = await self._update_returning(
            """
            UPDATE pgqueuer_jobs
            SET status = CASE WHEN status = 'queued' THEN 'cancelled' ELSE status END,
                payload = COALESCE(payload, '{}'::jsonb) || jsonb_build_object(
                    'cancel_requested', TRUE,
                    'message', CASE
                        WHEN status = 'queued' THEN 'Cancelled'
                        ELSE 'Cancellation requested'
                    END
                ),
                completed_at = CASE WHEN status = 'queued' THEN NOW() ELSE completed_at END,
                heartbeat_at = NOW()
            WHERE id = $1
              AND status IN ('queued', 'in_progress')
              AND COALESCE((payload->>'cancellable')::boolean, TRUE)
              AND NOT COALESCE((payload->>'cancel_requested')::boolean, FALSE)
            RETURNING id, entrypoint, status, payload, priority, error,
                      retry_count, parent_job_id, heartbeat_at, created_at,
                      started_at, completed_at
            """,
            job_id,
        )
        if row is not None:
            return self.project(self._job_from_row(row))

        job = await self._get_job(job_id)
        current = self.project(job)
        payload = normalize_operation_payload(job.entrypoint, job.payload)
        if current.status is OperationStatus.CANCELLED or (
            current.status is OperationStatus.IN_PROGRESS and payload.cancel_requested
        ):
            return current
        raise OperationConflictError(
            f"Operation {operation_id} cannot be cancelled from state {current.status.value}"
        )

    async def retry(self, operation_id: str | int) -> OperationHandle:
        """Requeue failed work while clearing all stale execution state."""

        job_id = self._parse_operation_id(operation_id)
        reset = {
            "progress": 0,
            "message": "Queued",
            "cancel_requested": False,
            "resource": None,
            "result": None,
            "problem": None,
        }
        row = await self._update_returning(
            """
            UPDATE pgqueuer_jobs
            SET status = 'queued',
                payload = COALESCE(payload, '{}'::jsonb) || $1::jsonb,
                error = NULL,
                retry_count = retry_count + 1,
                started_at = NULL,
                completed_at = NULL,
                execute_after = NOW(),
                heartbeat_at = NOW()
            WHERE id = $2 AND status = 'failed'
            RETURNING id, entrypoint, status, payload, priority, error,
                      retry_count, parent_job_id, heartbeat_at, created_at,
                      started_at, completed_at
            """,
            json.dumps(reset),
            job_id,
        )
        if row is None:
            current = await self.get(operation_id)
            raise OperationConflictError(
                f"Operation {operation_id} cannot be retried from state {current.status.value}"
            )
        async with queue_setup._queue_connection(self._connection) as conn:
            await conn.execute("SELECT pg_notify('pgqueuer', $1)", "operation_retry")
        return self.project(self._job_from_row(row))

    async def checkpoint_cancellation(
        self,
        operation_id: str | int,
    ) -> OperationHandle | None:
        """Transition requested running work at a workflow-declared safe point."""

        job_id = self._parse_operation_id(operation_id)
        row = await self._update_returning(
            """
            UPDATE pgqueuer_jobs
            SET status = 'cancelled',
                payload = COALESCE(payload, '{}'::jsonb) ||
                          '{"message":"Cancelled"}'::jsonb,
                completed_at = NOW(),
                heartbeat_at = NOW()
            WHERE id = $1
              AND status = 'in_progress'
              AND COALESCE((payload->>'cancel_requested')::boolean, FALSE)
            RETURNING id, entrypoint, status, payload, priority, error,
                      retry_count, parent_job_id, heartbeat_at, created_at,
                      started_at, completed_at
            """,
            job_id,
        )
        return self.project(self._job_from_row(row)) if row is not None else None

    async def _attach_payload(
        self,
        operation_id: str | int,
        patch: dict[str, Any],
        *,
        action: str,
    ) -> OperationHandle:
        job_id = self._parse_operation_id(operation_id)
        row = await self._update_returning(
            """
            UPDATE pgqueuer_jobs
            SET payload = COALESCE(payload, '{}'::jsonb) || $1::jsonb,
                heartbeat_at = NOW()
            WHERE id = $2 AND status = 'in_progress'
            RETURNING id, entrypoint, status, payload, priority, error,
                      retry_count, parent_job_id, heartbeat_at, created_at,
                      started_at, completed_at
            """,
            json.dumps(patch),
            job_id,
        )
        return self._require_updated(row, operation_id, action)

    async def _update_returning(self, query: str, *args: Any) -> Any:
        async with queue_setup._queue_connection(self._connection) as conn:
            return await conn.fetchrow(query, *args)

    async def _get_job(self, job_id: int) -> JobRecord:
        job = await queue_setup.get_job_status(job_id, conn=self._connection)
        if job is None:
            raise OperationNotFoundError(f"Operation {job_id} was not found")
        return job

    def _require_updated(
        self,
        row: Any,
        operation_id: str | int,
        action: str,
    ) -> OperationHandle:
        if row is None:
            raise OperationConflictError(f"Operation {operation_id} {action}")
        return self.project(self._job_from_row(row))

    @staticmethod
    def _job_from_row(row: Any) -> JobRecord:
        payload = row["payload"] or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        return JobRecord(
            id=int(row["id"]),
            entrypoint=str(row["entrypoint"]),
            status=JobStatus(row["status"]),
            payload=payload,
            priority=int(row["priority"] or 0),
            error=row["error"],
            retry_count=int(row["retry_count"] or 0),
            parent_job_id=row["parent_job_id"],
            heartbeat_at=row["heartbeat_at"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    @staticmethod
    def _derive_idempotency_key(
        operation_type: OperationType,
        normalized_input: dict[str, Any],
    ) -> str:
        canonical = json.dumps(normalized_input, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"operation:{operation_type.value}:{digest}"

    @staticmethod
    def _parse_operation_id(operation_id: str | int) -> int:
        try:
            parsed = int(operation_id)
        except (TypeError, ValueError) as exc:
            raise OperationNotFoundError(f"Invalid operation ID: {operation_id}") from exc
        if parsed < 1:
            raise OperationNotFoundError(f"Invalid operation ID: {operation_id}")
        return parsed

    @staticmethod
    def _encode_cursor(created_at: datetime, job_id: int) -> str:
        payload = json.dumps(
            {"created_at": created_at.isoformat(), "id": job_id},
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str | None) -> tuple[datetime | None, int]:
        if cursor is None:
            return None, 0
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
            created_at = datetime.fromisoformat(payload["created_at"])
            if created_at.tzinfo is None:
                raise ValueError("cursor timestamp must include a timezone")
            job_id = int(payload["id"])
            if job_id < 1:
                raise ValueError("cursor job ID must be positive")
        except (
            binascii.Error,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            UnicodeDecodeError,
            ValueError,
        ) as exc:
            raise ValueError("Invalid operation cursor") from exc
        return created_at, job_id
