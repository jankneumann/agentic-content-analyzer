"""State-machine tests for operation submission, retry, and cancellation."""

from __future__ import annotations

import inspect
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import asyncpg
import pytest

from src.models.jobs import (
    JobRecord,
    JobStatus,
    OperationPayloadV2,
    OperationStatus,
    OperationType,
    ResourceReference,
)
from src.queue.execution_claim import ExecutionClaim, bind_execution_claim
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


class _URLHandlerOperations:
    def __init__(self, result=None) -> None:
        self.handle = SimpleNamespace(
            status=JobStatus.IN_PROGRESS,
            resource=None,
            result=result,
        )
        self.attach_result = AsyncMock(side_effect=self._attach_result)
        self.update_progress = AsyncMock()
        self.checkpoint_cancellation = AsyncMock(return_value=None)

    async def get(self, _operation_id):
        return self.handle

    async def _attach_result(self, _operation_id, result):
        self.handle.result = result
        return self.handle


@pytest.mark.asyncio
async def test_url_retry_resumes_exact_content_without_reclassification(monkeypatch) -> None:
    from src.ingestion.registry import SourceRetryPolicy
    from src.ingestion.result import IngestionResponse
    from src.queue.workflow_handlers import build_workflow_handler_registry

    checkpoint = {"schema_version": 2, "command_key": "url"}
    operations = _URLHandlerOperations(result=checkpoint)
    command = SimpleNamespace(kind="url")
    sources = SimpleNamespace(
        parse_command=Mock(return_value=command),
        get=Mock(
            return_value=SimpleNamespace(
                key="url",
                retry_policy=SourceRetryPolicy(max_attempts=1),
            )
        ),
    )
    ingestion = SimpleNamespace(execute=Mock())
    resumed = Mock(
        return_value=IngestionResponse(
            command="ingest.url",
            source="url",
            status="ok",
            items_ingested=1,
            details={
                "command_key": "url",
                "resolved_route": "webpage",
                "emitted_sources": ["url"],
                "content_ids": [17],
            },
        )
    )
    monkeypatch.setattr("src.ingestion.orchestrator.resume_owned_url_extraction", resumed)
    registry = build_workflow_handler_registry(
        operation_service=operations,
        ingestion_service=ingestion,
        source_registry=sources,
    )

    with bind_execution_claim(ExecutionClaim(job_id=91, claim_generation=2)):
        await registry.dispatch(OperationType.INGESTION_EXECUTE, 91, {"kind": "url"})

    resumed.assert_called_once_with(91, checkpoint)
    ingestion.execute.assert_not_called()
    assert operations.handle.result["content_ids"] == [17]
    assert operations.handle.result["outcome"] == "success"


@pytest.mark.asyncio
async def test_url_extraction_failure_attaches_checkpoint_then_raises_retryably() -> None:
    from src.ingestion.registry import SourceRetryPolicy
    from src.ingestion.result import IngestionError, IngestionResponse
    from src.queue.workflow_handlers import (
        WorkflowExecutionError,
        build_workflow_handler_registry,
    )

    operations = _URLHandlerOperations()
    sources = SimpleNamespace(
        parse_command=Mock(return_value=SimpleNamespace(kind="url")),
        get=Mock(
            return_value=SimpleNamespace(
                key="url",
                retry_policy=SourceRetryPolicy(max_attempts=1),
            )
        ),
    )
    response = IngestionResponse(
        command="ingest.url",
        source="url",
        status="partial",
        items_ingested=1,
        errors=[IngestionError(code="extraction_failed", message="failed")],
        details={
            "command_key": "url",
            "resolved_route": "webpage",
            "emitted_sources": ["url"],
            "content_ids": [17],
        },
    )
    registry = build_workflow_handler_registry(
        operation_service=operations,
        ingestion_service=SimpleNamespace(execute=Mock(return_value=response)),
        source_registry=sources,
    )

    with bind_execution_claim(ExecutionClaim(job_id=91, claim_generation=1)):
        with pytest.raises(WorkflowExecutionError, match="resumable"):
            await registry.dispatch(OperationType.INGESTION_EXECUTE, 91, {"kind": "url"})

    operations.attach_result.assert_awaited_once()
    checkpoint = operations.attach_result.await_args.args[1]
    assert checkpoint["status"] == "partial"
    assert checkpoint["outcome"] == "partial"
    assert checkpoint["content_ids"] == [17]
    assert checkpoint["errors"][0]["code"] == "extraction_failed"


@pytest.mark.asyncio
async def test_url_initial_path_preserves_typed_claim_rejection() -> None:
    from src.ingestion.registry import SourceRetryPolicy
    from src.queue.execution_claim import ClaimCancelled
    from src.queue.workflow_handlers import build_workflow_handler_registry

    operations = _URLHandlerOperations()
    sources = SimpleNamespace(
        parse_command=Mock(return_value=SimpleNamespace(kind="url")),
        get=Mock(
            return_value=SimpleNamespace(
                key="url",
                retry_policy=SourceRetryPolicy(max_attempts=1),
            )
        ),
    )
    registry = build_workflow_handler_registry(
        operation_service=operations,
        ingestion_service=SimpleNamespace(
            execute=Mock(side_effect=ClaimCancelled("cancel raced extraction"))
        ),
        source_registry=sources,
    )

    with bind_execution_claim(ExecutionClaim(job_id=91, claim_generation=1)):
        with pytest.raises(ClaimCancelled, match="cancel raced extraction"):
            await registry.dispatch(OperationType.INGESTION_EXECUTE, 91, {"kind": "url"})


def test_url_checkpoint_requires_one_positive_non_bool_content_id() -> None:
    from src.queue.workflow_handlers import _is_url_extraction_checkpoint

    base = {
        "command_key": "url",
        "resolved_route": "webpage",
        "status": "partial",
        "outcome": "partial",
        "errors": [{"code": "extraction_failed"}],
    }
    assert not _is_url_extraction_checkpoint({**base, "content_ids": [True]})
    assert not _is_url_extraction_checkpoint({**base, "content_ids": [0]})
    assert _is_url_extraction_checkpoint({**base, "content_ids": [17]})


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
        class Transaction:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

        self.returned_job = returned_job
        self.fetch = AsyncMock(return_value=[])
        self.fetchrow = AsyncMock(side_effect=self._fetchrow)
        self.fetchval = AsyncMock(return_value=8123)
        self.execute = AsyncMock(return_value="SELECT 1")
        self.transaction = MagicMock(return_value=Transaction())

    async def _fetchrow(self, query: str, *args):
        del args
        if self.returned_job is None:
            return None
        job = self.returned_job
        row = {
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
        if "FOR UPDATE" in query:
            row["status"] = JobStatus.FAILED.value
            row["retry_count"] = max(0, job.retry_count - 1)
            return row
        return row if "RETURNING" in query else None


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

    query, reset_json, operation_id, ceiling = conn.fetchrow.await_args.args
    assert conn.fetchval.await_count == 5
    assert "WITH RECURSIVE lineage" in conn.fetchval.await_args_list[0].args[0]
    assert "pg_advisory_xact_lock" in conn.fetchval.await_args_list[1].args[0]
    assert "WITH RECURSIVE lineage" in conn.fetchval.await_args_list[2].args[0]
    assert "FOR UPDATE" in conn.fetchval.await_args_list[3].args[0]
    reset = json.loads(reset_json)
    assert operation_id == 8123
    assert ceiling is None
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


def _url_failure_result(*, content_ids: list[int] | None = None) -> dict:
    return {
        "schema_version": 2,
        "command_key": "url",
        "resolved_route": "webpage",
        "emitted_sources": ["webpage"],
        "status": "partial",
        "outcome": "partial",
        "items_ingested": 0,
        "items_skipped": 0,
        "items_failed": 1,
        "content_ids": [91] if content_ids is None else content_ids,
        "errors": [{"code": "extraction_failed", "message": "Extraction failed"}],
        "warnings": [],
        "errors_omitted": 0,
        "warnings_omitted": 0,
        "source_outcomes": [],
        "source_outcomes_omitted": 0,
        "details": {},
        "details_omitted": 0,
    }


class _LockedRetryConnection:
    def __init__(
        self,
        target: JobRecord,
        retried: JobRecord,
        *,
        owner_matches: bool = True,
        holds_lock: bool = True,
    ):
        self.target = target
        self.retried = retried
        self.owner_matches = owner_matches
        self.fetchrow = AsyncMock(side_effect=self._fetchrow)
        self.fetch = AsyncMock(return_value=[])
        self.holds_lock = holds_lock
        self.fetchval = AsyncMock(side_effect=self._fetchval)
        self.execute = AsyncMock()

    async def _fetchrow(self, query: str, *_args):
        if "FOR UPDATE" in query:
            return _job_row(self.target)
        if "UPDATE pgqueuer_jobs AS parent" in query:
            return _job_row(self.retried)
        return None

    async def _fetchval(self, query: str, *_args):
        if "pg_locks" in query:
            return self.holds_lock
        return self.owner_matches


@pytest.mark.asyncio
async def test_locked_retry_applies_atomic_optional_ceiling_and_notifies_on_connection() -> None:
    target = _job(status=JobStatus.FAILED, retry_count=2)
    target.claim_generation = 7
    retried = _job(status=JobStatus.QUEUED, retry_count=3)
    conn = _LockedRetryConnection(target, retried)

    row = await OperationService(connection=conn)._retry_locked(
        conn,
        8123,
        max_retries=3,
    )

    query, _reset, operation_id, ceiling = conn.fetchrow.await_args_list[-1].args
    assert "retry_count < $3" in query
    assert (operation_id, ceiling) == (8123, 3)
    assert row["status"] == "queued"
    conn.execute.assert_awaited_once_with(
        "SELECT pg_notify('pgqueuer', $1)",
        "operation_retry",
    )


@pytest.mark.asyncio
async def test_locked_retry_closes_current_terminal_attempt_before_state_reset(
    monkeypatch,
) -> None:
    target = _job(status=JobStatus.FAILED, retry_count=1)
    target.claim_generation = 7
    conn = _LockedRetryConnection(target, _job(status=JobStatus.QUEUED, retry_count=2))
    close_attempts = AsyncMock()
    monkeypatch.setattr(
        OperationService,
        "_close_terminal_attempts_before_retry",
        close_attempts,
    )

    await OperationService(connection=conn)._retry_locked(conn, 8123)

    close_attempts.assert_awaited_once_with(conn, [8123])
    assert conn.fetchrow.await_args_list[-1].args[0].lstrip().startswith("WITH retried_children")


@pytest.mark.asyncio
async def test_locked_retry_rejects_connection_without_graph_lock() -> None:
    conn = _LockedRetryConnection(
        _job(status=JobStatus.FAILED),
        _job(status=JobStatus.QUEUED),
        holds_lock=False,
    )

    with pytest.raises(OperationConflictError, match="graph lock"):
        await OperationService(connection=conn)._retry_locked(conn, 8123)

    conn.fetchrow.assert_not_awaited()
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_locked_retry_preserves_only_valid_exact_url_failure_checkpoint() -> None:
    checkpoint = _url_failure_result()
    target = _job(
        status=JobStatus.FAILED,
        payload=OperationPayloadV2(
            operation_type=OperationType.INGESTION_EXECUTE,
            input={"url": "https://example.com"},
            result=checkpoint,
        ).model_dump(mode="json"),
    )
    target.entrypoint = OperationType.INGESTION_EXECUTE.value
    target.claim_generation = 7
    retried = _job(status=JobStatus.QUEUED)
    conn = _LockedRetryConnection(target, retried)

    await OperationService(connection=conn)._retry_locked(conn, 8123)

    reset = json.loads(conn.fetchrow.await_args_list[-1].args[1])
    assert reset["result"] == checkpoint
    owner_query, content_id, operation_id, generation = conn.fetchval.await_args.args
    assert "status_operation_phase = 'parsing'" in owner_query
    assert "source_type" in owner_query
    assert (content_id, operation_id, generation) == (91, 8123, 7)


@pytest.mark.asyncio
async def test_locked_retry_clears_malformed_multi_id_url_checkpoint() -> None:
    target = _job(
        status=JobStatus.FAILED,
        payload=OperationPayloadV2(
            operation_type=OperationType.INGESTION_EXECUTE,
            input={"url": "https://example.com"},
            result=_url_failure_result(content_ids=[91, 92]),
        ).model_dump(mode="json"),
    )
    target.entrypoint = OperationType.INGESTION_EXECUTE.value
    target.claim_generation = 7
    conn = _LockedRetryConnection(target, _job(status=JobStatus.QUEUED))

    await OperationService(connection=conn)._retry_locked(conn, 8123)

    reset = json.loads(conn.fetchrow.await_args_list[-1].args[1])
    assert reset["result"] is None
    assert conn.fetchval.await_count == 1
    assert "pg_locks" in conn.fetchval.await_args.args[0]


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
    cancelled.claim_generation = 7
    conn = _MutationConnection(cancelled)

    with bind_execution_claim(ExecutionClaim(job_id=8123, claim_generation=7)):
        handle = await OperationService(connection=conn).checkpoint_cancellation("8123")

    query = conn.fetchrow.await_args.args[0]
    assert "status = 'in_progress'" in query
    assert "cancel_requested" in query
    assert handle is not None
    assert handle.status is OperationStatus.CANCELLED


class _CancellationStateConnection:
    def __init__(self) -> None:
        self.job = _job(status=JobStatus.IN_PROGRESS)
        self.job.claim_generation = 7
        self.fetchrow = AsyncMock(side_effect=self._fetchrow)
        self.fetchval = AsyncMock(side_effect=self._fetchval)

    async def _fetchrow(self, query: str, *_args):
        if "SET status = 'cancelled'" not in query or not self.job.payload["cancel_requested"]:
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
        "claim_generation": job.claim_generation,
        "claim_protocol_version": job.claim_protocol_version,
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
        conn.job.payload["cancel_requested"] = True
        handle = await OperationService(connection=conn).checkpoint_cancellation(job_id)
        assert handle is not None
        assert handle.status is OperationStatus.CANCELLED

    heartbeat = AsyncMock(return_value=True)
    notification = AsyncMock()
    monkeypatch.setattr("src.queue.setup.touch_job_heartbeat", heartbeat)
    monkeypatch.setattr(worker, "_emit_job_notification", notification)
    monkeypatch.setitem(worker._handlers, entrypoint, handler)

    await worker._process_job(
        conn,  # type: ignore[arg-type]
        {
            "id": conn.job.id,
            "entrypoint": entrypoint,
            "payload": conn.job.payload,
            "claim_generation": 7,
            "claim_protocol_version": 2,
        },
    )

    assert conn.job.status is JobStatus.CANCELLED
    assert "status = 'in_progress'" in conn.fetchval.await_args.args[0]
    notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_failure_does_not_overwrite_terminal_state() -> None:
    from src.queue import worker

    conn = AsyncMock()

    await worker._fail_job(conn, 8123, 7, "handler cleanup failed")

    query = conn.fetchval.await_args.args[0]
    assert "status = 'in_progress'" in query
    assert "claim_generation = $2" in query


@pytest.mark.asyncio
async def test_resource_and_result_attachments_preserve_active_state() -> None:
    with_resource = _job(status=JobStatus.IN_PROGRESS)
    with_resource.payload["resource"] = {
        "type": "digest",
        "id": "42",
        "url": "/api/v1/digests/42",
    }
    with_resource.claim_generation = 7
    conn = _MutationConnection(with_resource)
    service = OperationService(connection=conn)

    with bind_execution_claim(ExecutionClaim(job_id=8123, claim_generation=7)):
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

    class Transaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.fetchval = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [{"root_id": 1}],
            [{"id": 1}, {"id": 2}],
            [{"root_id": 1}],
            [{"id": 2}],
            [{"id": 1}],
        ]
    )
    conn.transaction.return_value = Transaction()

    @asynccontextmanager
    async def fake_connection(_conn=None):
        yield conn

    monkeypatch.setattr(queue_setup, "_queue_connection", fake_connection)

    count = await queue_setup.cleanup_old_jobs(older_than_days=30)

    assert count == 2
    candidate_query = conn.fetch.await_args_list[0].args[0]
    assert "status NOT IN ('completed', 'failed', 'cancelled')" in candidate_query
    assert "COUNT(*) FILTER (WHERE completed_at IS NULL)" in candidate_query
    assert conn.fetchval.await_count == 1
    assert "pg_advisory_xact_lock" in conn.fetchval.await_args.args[0]
    graph_lock = conn.fetch.await_args_list[1].args[0]
    assert "FOR UPDATE OF jobs" in graph_lock
    descendant_delete = conn.fetch.await_args_list[-2].args[0]
    root_delete = conn.fetch.await_args_list[-1].args[0]
    assert "jobs.id <> graph_ids.root_id" in descendant_delete
    assert "parent_job_id IS NULL" in root_delete


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
        {
            "completed": 1,
            "failed": 1,
            "cancelled": 0,
            "total": 2,
            "parent_claim_generation": 7,
        },
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
    assert update_args[4] == 7
    assert "claim_generation = $4" in update_args[0]


@pytest.mark.asyncio
async def test_child_reconciliation_requeues_canonical_parent_for_finalization() -> None:
    """A child must not complete a canonical parent before workflow re-entry."""

    from src.queue import setup as queue_setup

    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "completed": 1,
        "failed": 0,
        "cancelled": 0,
        "total": 1,
        "parent_claim_generation": 7,
    }

    await queue_setup._reconcile_batch_parent_status(conn, 8123)

    query = conn.execute.await_args.args[0]
    assert "payload->>'operation_type' = 'summarization.run'" in query
    assert "payload->'result'->'child_operation_ids' IS NOT NULL" in query
    assert "THEN 'queued'" in query
    assert "THEN status" in query
    assert "THEN NULL" in query
    assert "claim_generation = $4" in query


def test_cancelled_job_is_terminal() -> None:
    assert _job(status=JobStatus.CANCELLED).is_terminal is True
