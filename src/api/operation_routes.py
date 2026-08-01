"""Canonical durable-operation observation and control routes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from src.api.middleware.audit import audited
from src.api.workflow_dependencies import (
    get_capability_service,
    get_content_reconciliation_service,
    get_operation_service,
    get_sources_config,
)
from src.config.sources import SourcesConfig
from src.contracts.workflow_models import (
    CapabilityDocument,
    ConfiguredSourcePage,
    ContentReconciliationReport,
    ContentReconciliationRequest,
    OperationHandle,
    OperationPage,
    Problem,
)
from src.models.jobs import OperationStatus
from src.services.capability_service import CapabilityService
from src.services.content_reconciliation_service import (
    ContentReconciliationApplyDisabledError,
    ContentReconciliationService,
)
from src.services.operation_service import OperationService

router = APIRouter(prefix="/api/v1", tags=["operations"])


@router.get("/capabilities", response_model=CapabilityDocument)
async def get_capabilities(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    service: CapabilityService = Depends(get_capability_service),
) -> CapabilityDocument:
    return service.get_capabilities(limit=limit, cursor=cursor)


@router.get("/configured-sources", response_model=ConfiguredSourcePage)
async def list_configured_sources(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    service: CapabilityService = Depends(get_capability_service),
    config: SourcesConfig = Depends(get_sources_config),
) -> ConfiguredSourcePage:
    return service.list_configured_sources(config, limit=limit, cursor=cursor)


@router.get("/operations", response_model=OperationPage)
async def list_operations(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    status: OperationStatus | None = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationPage:
    page = await service.list(limit=limit, cursor=cursor, status=status)
    return OperationPage.model_validate(page.model_dump(mode="json"))


@router.post(
    "/operations/reconcile-content",
    response_model=ContentReconciliationReport,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Reconciliation apply is disabled by server policy",
            "content": {"application/problem+json": {"schema": Problem.model_json_schema()}},
        }
    },
)
@audited(operation="operations.reconcile_content")
async def reconcile_content(
    body: ContentReconciliationRequest,
    request: Request,
    service: ContentReconciliationService = Depends(get_content_reconciliation_service),
) -> ContentReconciliationReport:
    """Preview or apply exactly one bounded reconciliation page."""
    request.state.audit_notes = {"mode": "apply" if body.apply else "dry_run"}
    try:
        report = await service.reconcile(body)
    except ContentReconciliationApplyDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Content reconciliation apply is disabled",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid reconciliation request",
        ) from exc
    request.state.audit_notes.update(
        {
            "run_id": str(report.run_id),
            "scanned": report.scanned,
            "reported": report.reported,
            "counts": report.counts.model_dump(mode="json"),
        }
    )
    return report


@router.get("/operations/{operation_id}", response_model=OperationHandle)
async def get_operation(
    operation_id: str,
    wait_seconds: Annotated[int, Query(ge=0, le=30)] = 0,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    if wait_seconds:
        handle = await service.wait(operation_id, timeout_seconds=wait_seconds)
    else:
        handle = await service.get(operation_id)
    return OperationHandle.model_validate(handle.model_dump(mode="json"))


@router.post(
    "/operations/{operation_id}/retry",
    response_model=OperationHandle,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_operation(
    operation_id: str,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    handle = await service.retry(operation_id)
    return OperationHandle.model_validate(handle.model_dump(mode="json"))


@router.post(
    "/operations/{operation_id}/cancel",
    response_model=OperationHandle,
    status_code=status.HTTP_202_ACCEPTED,
)
async def cancel_operation(
    operation_id: str,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    handle = await service.cancel(operation_id)
    return OperationHandle.model_validate(handle.model_dump(mode="json"))


@router.get("/operations/{operation_id}/events")
async def stream_operation_events(
    operation_id: str,
    request: Request,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    service: OperationService = Depends(get_operation_service),
) -> StreamingResponse:
    initial = await service.get(operation_id)
    sequence = _event_sequence(last_event_id, operation_id)

    async def events() -> AsyncIterator[str]:
        nonlocal initial, sequence
        previous: tuple[object, ...] | None = None
        while not await request.is_disconnected():
            snapshot = _snapshot_key(initial)
            if snapshot != previous:
                event = service.event(initial, sequence=sequence)
                yield (
                    f"id: {event.event_id}\nevent: progress\ndata: {event.model_dump_json()}\n\n"
                )
                sequence += 1
                previous = snapshot
            if str(initial.status) in {"completed", "failed", "cancelled"}:
                return
            await asyncio.sleep(0.5)
            initial = await service.get(operation_id)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _event_sequence(last_event_id: str | None, operation_id: str) -> int:
    if not last_event_id:
        return 0
    try:
        event_operation_id, raw_sequence = last_event_id.rsplit(":", 1)
        if event_operation_id != operation_id:
            return 0
        return max(int(raw_sequence) + 1, 0)
    except ValueError:
        return 0


def _snapshot_key(handle: OperationHandle) -> tuple[object, ...]:
    return (
        handle.status,
        handle.progress,
        handle.message,
        json.dumps(handle.result, sort_keys=True),
        json.dumps(handle.resource.model_dump(mode="json") if handle.resource else None),
        json.dumps(handle.problem.model_dump(mode="json") if handle.problem else None),
    )
