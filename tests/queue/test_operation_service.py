"""Contract tests for the durable operation projection."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock

import asyncpg
import pytest
import yaml
from jsonschema import Draft202012Validator

from src.models.jobs import (
    JobRecord,
    JobStatus,
    OperationPayloadV2,
    OperationProblem,
    OperationProblemError,
    OperationStatus,
    OperationType,
    ResourceReference,
)
from src.services.operation_service import OperationService

NOW = datetime(2026, 7, 13, 10, 0, tzinfo=UTC)
CONTRACT_MODELS = (
    Path(__file__).parents[2]
    / "openspec/changes/unify-content-workflows-agentic-surfaces/contracts/generated/models.py"
)
OPENAPI_CONTRACT = (
    Path(__file__).parents[2]
    / "openspec/changes/unify-content-workflows-agentic-surfaces/contracts/openapi/v1.yaml"
)


def _contract_models() -> ModuleType:
    spec = importlib.util.spec_from_file_location("operation_contract_models", CONTRACT_MODELS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _validate_operation_handle_contract(handle: dict) -> None:
    contract = yaml.safe_load(OPENAPI_CONTRACT.read_text())
    schema = {
        "$ref": "#/components/schemas/OperationHandle",
        "components": contract["components"],
    }
    Draft202012Validator(schema).validate(handle)


def _job(
    *,
    job_id: int = 8123,
    entrypoint: str = "digest.create",
    status: JobStatus = JobStatus.QUEUED,
    payload: dict | None = None,
    error: str | None = None,
) -> JobRecord:
    return JobRecord(
        id=job_id,
        entrypoint=entrypoint,
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
        error=error,
        retry_count=0,
        created_at=NOW,
    )


def test_version_2_payload_projects_openapi_operation_handle() -> None:
    handle = OperationService.project(_job())

    assert handle.model_dump(mode="json") == {
        "schema_version": 2,
        "operation_id": "8123",
        "operation_type": "digest.create",
        "status": "queued",
        "progress": 0,
        "message": "Queued",
        "cancellable": True,
        "retry_count": 0,
        "status_url": "/api/v1/operations/8123",
        "events_url": "/api/v1/operations/8123/events",
        "resource": None,
        "result": None,
        "problem": None,
        "created_at": "2026-07-13T10:00:00Z",
        "started_at": None,
        "completed_at": None,
    }
    _contract_models().OperationHandle.model_validate(handle.model_dump(mode="json"))


def test_completed_operation_projects_persisted_resource_and_result() -> None:
    payload = OperationPayloadV2(
        operation_type=OperationType.DIGEST_CREATE,
        input={"digest_type": "daily"},
        progress=100,
        message="Digest created",
        resource=ResourceReference(type="digest", id="42", url="/api/v1/digests/42"),
        result={"selection_fingerprint": "abc123"},
    ).model_dump(mode="json")
    job = _job(status=JobStatus.COMPLETED, payload=payload)
    job.completed_at = NOW

    handle = OperationService.project(job)

    assert handle.status is OperationStatus.COMPLETED
    assert handle.cancellable is False
    assert handle.resource == ResourceReference(type="digest", id="42", url="/api/v1/digests/42")
    assert handle.result == {"selection_fingerprint": "abc123"}


def test_failed_operation_projects_rfc7807_problem() -> None:
    handle = OperationService.project(_job(status=JobStatus.FAILED, error="provider unavailable"))
    serialized = handle.model_dump(mode="json")

    assert handle.status is OperationStatus.FAILED
    assert handle.problem is not None
    assert handle.problem.status == 500
    assert handle.problem.detail == "provider unavailable"
    assert handle.problem.code == "operation_failed"
    assert "errors" not in serialized["problem"]
    _validate_operation_handle_contract(serialized)


def test_operation_problem_errors_match_openapi_contract() -> None:
    job = _job(status=JobStatus.FAILED)
    job.payload["problem"] = OperationProblem(
        type="https://aca.rotkohl.ai/problems/validation",
        title="Validation failed",
        status=422,
        detail="The request was invalid",
        errors=[
            OperationProblemError(
                path=["input", "url"],
                code="invalid_url",
                message="Must be an absolute URL",
            )
        ],
    ).model_dump(mode="json")

    serialized = OperationService.project(job).model_dump(mode="json")

    assert serialized["problem"]["errors"] == [
        {
            "path": ["input", "url"],
            "code": "invalid_url",
            "message": "Must be an absolute URL",
        }
    ]
    _validate_operation_handle_contract(serialized)


@pytest.mark.parametrize(
    ("entrypoint", "operation_type"),
    [
        ("ingest_content", OperationType.INGESTION_EXECUTE),
        ("summarize_content", OperationType.SUMMARIZATION_RUN),
        ("run_pipeline", OperationType.PIPELINE_RUN),
        ("create_digest", OperationType.DIGEST_CREATE),
    ],
)
def test_version_1_payloads_remain_queryable(
    entrypoint: str, operation_type: OperationType
) -> None:
    job = _job(
        entrypoint=entrypoint,
        payload={"schema_version": 1, "progress": 25, "message": "Working"},
    )

    handle = OperationService.project(job)

    assert handle.schema_version == 2
    assert handle.operation_type is operation_type
    assert handle.progress == 25
    assert handle.message == "Working"


def test_progress_event_matches_shared_event_contract() -> None:
    event = OperationService.event(OperationService.project(_job()), sequence=5, occurred_at=NOW)

    assert event.model_dump(mode="json") == {
        "schema_version": 2,
        "event_id": "8123:5",
        "operation_id": "8123",
        "operation_type": "digest.create",
        "status": "queued",
        "progress": 0,
        "message": "Queued",
        "resource": None,
        "problem": None,
        "occurred_at": "2026-07-13T10:00:00Z",
    }
    _contract_models().OperationEvent.model_validate(event.model_dump(mode="json"))


@pytest.mark.asyncio
async def test_bounded_wait_returns_latest_nonterminal_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = OperationService(poll_interval=0.001)
    get_operation = AsyncMock(return_value=OperationService.project(_job()))
    monkeypatch.setattr(service, "get", get_operation)

    handle = await service.wait("8123", timeout_seconds=0.002)

    assert handle.status is OperationStatus.QUEUED
    assert get_operation.await_count >= 1


@pytest.mark.asyncio
async def test_bounded_wait_returns_terminal_handle(monkeypatch: pytest.MonkeyPatch) -> None:
    service = OperationService(poll_interval=0)
    queued = OperationService.project(_job())
    completed_job = _job(status=JobStatus.COMPLETED)
    completed_job.payload["progress"] = 100
    completed_job.payload["message"] = "Done"
    completed = OperationService.project(completed_job)
    get_operation = AsyncMock(side_effect=[queued, completed])
    monkeypatch.setattr(service, "get", get_operation)

    handle = await service.wait("8123", timeout_seconds=1)

    assert handle.status is OperationStatus.COMPLETED
    assert get_operation.await_count == 2


def _row(job_id: int, created_at: datetime) -> dict:
    job = _job(job_id=job_id)
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
        "created_at": created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }


@pytest.mark.asyncio
async def test_operation_listing_uses_opaque_keyset_cursor() -> None:
    conn = AsyncMock()
    conn.fetch.return_value = [
        _row(3, NOW),
        _row(2, NOW.replace(minute=1)),
        _row(1, NOW.replace(minute=2)),
    ]
    service = OperationService(connection=conn)

    page = await service.list(limit=2)

    assert [item.operation_id for item in page.data] == ["3", "2"]
    assert page.next_cursor is not None
    decoded_at, decoded_id = service._decode_cursor(page.next_cursor)
    assert decoded_at == NOW.replace(minute=1)
    assert decoded_id == 2
    assert "ORDER BY created_at DESC, id DESC" in conn.fetch.await_args.args[0]


def test_invalid_operation_cursor_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid operation cursor"):
        OperationService._decode_cursor("not-a-valid-cursor")


@pytest.mark.asyncio
async def test_defer_atomically_checkpoints_and_requeues_parent() -> None:
    service = OperationService()
    queued = _row(8123, NOW)
    queued["status"] = "queued"
    queued["payload"]["result"] = {"stage": "ingestion"}
    update = AsyncMock(return_value=queued)
    service._update_returning = update  # type: ignore[method-assign]

    handle = await service.defer(
        "8123",
        checkpoint={"stage": "ingestion"},
        progress=10,
        message="Waiting for source operations",
    )

    query, patch, operation_id = update.await_args.args
    assert "status = 'queued'" in query
    assert "execute_after" in query
    assert "status = 'in_progress'" in query
    assert "priority = LEAST(priority, -1)" in query
    assert operation_id == 8123
    assert __import__("json").loads(patch) == {
        "result": {"stage": "ingestion"},
        "progress": 10,
        "message": "Waiting for source operations",
    }
    assert handle.status is OperationStatus.QUEUED


@pytest.mark.asyncio
async def test_attach_completion_atomically_persists_result_resource_and_progress() -> None:
    service = OperationService()
    completed = _row(8123, NOW)
    completed["payload"].update(
        {
            "result": {"stage": "completed", "digest_id": 91},
            "resource": {
                "type": "digest",
                "id": "91",
                "url": "/api/v1/digests/91",
            },
            "progress": 100,
            "message": "Pipeline complete",
        }
    )
    update = AsyncMock(return_value=completed)
    service._update_returning = update  # type: ignore[method-assign]
    resource = ResourceReference(type="digest", id="91", url="/api/v1/digests/91")

    await service.attach_completion(
        "8123",
        result={"stage": "completed", "digest_id": 91},
        resource=resource,
        message="Pipeline complete",
    )

    _query, patch, operation_id = update.await_args.args
    assert operation_id == 8123
    assert __import__("json").loads(patch) == {
        "result": {"stage": "completed", "digest_id": 91},
        "resource": resource.model_dump(mode="json"),
        "progress": 100,
        "message": "Pipeline complete",
    }


@pytest.mark.asyncio
async def test_submit_child_reuses_terminal_parent_scoped_operation(monkeypatch) -> None:
    service = OperationService()
    existing = _job(
        job_id=44,
        entrypoint="ingestion.execute",
        status=JobStatus.COMPLETED,
        payload=OperationPayloadV2(
            operation_type=OperationType.INGESTION_EXECUTE,
            input={"kind": "rss"},
        ).model_dump(mode="json"),
    )
    lookup = AsyncMock(return_value=existing)
    enqueue = AsyncMock()
    monkeypatch.setattr(
        "src.services.operation_service.queue_setup.get_child_job_by_idempotency_key", lookup
    )
    monkeypatch.setattr("src.services.operation_service.queue_setup.enqueue_queue_job", enqueue)

    handle = await service.submit_child(
        "10",
        OperationType.INGESTION_EXECUTE,
        {"kind": "rss"},
        idempotency_key="pipeline:10:source:rss:abc",
    )

    assert handle.operation_id == "44"
    assert handle.status is OperationStatus.COMPLETED
    lookup.assert_awaited_once_with(
        10,
        "ingestion.execute",
        "parent:10:pipeline:10:source:rss:abc",
        conn=None,
    )
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_child_namespaces_caller_key_by_parent(monkeypatch) -> None:
    service = OperationService()
    lookup = AsyncMock(return_value=None)
    enqueue = AsyncMock(side_effect=[(51, True), (52, True)])
    get_operation = AsyncMock(
        side_effect=[
            OperationService.project(_job(job_id=51)),
            OperationService.project(_job(job_id=52)),
        ]
    )
    monkeypatch.setattr(
        "src.services.operation_service.queue_setup.get_child_job_by_idempotency_key", lookup
    )
    monkeypatch.setattr("src.services.operation_service.queue_setup.enqueue_queue_job", enqueue)
    monkeypatch.setattr(service, "get", get_operation)

    for parent_id in (10, 11):
        await service.submit_child(
            parent_id,
            OperationType.INGESTION_EXECUTE,
            {"kind": "rss"},
            idempotency_key="source:rss",
        )

    assert [call.kwargs["idempotency_key"] for call in enqueue.await_args_list] == [
        "parent:10:source:rss",
        "parent:11:source:rss",
    ]


@pytest.mark.asyncio
async def test_pipeline_retry_preserves_checkpoint_and_requeues_failed_children() -> None:
    service = OperationService(connection=AsyncMock())
    queued = _row(8123, NOW)
    queued["entrypoint"] = OperationType.PIPELINE_RUN.value
    queued["status"] = JobStatus.QUEUED.value
    update = AsyncMock(return_value=queued)
    service._update_returning = update  # type: ignore[method-assign]

    await service.retry("8123")

    query = update.await_args.args[0]
    assert "WITH retried_children AS" in query
    assert query.index("UPDATE pgqueuer_jobs AS child") < query.index(
        "UPDATE pgqueuer_jobs AS parent"
    )
    assert "child.parent_job_id = $2" in query
    assert "retry_child_operation_ids" in query
    assert "child.status IN ('failed', 'cancelled')" in query
    assert "child.id" in query
    assert "parent.entrypoint = 'pipeline.run'" in query
    assert "entrypoint = 'pipeline.run'" in query
    assert "jsonb_build_object('result', parent.payload->'result')" in query


@pytest.mark.asyncio
async def test_pipeline_retry_requeues_only_checkpointed_failed_or_cancelled_children(
    test_engine,
) -> None:
    parent_id = 9_008_123
    tolerated_source_id = parent_id + 1
    failed_summary_id = parent_id + 2
    cancelled_digest_id = parent_id + 3
    dsn = test_engine.url.render_as_string(hide_password=False)
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """
            INSERT INTO pgqueuer_jobs (id, entrypoint, payload, status, completed_at)
            VALUES ($1, 'pipeline.run', $2::jsonb, 'failed', NOW())
            """,
            parent_id,
            json.dumps(
                OperationPayloadV2(
                    operation_type=OperationType.PIPELINE_RUN,
                    input={"period": "daily"},
                    result={
                        "stage": "failed",
                        "retry_child_operation_ids": [failed_summary_id, cancelled_digest_id],
                    },
                ).model_dump(mode="json")
            ),
        )
        for child_id, operation_type in (
            (tolerated_source_id, OperationType.INGESTION_EXECUTE),
            (failed_summary_id, OperationType.SUMMARIZATION_RUN),
            (cancelled_digest_id, OperationType.DIGEST_CREATE),
        ):
            child_status = "cancelled" if child_id == cancelled_digest_id else "failed"
            await conn.execute(
                """
                INSERT INTO pgqueuer_jobs (
                    id, entrypoint, payload, status, parent_job_id, completed_at
                )
                VALUES (
                    $1,
                    $2,
                    $3::jsonb,
                    $4,
                    $5,
                    NOW()
                )
                """,
                child_id,
                operation_type.value,
                json.dumps(
                    OperationPayloadV2(
                        operation_type=operation_type,
                        input={},
                    ).model_dump(mode="json")
                ),
                child_status,
                parent_id,
            )

        await OperationService(connection=conn).retry(parent_id)

        statuses = {
            int(row["id"]): row["status"]
            for row in await conn.fetch(
                "SELECT id, status FROM pgqueuer_jobs WHERE id = ANY($1::bigint[])",
                [parent_id, tolerated_source_id, failed_summary_id, cancelled_digest_id],
            )
        }
        assert statuses == {
            parent_id: "queued",
            tolerated_source_id: "failed",
            failed_summary_id: "queued",
            cancelled_digest_id: "queued",
        }
    finally:
        await conn.execute(
            "DELETE FROM pgqueuer_jobs WHERE id = ANY($1::bigint[])",
            [tolerated_source_id, failed_summary_id, cancelled_digest_id, parent_id],
        )
        await conn.close()
