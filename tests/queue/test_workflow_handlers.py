"""Integration tests for canonical durable workflow queue handlers."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock

import pytest

from src.ingestion.registry import SourceRetryPolicy
from src.ingestion.result import IngestionError, IngestionResponse, IngestionWarning
from src.models.jobs import JobStatus, OperationType, ResourceReference
from src.models.query import ResolvedContentSet, SelectionPolicy, compute_selection_fingerprint
from src.queue.workflow_handlers import WorkflowExecutionError, build_workflow_handler_registry


class FakeOperations:
    def __init__(self) -> None:
        self.handle = SimpleNamespace(status=JobStatus.IN_PROGRESS, resource=None)
        self.defer = AsyncMock(side_effect=self._defer)
        self.attach_result = AsyncMock()
        self.update_progress = AsyncMock()
        self.checkpoint_cancellation = AsyncMock(return_value=None)

    async def get(self, _operation_id: int | str):
        return self.handle

    async def _defer(self, _operation_id: int | str, **_kwargs):
        self.handle.status = JobStatus.QUEUED
        return self.handle


@pytest.mark.asyncio
async def test_deferred_summarization_requeues_parent_for_concurrency_one() -> None:
    operations = FakeOperations()
    workflow = SimpleNamespace(
        execute=AsyncMock(
            return_value={
                "deferred": True,
                "content_ids": [11],
                "child_operation_ids": [101],
                "completed_ids": [],
                "failed_ids": [],
            }
        )
    )
    registry = build_workflow_handler_registry(
        operation_service=operations,
        workflow_overrides={OperationType.SUMMARIZATION_RUN: workflow},
    )

    await registry.dispatch(
        OperationType.SUMMARIZATION_RUN,
        7,
        {"content_ids": [11], "force_reprocess": False},
    )

    operations.defer.assert_awaited_once()
    assert operations.defer.await_args.kwargs["checkpoint"]["child_operation_ids"] == [101]
    assert operations.handle.status is JobStatus.QUEUED


@pytest.mark.asyncio
async def test_worker_releases_slot_after_parent_defers(monkeypatch) -> None:
    from src.queue import worker

    operations = FakeOperations()
    workflow = SimpleNamespace(
        execute=AsyncMock(
            return_value={
                "deferred": True,
                "content_ids": [11],
                "child_operation_ids": [101],
                "completed_ids": [],
                "failed_ids": [],
            }
        )
    )
    registry = build_workflow_handler_registry(
        operation_service=operations,
        workflow_overrides={OperationType.SUMMARIZATION_RUN: workflow},
    )
    entrypoint = OperationType.SUMMARIZATION_RUN.value
    monkeypatch.setitem(
        worker._handlers, entrypoint, registry.worker_handler(OperationType.SUMMARIZATION_RUN)
    )
    monkeypatch.setattr(
        "src.queue.setup.touch_job_heartbeat",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        worker,
        "_checkpoint_job_cancellation",
        AsyncMock(return_value=False),
    )
    notification = AsyncMock()
    monkeypatch.setattr(worker, "_emit_job_notification", notification)
    conn = AsyncMock()
    conn.fetchval.return_value = None

    await worker._process_job(
        conn,
        {
            "id": 20,
            "entrypoint": entrypoint,
            "claim_generation": 1,
            "claim_protocol_version": 2,
            "payload": {
                "schema_version": 2,
                "operation_type": entrypoint,
                "input": {"content_ids": [11], "force_reprocess": False},
            },
        },
    )

    operations.defer.assert_awaited_once()
    assert operations.handle.status is JobStatus.QUEUED
    assert "status = 'in_progress'" in conn.fetchval.await_args.args[0]
    notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_summarization_propagates_force_reprocess() -> None:
    operations = FakeOperations()

    async def execute(operation_id, request):
        assert operation_id == 8
        assert request.force_reprocess is True
        operations.handle.resource = ResourceReference(
            type="summary_batch", id="8", url="/api/v1/operations/8"
        )
        return {
            "deferred": False,
            "content_ids": [11],
            "child_operation_ids": [101],
            "completed_ids": [11],
            "failed_ids": [],
        }

    registry = build_workflow_handler_registry(
        operation_service=operations,
        workflow_overrides={OperationType.SUMMARIZATION_RUN: SimpleNamespace(execute=execute)},
    )

    await registry.dispatch(
        OperationType.SUMMARIZATION_RUN,
        8,
        {"content_ids": [11], "force_reprocess": True},
    )


@pytest.mark.asyncio
async def test_summary_item_handler_honors_force_from_canonical_parent(monkeypatch) -> None:
    from src.queue import worker

    prepare = Mock()
    summarize = SimpleNamespace(summarize_content=Mock(return_value=True))
    monkeypatch.setattr(worker, "_prepare_forced_summary", prepare)
    monkeypatch.setattr("src.processors.summarizer.ContentSummarizer", lambda: summarize)
    monkeypatch.setattr("src.queue.setup.update_job_progress", AsyncMock())
    monkeypatch.setattr("src.queue.setup.reconcile_batch_job_status", AsyncMock())
    worker.register_all_handlers()

    await worker._handlers["summarize_content"](19, {"content_id": 11, "force": True})

    prepare.assert_called_once_with(11)
    summarize.summarize_content.assert_called_once_with(11)


class _RateLimitError(RuntimeError):
    def __init__(self, message: str = "too many requests") -> None:
        super().__init__(message)
        self.response = SimpleNamespace(status_code=429)


@pytest.mark.asyncio
async def test_ingestion_uses_descriptor_retry_policy_for_http_429() -> None:
    operations = FakeOperations()
    command = SimpleNamespace(kind="rss")
    descriptor = SimpleNamespace(
        key="rss",
        retry_policy=SourceRetryPolicy(
            max_attempts=3,
            base_delay_seconds=0,
            max_delay_seconds=0,
        ),
    )
    source_registry = SimpleNamespace(
        parse_command=Mock(return_value=command),
        get=Mock(return_value=descriptor),
    )
    response = IngestionResponse(
        command="ingest.rss",
        source="rss",
        status="ok",
        items_ingested=1,
        details={
            "command_key": "rss",
            "resolved_route": "rss",
            "emitted_sources": ["rss"],
            "content_ids": [21],
        },
    )
    ingestion = SimpleNamespace(execute=Mock(side_effect=[_RateLimitError(), response]))
    sleep = AsyncMock()
    registry = build_workflow_handler_registry(
        operation_service=operations,
        ingestion_service=ingestion,
        source_registry=source_registry,
        sleep=sleep,
    )

    await registry.dispatch(OperationType.INGESTION_EXECUTE, 9, {"kind": "rss"})

    assert ingestion.execute.call_count == 2
    sleep.assert_awaited_once_with(0)
    operations.attach_result.assert_awaited_once_with(
        9,
        {
            "schema_version": 2,
            "command_key": "rss",
            "resolved_route": "rss",
            "emitted_sources": ["rss"],
            "status": "ok",
            "outcome": "success",
            "items_ingested": 1,
            "items_skipped": 0,
            "items_failed": 0,
            "content_ids": [21],
            "errors": [],
            "warnings": [],
            "errors_omitted": 0,
            "warnings_omitted": 0,
            "source_outcomes": [],
            "source_outcomes_omitted": 0,
            "details": {},
            "details_omitted": 4,
        },
    )


@pytest.mark.asyncio
async def test_generic_ingestion_handler_preserves_obsidian_server_version_to_service() -> None:
    from src.ingestion.registry import SOURCE_REGISTRY

    operations = FakeOperations()
    response = IngestionResponse(
        command="ingest.obsidian-vault",
        source="obsidian",
        status="ok",
        items_ingested=1,
        details={
            "command_key": "obsidian_vault",
            "resolved_route": "obsidian_vault",
            "emitted_sources": ["obsidian"],
            "content_ids": [21],
        },
    )
    ingestion = SimpleNamespace(execute=Mock(return_value=response))
    registry = build_workflow_handler_registry(
        operation_service=operations,
        ingestion_service=ingestion,
        source_registry=SOURCE_REGISTRY,
    )
    payload = {
        "kind": "obsidian_vault",
        "source_key": "src_0123456789abcdef0123",
        "configured_source_version": "a" * 64,
        "max_items": 5,
        "force_reprocess": True,
    }

    await registry.dispatch(OperationType.INGESTION_EXECUTE, 13, payload)

    command = ingestion.execute.call_args.args[0]
    assert command.kind == "obsidian_vault"
    assert command.source_key == payload["source_key"]
    assert command.configured_source_version == payload["configured_source_version"]
    assert command.max_items == 5
    assert command.force_reprocess is True


@pytest.mark.asyncio
async def test_partial_ingestion_attaches_bounded_v2_result() -> None:
    operations = FakeOperations()
    command = SimpleNamespace(kind="rss")
    descriptor = SimpleNamespace(
        key="rss",
        retry_policy=SourceRetryPolicy(max_attempts=1),
    )
    secret = "DO-NOT-PERSIST"
    response = IngestionResponse(
        command="ingest.rss",
        source="rss",
        status="partial",
        items_ingested=2,
        items_failed=1,
        errors=[
            IngestionError(
                code="feed_ingest_error",
                message=f"https://user:{secret}@private.example/feed?token={secret}",
                url=f"https://private.example/feed?token={secret}",
            )
        ],
        warnings=[
            IngestionWarning(
                code="feed_redirected",
                message=f"redirected from secret={secret}",
                redirected_to=f"https://private.example/new?token={secret}",
            )
        ],
        source_outcomes=[
            {
                "source_key": "src_0123456789abcdefabcd",
                "status": "partial",
                "items_ingested": 2,
                "items_failed": 1,
                "errors": [
                    {
                        "code": "fetch_error",
                        "message": f"credential={secret}",
                    }
                ],
                "warnings": [],
                "errors_omitted": 2,
                "warnings_omitted": 0,
            }
        ],
        source_outcomes_omitted=3,
        details={
            "command_key": "rss",
            "resolved_route": "rss",
            "emitted_sources": ["rss"],
            "content_ids": [21, 22],
            "dry_run": True,
            "query_echo": f"subject:{secret}",
        },
    )
    registry = build_workflow_handler_registry(
        operation_service=operations,
        ingestion_service=SimpleNamespace(execute=Mock(return_value=response)),
        source_registry=SimpleNamespace(
            parse_command=Mock(return_value=command),
            get=Mock(return_value=descriptor),
        ),
    )

    await registry.dispatch(OperationType.INGESTION_EXECUTE, 11, {"kind": "rss"})

    result = operations.attach_result.await_args.args[1]
    assert result["schema_version"] == 2
    assert result["status"] == "partial"
    assert result["outcome"] == "partial"
    assert result["items_ingested"] == 2
    assert result["items_failed"] == 1
    assert result["content_ids"] == [21, 22]
    assert result["errors"] == [
        {
            "code": "feed_ingest_error",
            "message": "A configured source could not be ingested",
        }
    ]
    assert result["warnings"] == [
        {
            "code": "feed_redirected",
            "message": "A configured source redirected",
        }
    ]
    assert result["source_outcomes"] == [
        {
            "source_key": "src_0123456789abcdefabcd",
            "status": "partial",
            "items_ingested": 2,
            "items_failed": 1,
            "errors": [
                {
                    "code": "fetch_error",
                    "message": "A configured source could not be fetched",
                }
            ],
            "warnings": [],
            "errors_omitted": 2,
            "warnings_omitted": 0,
        }
    ]
    assert result["source_outcomes_omitted"] == 3
    assert result["details"] == {"dry_run": True}
    assert secret not in str(result)


@pytest.mark.asyncio
async def test_failed_ingestion_attaches_bounded_v2_result_before_raising() -> None:
    operations = FakeOperations()
    command = SimpleNamespace(kind="rss")
    descriptor = SimpleNamespace(
        key="rss",
        retry_policy=SourceRetryPolicy(max_attempts=1),
    )
    secret = "DO-NOT-PERSIST"
    response = IngestionResponse(
        command="ingest.rss",
        source="rss",
        status="error",
        items_failed=1,
        errors=[
            IngestionError(
                code="fetch_error",
                message=f"credential={secret}\nforged log entry",
                url=f"https://user:{secret}@private.example/feed",
            )
        ],
        details={
            "command_key": "rss",
            "resolved_route": "rss",
            "emitted_sources": ["rss"],
            "content_ids": [],
        },
    )
    registry = build_workflow_handler_registry(
        operation_service=operations,
        ingestion_service=SimpleNamespace(execute=Mock(return_value=response)),
        source_registry=SimpleNamespace(
            parse_command=Mock(return_value=command),
            get=Mock(return_value=descriptor),
        ),
    )

    with pytest.raises(WorkflowExecutionError) as exc_info:
        await registry.dispatch(OperationType.INGESTION_EXECUTE, 12, {"kind": "rss"})

    operations.attach_result.assert_awaited_once()
    result = operations.attach_result.await_args.args[1]
    assert result["schema_version"] == 2
    assert result["status"] == "error"
    assert result["outcome"] == "failed"
    assert result["errors"] == [
        {
            "code": "fetch_error",
            "message": "A configured source could not be fetched",
        }
    ]
    assert secret not in str(result)
    assert secret not in str(exc_info.value)


@pytest.mark.asyncio
async def test_ingestion_retry_exhaustion_retains_429_diagnostics() -> None:
    operations = FakeOperations()
    secret = "DO-NOT-PERSIST"
    command = SimpleNamespace(kind="rss")
    descriptor = SimpleNamespace(
        key="rss",
        retry_policy=SourceRetryPolicy(
            max_attempts=2,
            base_delay_seconds=0,
            max_delay_seconds=0,
        ),
    )
    registry = build_workflow_handler_registry(
        operation_service=operations,
        ingestion_service=SimpleNamespace(
            execute=Mock(side_effect=_RateLimitError(f"token={secret}\nforged log entry"))
        ),
        source_registry=SimpleNamespace(
            parse_command=Mock(return_value=command),
            get=Mock(return_value=descriptor),
        ),
        sleep=AsyncMock(),
    )

    with pytest.raises(WorkflowExecutionError) as exc_info:
        await registry.dispatch(OperationType.INGESTION_EXECUTE, 10, {"kind": "rss"})

    diagnostic = str(exc_info.value)
    assert "rss" in diagnostic
    assert "HTTP 429" in diagnostic
    assert "2 attempts" in diagnostic
    assert secret not in diagnostic
    assert "forged log entry" not in diagnostic


@pytest.mark.asyncio
async def test_digest_reconstructs_and_passes_exact_resolved_set() -> None:
    operations = FakeOperations()
    start = datetime(2026, 7, 14, tzinfo=UTC)
    end = datetime(2026, 7, 15, tzinfo=UTC)
    policy = SelectionPolicy(start_date=start, end_date=end)
    resolved = ResolvedContentSet(
        policy=policy,
        fingerprint=compute_selection_fingerprint(policy, [], []),
    )

    async def execute(operation_id, request, *, resolved_set):
        assert operation_id == 11
        assert request.period_start == start
        assert resolved_set == resolved
        operations.handle.resource = ResourceReference(
            type="digest", id="42", url="/api/v1/digests/42"
        )
        return SimpleNamespace(id=42)

    registry = build_workflow_handler_registry(
        operation_service=operations,
        workflow_overrides={OperationType.DIGEST_CREATE: SimpleNamespace(execute=execute)},
    )

    await registry.dispatch(
        OperationType.DIGEST_CREATE,
        11,
        {
            "request": {
                "digest_type": "daily",
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
            },
            "resolved_set": resolved.model_dump(mode="json"),
        },
    )


@pytest.mark.asyncio
async def test_digest_accepts_flat_direct_workflow_request() -> None:
    operations = FakeOperations()
    operations.handle.resource = ResourceReference(type="digest", id="43", url="/api/v1/digests/43")
    workflow = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(id=43)))
    registry = build_workflow_handler_registry(
        operation_service=operations,
        workflow_overrides={OperationType.DIGEST_CREATE: workflow},
    )

    await registry.dispatch(
        OperationType.DIGEST_CREATE,
        14,
        {
            "digest_type": "weekly",
            "period_start": "2026-07-07T00:00:00Z",
            "period_end": "2026-07-14T00:00:00Z",
        },
    )

    assert workflow.execute.await_args.kwargs["resolved_set"] is None


@pytest.mark.asyncio
async def test_digest_rejects_tampered_serialized_resolved_set() -> None:
    operations = FakeOperations()
    start = datetime(2026, 7, 14, tzinfo=UTC)
    end = datetime(2026, 7, 15, tzinfo=UTC)
    workflow = SimpleNamespace(execute=AsyncMock())
    registry = build_workflow_handler_registry(
        operation_service=operations,
        workflow_overrides={OperationType.DIGEST_CREATE: workflow},
    )
    serialized = ResolvedContentSet(
        policy=SelectionPolicy(start_date=start, end_date=end),
        fingerprint="0" * 64,
    ).model_dump(mode="json")

    with pytest.raises(WorkflowExecutionError, match="provenance validation"):
        await registry.dispatch(
            OperationType.DIGEST_CREATE,
            13,
            {
                "digest_type": "daily",
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "resolved_set": serialized,
            },
        )

    workflow.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_pipeline_deferral_is_not_requeued_twice() -> None:
    operations = FakeOperations()

    async def execute(_operation_id, _request):
        operations.handle.status = JobStatus.QUEUED
        return {"deferred": True, "stage": "ingestion", "source_operation_ids": [101]}

    registry = build_workflow_handler_registry(
        operation_service=operations,
        workflow_overrides={OperationType.PIPELINE_RUN: SimpleNamespace(execute=execute)},
    )

    await registry.dispatch(
        OperationType.PIPELINE_RUN,
        12,
        {
            "period": "daily",
            "period_start": "2026-07-14T00:00:00Z",
            "period_end": "2026-07-15T00:00:00Z",
        },
    )

    operations.defer.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_persists_controlled_retry_exhaustion_diagnostic(monkeypatch) -> None:
    from src.queue import worker

    diagnostic = "Ingestion 'rss' failed after 3 attempts (HTTP 429): too many requests"

    async def handler(_job_id: int, _payload: dict) -> None:
        raise WorkflowExecutionError(diagnostic)

    fail_job = AsyncMock()
    notification = AsyncMock()
    monkeypatch.setattr(
        "src.queue.setup.touch_job_heartbeat",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        worker,
        "_checkpoint_job_cancellation",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(worker, "_fail_job", fail_job)
    monkeypatch.setattr(worker, "_emit_job_notification", notification)
    monkeypatch.setitem(worker._handlers, OperationType.INGESTION_EXECUTE.value, handler)

    await worker._process_job(
        AsyncMock(),
        {
            "id": 18,
            "entrypoint": OperationType.INGESTION_EXECUTE.value,
            "claim_generation": 1,
            "claim_protocol_version": 2,
            "payload": {},
        },
    )

    fail_job.assert_awaited_once_with(ANY, 18, 1, diagnostic)
    assert notification.await_args.kwargs["error"] == diagnostic


@pytest.mark.asyncio
async def test_worker_cancellation_wins_race_with_final_completion(monkeypatch) -> None:
    from src.queue import worker

    entrypoint = "test.cancel-race"

    async def handler(_job_id: int, _payload: dict) -> None:
        return None

    async def fetchval(query: str, *_args):
        assert "cancel_requested" in query
        return None

    conn = SimpleNamespace(
        fetchval=AsyncMock(side_effect=fetchval),
        fetchrow=AsyncMock(side_effect=[None, {"id": 22}]),
    )
    notification = AsyncMock()
    monkeypatch.setattr(
        "src.queue.setup.touch_job_heartbeat",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(worker, "_emit_job_notification", notification)
    monkeypatch.setitem(worker._handlers, entrypoint, handler)

    await worker._process_job(
        conn,
        {
            "id": 22,
            "entrypoint": entrypoint,
            "claim_generation": 1,
            "claim_protocol_version": 2,
            "payload": {},
        },
    )

    assert conn.fetchrow.await_count == 2
    assert "SET status = 'cancelled'" in conn.fetchrow.await_args.args[0]
    notification.assert_not_awaited()
