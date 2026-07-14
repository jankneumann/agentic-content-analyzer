"""Contract tests for the durable operation projection."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock

import pytest

from src.models.jobs import (
    JobRecord,
    JobStatus,
    OperationPayloadV2,
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


def _contract_models() -> ModuleType:
    spec = importlib.util.spec_from_file_location("operation_contract_models", CONTRACT_MODELS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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

    assert handle.status is OperationStatus.FAILED
    assert handle.problem is not None
    assert handle.problem.status == 500
    assert handle.problem.detail == "provider unavailable"
    assert handle.problem.code == "operation_failed"


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
