"""State-machine tests for operation submission, retry, and cancellation."""

from __future__ import annotations

import inspect
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import asyncpg
import pytest

from src.models.jobs import (
    JobRecord,
    JobStatus,
    OperationStatus,
    OperationType,
    ResourceReference,
)
from src.services.operation_service import OperationConflictError, OperationService

NOW = datetime(2026, 7, 13, 10, 0, tzinfo=UTC)


def _job(
    *,
    status: JobStatus = JobStatus.QUEUED,
    payload: dict | None = None,
    retry_count: int = 0,
) -> JobRecord:
    return JobRecord(
        id=8123,
        entrypoint="digest.create",
        status=status,
        payload=payload
        or {
            "schema_version": 2,
            "operation_type": "digest.create",
            "input": {"digest_type": "daily"},
            "progress": 0,
            "message": "Queued",
            "cancel_requested": False,
            "resource": None,
            "result": None,
        },
        priority=0,
        retry_count=retry_count,
        created_at=NOW,
    )


@pytest.mark.asyncio
async def test_submission_emits_schema_v2_and_deterministic_idempotency(monkeypatch) -> None:
    enqueue = AsyncMock(return_value=(8123, True))
    get_status = AsyncMock(return_value=_job())
    monkeypatch.setattr("src.services.operation_service.queue_setup.enqueue_queue_job", enqueue)
    monkeypatch.setattr("src.services.operation_service.queue_setup.get_job_status", get_status)
    service = OperationService()

    first = await service.submit(
        OperationType.DIGEST_CREATE,
        {"period_end": "2026-07-14", "period_start": "2026-07-13"},
    )
    await service.submit(
        OperationType.DIGEST_CREATE,
        {"period_start": "2026-07-13", "period_end": "2026-07-14"},
    )

    first_call = enqueue.await_args_list[0]
    second_call = enqueue.await_args_list[1]
    payload = first_call.args[1]
    assert first_call.args[0] == OperationType.DIGEST_CREATE.value
    assert payload == {
        "schema_version": 2,
        "operation_type": "digest.create",
        "input": {"period_end": "2026-07-14", "period_start": "2026-07-13"},
        "progress": 0,
        "message": "Queued",
        "cancel_requested": False,
        "cancellable": True,
        "resource": None,
        "result": None,
        "problem": None,
    }
    assert first_call.kwargs["idempotency_key"] == second_call.kwargs["idempotency_key"]
    assert first.operation_id == "8123"


def test_submission_exposes_only_canonical_operation_entrypoints() -> None:
    assert "entrypoint" not in inspect.signature(OperationService.submit).parameters


@pytest.mark.asyncio
async def test_active_duplicate_returns_existing_handle(monkeypatch) -> None:
    enqueue = AsyncMock(return_value=(8123, False))
    get_status = AsyncMock(return_value=_job())
    monkeypatch.setattr("src.services.operation_service.queue_setup.enqueue_queue_job", enqueue)
    monkeypatch.setattr("src.services.operation_service.queue_setup.get_job_status", get_status)

    handle = await OperationService().submit(
        OperationType.DIGEST_CREATE,
        {"digest_type": "daily"},
        idempotency_key="weekly-2026-07-13",
    )

    assert handle.operation_id == "8123"
    assert enqueue.await_args.kwargs["idempotency_key"] == "weekly-2026-07-13"


class _MutationConnection:
    def __init__(self, returned_job: JobRecord | None) -> None:
        self.returned_job = returned_job
        self.fetchrow = AsyncMock(side_effect=self._fetchrow)
        self.execute = AsyncMock(return_value="SELECT 1")

    async def _fetchrow(self, query: str, *args):
        del args
        if "RETURNING" not in query or self.returned_job is None:
            return None
        job = self.returned_job
        return {
            "id": job.id,
            "entrypoint": job.entrypoint,
            "status": job.status.value,
            "payload": job.payload,
            "priority": job.priority,
            "error": job.error,
            "retry_count": job.retry_count,
            "parent_job_id": job.parent_job_id,
            "heartbeat_at": job.heartbeat_at,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
        }


@pytest.mark.asyncio
async def test_queued_cancellation_is_atomic() -> None:
    cancelled = _job(status=JobStatus.CANCELLED)
    cancelled.payload["cancel_requested"] = True
    cancelled.payload["message"] = "Cancelled"
    conn = _MutationConnection(cancelled)

    handle = await OperationService(connection=conn).cancel("8123")

    query = conn.fetchrow.await_args.args[0]
    assert "THEN 'cancelled'" in query
    assert "status = 'queued'" in query
    assert handle.status is OperationStatus.CANCELLED
    assert handle.cancellable is False


@pytest.mark.asyncio
async def test_running_cancellation_sets_request_for_safe_checkpoint() -> None:
    running = _job(status=JobStatus.IN_PROGRESS)
    running.payload["cancel_requested"] = True
    running.payload["message"] = "Cancellation requested"
    conn = _MutationConnection(running)

    handle = await OperationService(connection=conn).cancel("8123")

    query = conn.fetchrow.await_args.args[0]
    assert "cancel_requested" in query
    assert "status IN ('queued', 'in_progress')" in query
    assert handle.status is OperationStatus.IN_PROGRESS
    assert handle.message == "Cancellation requested"
    assert handle.cancellable is False


@pytest.mark.asyncio
async def test_completed_operation_rejects_cancellation(monkeypatch) -> None:
    conn = _MutationConnection(None)
    get_status = AsyncMock(return_value=_job(status=JobStatus.COMPLETED))
    monkeypatch.setattr(
        "src.services.operation_service.queue_setup.get_job_status",
        get_status,
    )

    with pytest.raises(OperationConflictError, match="cannot be cancelled"):
        await OperationService(connection=conn).cancel("8123")


@pytest.mark.asyncio
async def test_non_cancellable_running_operation_rejects_cancellation(monkeypatch) -> None:
    conn = _MutationConnection(None)
    running = _job(status=JobStatus.IN_PROGRESS)
    running.payload["cancellable"] = False
    get_status = AsyncMock(return_value=running)
    monkeypatch.setattr("src.services.operation_service.queue_setup.get_job_status", get_status)

    with pytest.raises(OperationConflictError, match="cannot be cancelled"):
        await OperationService(connection=conn).cancel("8123")


@pytest.mark.asyncio
async def test_repeated_running_cancellation_request_is_idempotent(monkeypatch) -> None:
    conn = _MutationConnection(None)
    running = _job(status=JobStatus.IN_PROGRESS)
    running.payload["cancel_requested"] = True
    running.payload["message"] = "Cancellation requested"
    get_status = AsyncMock(return_value=running)
    monkeypatch.setattr("src.services.operation_service.queue_setup.get_job_status", get_status)

    handle = await OperationService(connection=conn).cancel("8123")

    assert handle.status is OperationStatus.IN_PROGRESS
    assert handle.message == "Cancellation requested"


@pytest.mark.asyncio
async def test_retry_clears_stale_state_and_preserves_normalized_input() -> None:
    retried = _job(status=JobStatus.QUEUED, retry_count=2)
    conn = _MutationConnection(retried)

    handle = await OperationService(connection=conn).retry("8123")

    query, reset_json, operation_id = conn.fetchrow.await_args.args
    reset = json.loads(reset_json)
    assert operation_id == 8123
    assert "status = 'failed'" in query
    assert "retry_count = retry_count + 1" in query
    assert reset == {
        "progress": 0,
        "message": "Queued",
        "cancel_requested": False,
        "resource": None,
        "result": None,
        "problem": None,
    }
    assert handle.retry_count == 2


@pytest.mark.asyncio
async def test_retry_collision_is_reported_as_operation_conflict() -> None:
    conn = _MutationConnection(None)
    conn.fetchrow.side_effect = asyncpg.UniqueViolationError("active operation exists")

    with pytest.raises(OperationConflictError, match="equivalent operation is active"):
        await OperationService(connection=conn).retry("8123")


@pytest.mark.asyncio
async def test_cancellation_checkpoint_transitions_requested_job() -> None:
    cancelled = _job(status=JobStatus.CANCELLED)
    cancelled.payload["cancel_requested"] = True
    cancelled.payload["message"] = "Cancelled"
    conn = _MutationConnection(cancelled)

    handle = await OperationService(connection=conn).checkpoint_cancellation("8123")

    query = conn.fetchrow.await_args.args[0]
    assert "status = 'in_progress'" in query
    assert "cancel_requested" in query
    assert handle is not None
    assert handle.status is OperationStatus.CANCELLED


class _CancellationStateConnection:
    def __init__(self) -> None:
        self.job = _job(status=JobStatus.IN_PROGRESS)
        self.job.payload["cancel_requested"] = True
        self.fetchrow = AsyncMock(side_effect=self._fetchrow)
        self.fetchval = AsyncMock(side_effect=self._fetchval)

    async def _fetchrow(self, query: str, *_args):
        if "SET status = 'cancelled'" not in query:
            return None
        self.job.status = JobStatus.CANCELLED
        self.job.payload["message"] = "Cancelled"
        self.job.completed_at = NOW
        return _job_row(self.job)

    async def _fetchval(self, query: str, *_args):
        if "SET status = 'completed'" in query and self.job.status is JobStatus.IN_PROGRESS:
            self.job.status = JobStatus.COMPLETED
            return self.job.id
        return None


def _job_row(job: JobRecord) -> dict:
    return {
        "id": job.id,
        "entrypoint": job.entrypoint,
        "status": job.status.value,
        "payload": job.payload,
        "priority": job.priority,
        "error": job.error,
        "retry_count": job.retry_count,
        "parent_job_id": job.parent_job_id,
        "heartbeat_at": job.heartbeat_at,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }


@pytest.mark.asyncio
async def test_worker_completion_preserves_checkpoint_cancellation(monkeypatch) -> None:
    from src.queue import worker

    conn = _CancellationStateConnection()
    entrypoint = "test.cancellation"

    async def handler(job_id: int, _payload: dict) -> None:
        handle = await OperationService(connection=conn).checkpoint_cancellation(job_id)
        assert handle is not None
        assert handle.status is OperationStatus.CANCELLED

    heartbeat = AsyncMock()
    notification = AsyncMock()
    monkeypatch.setattr("src.queue.setup.touch_job_heartbeat", heartbeat)
    monkeypatch.setattr(worker, "_emit_job_notification", notification)
    monkeypatch.setitem(worker._handlers, entrypoint, handler)

    await worker._process_job(
        conn,  # type: ignore[arg-type]
        {"id": conn.job.id, "entrypoint": entrypoint, "payload": conn.job.payload},
    )

    assert conn.job.status is JobStatus.CANCELLED
    assert "status = 'in_progress'" in conn.fetchval.await_args.args[0]
    notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_failure_does_not_overwrite_terminal_state() -> None:
    from src.queue import worker

    conn = AsyncMock()

    await worker._fail_job(conn, 8123, "handler cleanup failed")

    query = conn.execute.await_args.args[0]
    assert "status = 'in_progress'" in query


@pytest.mark.asyncio
async def test_resource_and_result_attachments_preserve_active_state() -> None:
    with_resource = _job(status=JobStatus.IN_PROGRESS)
    with_resource.payload["resource"] = {
        "type": "digest",
        "id": "42",
        "url": "/api/v1/digests/42",
    }
    conn = _MutationConnection(with_resource)
    service = OperationService(connection=conn)

    resource_handle = await service.attach_resource(
        "8123",
        resource=ResourceReference(type="digest", id="42", url="/api/v1/digests/42"),
    )
    result_handle = await service.attach_result("8123", {"selection_fingerprint": "abc"})

    assert resource_handle.resource is not None
    assert result_handle.status is OperationStatus.IN_PROGRESS
    assert conn.fetchrow.await_count == 2


@pytest.mark.asyncio
async def test_cleanup_includes_cancelled_jobs(monkeypatch) -> None:
    from src.queue import setup as queue_setup

    conn = AsyncMock()
    conn.execute.return_value = "DELETE 2"

    @asynccontextmanager
    async def fake_connection(_conn=None):
        yield conn

    monkeypatch.setattr(queue_setup, "_queue_connection", fake_connection)

    count = await queue_setup.cleanup_old_jobs(older_than_days=30)

    assert count == 2
    assert "status IN ('completed', 'cancelled')" in conn.execute.await_args.args[0]


@pytest.mark.asyncio
async def test_status_read_reconciles_parent_after_failed_child(monkeypatch) -> None:
    from src.queue import setup as queue_setup

    parent = _job(status=JobStatus.IN_PROGRESS)
    parent.entrypoint = "summarize_batch"
    parent.payload["operation_type"] = "summarization.run"
    completed_parent = parent.model_copy(deep=True)
    completed_parent.status = JobStatus.COMPLETED
    completed_parent.payload.update(
        {"completed": 1, "failed": 1, "processed": 2, "total": 2, "progress": 100}
    )

    def row(job: JobRecord) -> dict:
        return {
            "id": job.id,
            "entrypoint": job.entrypoint,
            "status": job.status.value,
            "payload": job.payload,
            "priority": job.priority,
            "error": job.error,
            "retry_count": job.retry_count,
            "parent_job_id": job.parent_job_id,
            "heartbeat_at": job.heartbeat_at,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
        }

    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        row(parent),
        {"completed": 1, "failed": 1, "cancelled": 0, "total": 2},
        row(completed_parent),
    ]

    @asynccontextmanager
    async def fake_connection(_conn=None):
        yield conn

    monkeypatch.setattr(queue_setup, "_queue_connection", fake_connection)

    status = await queue_setup.get_job_status(parent.id)

    assert status is not None
    assert status.status is JobStatus.COMPLETED
    update_args = conn.execute.await_args.args
    aggregate = json.loads(update_args[2])
    assert aggregate["failed"] == 1
    assert aggregate["processed"] == 2
    assert update_args[3] is True


def test_cancelled_job_is_terminal() -> None:
    assert _job(status=JobStatus.CANCELLED).is_terminal is True
