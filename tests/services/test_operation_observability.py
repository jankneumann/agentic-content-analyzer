"""Submission-side operation correlation tests (CORR-001/003)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import pytest

from src.contracts.operation_context import OperationContext, bind_operation_context
from src.models.jobs import JobRecord, JobStatus, OperationType
from src.services.operation_service import OperationService


class _Transaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


class _Connection:
    def __init__(self) -> None:
        self.executions: list[tuple[str, tuple[Any, ...]]] = []

    def transaction(self) -> _Transaction:
        return _Transaction()

    async def execute(self, sql: str, *args: Any) -> str:
        self.executions.append((sql, args))
        return "UPDATE 1"


def _context(*, operation_id: str = "41", parent: str | None = None) -> OperationContext:
    return OperationContext(
        schema_version=1,
        operation_id=operation_id,
        root_operation_id="41",
        parent_operation_id=parent,
        traceparent="00-11111111111111111111111111111111-2222222222222222-01",
        tracestate=None,
        trace_id="11111111111111111111111111111111",
        span_id="2222222222222222",
        claim_generation="0",
        attempt_number=None,
        entrypoint="pipeline.run",
        service_name="aca-api",
        service_instance_id="api-1",
        environment="test",
        release_revision="test-revision",
        stage="submit",
        resource_kind=None,
        resource_key=None,
    )


@pytest.mark.asyncio
async def test_submit_stores_context_in_same_outer_transaction(monkeypatch) -> None:
    connection = _Connection()
    submitted: dict[str, Any] = {}

    @asynccontextmanager
    async def queue_connection(_connection: object):
        yield connection

    async def enqueue(entrypoint: str, payload: dict[str, Any], **kwargs: Any) -> tuple[int, bool]:
        submitted.update(entrypoint=entrypoint, payload=payload, kwargs=kwargs)
        return 41, True

    async def get_job(_job_id: int, **_kwargs: Any) -> JobRecord:
        return JobRecord(
            id=41,
            entrypoint="pipeline.run",
            status=JobStatus.QUEUED,
            payload=submitted["payload"],
            priority=0,
            created_at=datetime.now(UTC),
        )

    monkeypatch.setattr(
        "src.services.operation_service.queue_setup._queue_connection", queue_connection
    )
    monkeypatch.setattr("src.services.operation_service.queue_setup.enqueue_queue_job", enqueue)
    monkeypatch.setattr("src.services.operation_service.queue_setup.get_job_status", get_job)
    monkeypatch.setattr(
        OperationService, "_new_submission_context", staticmethod(lambda *a, **k: _context())
    )
    handle = await OperationService(connection=connection).submit(
        OperationType.PIPELINE_RUN,
        {
            "period": "daily",
            "period_start": "2026-08-27T00:00:00Z",
            "period_end": "2026-08-28T00:00:00Z",
        },
        idempotency_key="pipeline:one",
    )
    assert handle.operation_id == "41"
    assert submitted["kwargs"]["conn"] is connection
    updates = [item for item in connection.executions if "submission_context" in item[0]]
    assert len(updates) == 1
    assert any("11111111111111111111111111111111" in str(value) for value in updates[0][1])


@pytest.mark.asyncio
async def test_submit_child_preserves_root_trace_and_parent_identity(monkeypatch) -> None:
    parent = _context()
    captured: dict[str, Any] = {}

    async def submit_observed(self: OperationService, **kwargs: Any) -> tuple[int, bool]:
        captured.update(kwargs)
        captured["submission_context"] = self._new_submission_context(
            operation_id=42,
            entrypoint="summarization.run",
            parent_context=kwargs["parent_context"],
            parent_job_id=41,
        )
        return 42, True

    async def no_existing(*args: Any, **kwargs: Any) -> None:
        return None

    async def get_job(_job_id: int, **_kwargs: Any) -> JobRecord:
        return JobRecord(
            id=42,
            entrypoint="summarization.run",
            status=JobStatus.QUEUED,
            payload={
                "schema_version": 2,
                "operation_type": "summarization.run",
                "input": {},
                "cancellable": True,
                "progress": 0,
                "message": "Queued",
            },
            priority=0,
            parent_job_id=41,
            created_at=datetime.now(UTC),
        )

    monkeypatch.setattr(OperationService, "_enqueue_observed", submit_observed)
    monkeypatch.setattr(
        "src.services.operation_service.queue_setup.get_child_job_by_idempotency_key", no_existing
    )
    monkeypatch.setattr("src.services.operation_service.queue_setup.get_job_status", get_job)
    with bind_operation_context(parent):
        await OperationService().submit_child(
            41, OperationType.SUMMARIZATION_RUN, {}, idempotency_key="summary:1"
        )
    child = captured["submission_context"]
    assert child.operation_id == "42" and child.root_operation_id == "41"
    assert child.parent_operation_id == "41" and child.trace_id == parent.trace_id
    assert child.span_id == parent.span_id
    assert child.traceparent == parent.traceparent


def test_root_submission_uses_active_api_span_identity() -> None:
    from opentelemetry.sdk.trace import TracerProvider

    tracer = TracerProvider().get_tracer(__name__)
    with tracer.start_as_current_span("POST /api/v1/pipelines") as span:
        context = OperationService._new_submission_context(
            operation_id=51,
            entrypoint="pipeline.run",
            parent_context=None,
            parent_job_id=None,
        )
        active = span.get_span_context()
    assert context.trace_id == format(active.trace_id, "032x")
    assert context.span_id == format(active.span_id, "016x")


def test_child_submission_carrier_is_the_active_attempt_span() -> None:
    parent = _context()
    child = OperationService._new_submission_context(
        operation_id=42,
        entrypoint="summarization.run",
        parent_context=parent,
        parent_job_id=41,
    )
    assert child.trace_id == parent.trace_id
    assert child.span_id == parent.span_id
    assert child.traceparent == parent.traceparent
