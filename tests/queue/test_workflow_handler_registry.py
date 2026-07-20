"""Contract tests for canonical operation handler registration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.models.jobs import JobStatus, OperationType, ResourceReference
from src.queue.workflow_handlers import (
    WorkflowHandlerOutcome,
    WorkflowHandlerRegistry,
    WorkflowResourceError,
    build_workflow_handler_registry,
)


def test_default_registry_covers_every_declared_operation_type() -> None:
    registry = build_workflow_handler_registry(operation_service=AsyncMock())

    assert registry.operation_types == frozenset(OperationType)
    registry.validate_complete()


def test_registry_rejects_duplicate_operation_type() -> None:
    registry = WorkflowHandlerRegistry(operation_service=AsyncMock())

    async def handler(_operation_id: int, _payload: dict) -> WorkflowHandlerOutcome:
        return WorkflowHandlerOutcome()

    registry.register(OperationType.INGESTION_EXECUTE, handler)

    with pytest.raises(ValueError, match="already has a handler"):
        registry.register(OperationType.INGESTION_EXECUTE, handler)


def test_registry_fails_completeness_validation_with_missing_types() -> None:
    registry = WorkflowHandlerRegistry(operation_service=AsyncMock())

    with pytest.raises(ValueError, match="Missing workflow handlers") as exc_info:
        registry.validate_complete()

    for operation_type in OperationType:
        assert operation_type.value in str(exc_info.value)


@pytest.mark.asyncio
async def test_resource_producing_handler_requires_attached_matching_resource() -> None:
    operations = SimpleNamespace(
        checkpoint_cancellation=AsyncMock(return_value=None),
        get=AsyncMock(
            return_value=SimpleNamespace(
                status=JobStatus.IN_PROGRESS,
                resource=ResourceReference(type="digest", id="41", url="/api/v1/digests/41"),
            )
        ),
    )
    registry = WorkflowHandlerRegistry(operation_service=operations)

    async def handler(_operation_id: int, _payload: dict) -> WorkflowHandlerOutcome:
        return WorkflowHandlerOutcome(resource_id="42")

    registry.register(OperationType.DIGEST_CREATE, handler, resource_type="digest")

    with pytest.raises(WorkflowResourceError, match="expected digest/42"):
        await registry.dispatch(OperationType.DIGEST_CREATE, 7, {})


@pytest.mark.asyncio
async def test_resource_producing_handler_accepts_matching_resource() -> None:
    resource = ResourceReference(type="digest", id="42", url="/api/v1/digests/42")
    operations = SimpleNamespace(
        checkpoint_cancellation=AsyncMock(return_value=None),
        get=AsyncMock(
            return_value=SimpleNamespace(status=JobStatus.IN_PROGRESS, resource=resource)
        ),
    )
    registry = WorkflowHandlerRegistry(operation_service=operations)

    async def handler(_operation_id: int, _payload: dict) -> WorkflowHandlerOutcome:
        return WorkflowHandlerOutcome(resource_id="42")

    registry.register(OperationType.DIGEST_CREATE, handler, resource_type="digest")

    await registry.dispatch(OperationType.DIGEST_CREATE, 7, {})


@pytest.mark.asyncio
async def test_worker_handler_unwraps_schema_v2_input() -> None:
    operations = SimpleNamespace(
        checkpoint_cancellation=AsyncMock(return_value=None),
        get=AsyncMock(return_value=SimpleNamespace(status=JobStatus.IN_PROGRESS, resource=None)),
    )
    registry = WorkflowHandlerRegistry(operation_service=operations)
    seen = AsyncMock(return_value=WorkflowHandlerOutcome())
    registry.register(OperationType.INGESTION_EXECUTE, seen)

    await registry.worker_handler(OperationType.INGESTION_EXECUTE)(
        17,
        {
            "schema_version": 2,
            "operation_type": "ingestion.execute",
            "input": {"kind": "rss", "force_reprocess": True},
            "progress": 0,
            "message": "Queued",
            "cancel_requested": False,
            "cancellable": True,
            "resource": None,
            "result": None,
            "problem": None,
        },
    )

    seen.assert_awaited_once_with(17, {"kind": "rss", "force_reprocess": True})


def test_worker_registration_exposes_all_canonical_entrypoints() -> None:
    from src.queue.worker import _handlers, register_all_handlers

    register_all_handlers()

    assert {operation_type.value for operation_type in OperationType}.issubset(_handlers)
