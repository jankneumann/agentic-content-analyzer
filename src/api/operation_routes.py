"""Canonical durable-operation observation and control routes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import StreamingResponse

from src.api.dependencies import (
    operator_capability_matches,
    verify_admin_key,
    verify_operator_key,
)
from src.api.middleware.audit import audited
from src.api.workflow_dependencies import (
    get_capability_service,
    get_content_reconciliation_service,
    get_operation_service,
    get_sources_config,
)
from src.config.release_identity import release_identity
from src.config.settings import get_settings
from src.config.sources import SourcesConfig
from src.contracts.workflow_models import (
    CapabilityDocument,
    ConfiguredSourcePage,
    ContentReconciliationReport,
    ContentReconciliationRequest,
    ObservabilityHealthPage,
    OperationAttemptPage,
    OperationAttemptSummary,
    OperationHandle,
    OperationObservabilitySummary,
    OperationPage,
    Problem,
    ProcessObservabilityHealth,
    WorkflowAlertVerificationContext,
    WorkflowTerminalEventDiagnostic,
)
from src.models.jobs import OperationStatus
from src.queue import setup as queue_setup
from src.repositories.operation_observation_attempts import list_attempts
from src.repositories.telemetry_process_health import list_process_health
from src.services.capability_service import CapabilityService
from src.services.content_reconciliation_service import (
    ContentReconciliationApplyDisabledError,
    ContentReconciliationService,
)
from src.services.operation_service import OperationService
from src.services.workflow_terminal_event_service import WorkflowTerminalEventService

router = APIRouter(prefix="/api/v1", tags=["operations"])

_TRUSTED_ALERT_VERIFICATION_REVISION_SOURCE = "railway_commit_sha"


def _attempt_summary(attempt: Any) -> OperationAttemptSummary:
    return OperationAttemptSummary(
        claim_generation=str(attempt.claim_generation),
        attempt_number=str(attempt.attempt_number),
        trace_id=attempt.trace_id,
        root_span_id=attempt.root_span_id,
        langfuse_observation_id=attempt.langfuse_observation_id,
        service_name=attempt.service_name,
        service_instance_id=attempt.service_instance_id,
        environment=attempt.environment,
        release_revision=attempt.release_revision,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
        terminal_stage=attempt.terminal_stage,
        outcome=attempt.outcome,
        retryable=attempt.retryable,
        telemetry_delivery_state=attempt.telemetry_delivery_state,
        diagnostic_codes=list(attempt.diagnostic_codes),
        diagnostics_omitted=attempt.diagnostics_omitted,
    )


def _langfuse_url(trace_id: str, *, authorized: bool) -> str | None:
    base = get_settings().langfuse_public_url
    if not authorized or base is None:
        return None
    return f"{base}/trace/{trace_id}"


async def _observability_summary(
    operation_id: int,
    *,
    include_privileged_link: bool,
) -> OperationObservabilitySummary | None:
    async with queue_setup._queue_connection() as connection:
        row = await connection.fetchrow(
            "SELECT root_operation_id, trace_id FROM pgqueuer_jobs WHERE id = $1",
            operation_id,
        )
        if row is None or row["trace_id"] is None:
            return None
        trace_id = str(row["trace_id"])
        root_operation_id = int(row["root_operation_id"] or operation_id)
        attempt_count = int(
            await connection.fetchval(
                "SELECT COUNT(*) FROM operation_observation_attempts WHERE operation_id = $1",
                operation_id,
            )
            or 0
        )
        latest = None
        if attempt_count:
            latest_generation = await connection.fetchval(
                "SELECT MAX(claim_generation) FROM operation_observation_attempts "
                "WHERE operation_id = $1",
                operation_id,
            )
            latest_rows = await list_attempts(
                connection,
                operation_id,
                after_claim_generation=int(latest_generation) - 1,
                limit=1,
            )
            if latest_rows:
                latest = _attempt_summary(latest_rows[0])
        delivery = latest.telemetry_delivery_state if latest is not None else "pending"
        return OperationObservabilitySummary(
            root_operation_id=str(root_operation_id),
            trace_id=trace_id,
            attempt_count=attempt_count,
            latest_attempt=latest,
            telemetry_delivery_state=delivery,
            langfuse_url=_langfuse_url(trace_id, authorized=include_privileged_link),
        )


async def _enrich_operation_handle(
    handle: Any,
    *,
    operator_key: str | None,
) -> OperationHandle:
    projected = OperationHandle.model_validate(handle.model_dump(mode="json"))
    summary = await _observability_summary(
        int(projected.operation_id),
        include_privileged_link=operator_capability_matches(operator_key),
    )
    return projected.model_copy(update={"observability": summary})


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


@router.get(
    "/workflow-alert-verification-context",
    response_model=WorkflowAlertVerificationContext,
    dependencies=[Depends(verify_admin_key)],
)
async def get_workflow_alert_verification_context() -> WorkflowAlertVerificationContext:
    """Return positive deployment identity only for verified Railway staging."""

    revision, revision_source = release_identity()
    if (
        get_settings().environment != "staging"
        or revision_source != _TRUSTED_ALERT_VERIFICATION_REVISION_SOURCE
        or len(revision) != 40
    ):
        # Not 503: this is a permanent property of the deployment, not a
        # transient outage, so "retry later" would be a lie and the fuzz
        # contract (no 5xx for schema-valid input) would be violated. The
        # resource simply does not exist outside verified staging — the same
        # answer disabled features give elsewhere (otel_proxy_routes).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow alert verification context not available",
        )
    return WorkflowAlertVerificationContext(
        environment_class="staging",
        revision=revision,
        revision_source=_TRUSTED_ALERT_VERIFICATION_REVISION_SOURCE,
    )


@router.get(
    "/workflow-terminal-events/{event_id}",
    response_model=WorkflowTerminalEventDiagnostic,
    dependencies=[Depends(verify_admin_key)],
)
async def get_workflow_terminal_event(
    event_id: UUID,
) -> WorkflowTerminalEventDiagnostic:
    """Read one bounded, allowlist-first terminal-event diagnostic."""

    async with queue_setup._queue_connection() as connection:
        diagnostic = await WorkflowTerminalEventService(connection).get_diagnostic(event_id)
    if diagnostic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return diagnostic


@router.post(
    "/operations/reconcile-content",
    response_model=ContentReconciliationReport,
    responses={
        status.HTTP_409_CONFLICT: {
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
        # Not 503: apply stays disabled until an operator changes server policy,
        # so retrying never succeeds. The dry-run resource itself is healthy —
        # only the requested apply mode conflicts with current server state.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
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
    operator_key: Annotated[str | None, Header(alias="X-Operator-Key")] = None,
    service: OperationService = Depends(get_operation_service),
) -> OperationHandle:
    if wait_seconds:
        handle = await service.wait(operation_id, timeout_seconds=wait_seconds)
    else:
        handle = await service.get(operation_id)
    return await _enrich_operation_handle(handle, operator_key=operator_key)


@router.get(
    "/operations/{operation_id}/attempts",
    response_model=OperationAttemptPage,
    dependencies=[Depends(verify_operator_key)],
)
async def get_operation_attempts(
    operation_id: Annotated[str, Path(pattern="^[1-9][0-9]{0,18}$")],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after_claim_generation: Annotated[str | None, Query(pattern="^(0|[1-9][0-9]{0,18})$")] = None,
) -> OperationAttemptPage:
    numeric_id = int(operation_id)
    if numeric_id > 9_223_372_036_854_775_807:
        raise HTTPException(status_code=422, detail="Invalid operation identifier")
    after = int(after_claim_generation) if after_claim_generation is not None else None
    if after is not None and after > 9_223_372_036_854_775_806:
        raise HTTPException(status_code=422, detail="Invalid attempt cursor")
    async with queue_setup._queue_connection() as connection:
        row = await connection.fetchrow(
            "SELECT root_operation_id, trace_id FROM pgqueuer_jobs WHERE id = $1",
            numeric_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Not found")
        root_id = int(row["root_operation_id"] or numeric_id)
        attempts = await list_attempts(
            connection,
            numeric_id,
            after_claim_generation=after,
            limit=limit,
        )
        remaining = int(
            await connection.fetchval(
                "SELECT COUNT(*) FROM operation_observation_attempts "
                "WHERE operation_id = $1 AND claim_generation > $2",
                numeric_id,
                -1 if after is None else after,
            )
            or 0
        )
    omitted = max(0, remaining - len(attempts))
    next_cursor = str(attempts[-1].claim_generation) if omitted and attempts else None
    return OperationAttemptPage(
        operation_id=operation_id,
        root_operation_id=str(root_id),
        attempts=[_attempt_summary(attempt) for attempt in attempts],
        attempts_omitted=omitted,
        next_after_claim_generation=next_cursor,
    )


@router.get(
    "/status/observability",
    response_model=ObservabilityHealthPage,
    dependencies=[Depends(verify_operator_key)],
)
async def get_observability_health(response: Response) -> ObservabilityHealthPage:
    settings = get_settings()
    now = datetime.now(UTC)
    stale_after = settings.telemetry_heartbeat_interval_seconds * 3
    async with queue_setup._queue_connection() as connection:
        rows, omitted = await list_process_health(
            connection,
            settings.environment,
            now=now,
            limit=1000,
        )
    processes: list[ProcessObservabilityHealth] = []
    degraded = False
    for row in rows:
        heartbeat_age = max(0, int((now - row.last_heartbeat_at).total_seconds()))
        status_value = "stale" if heartbeat_age > stale_after else row.status
        if row.required_observability and (
            not row.initialized or status_value != "healthy" or row.dropped_count > 0
        ):
            degraded = True
        processes.append(
            ProcessObservabilityHealth(
                required=row.required_observability,
                initialized=row.initialized,
                status=status_value,
                service_name=row.service_name,
                service_instance_id=row.service_instance_id,
                environment=row.environment,
                release_revision=row.release_revision,
                lifecycle_kind=row.lifecycle_kind,
                expires_at=row.expires_at,
                export_target=row.export_target,
                last_heartbeat_at=row.last_heartbeat_at,
                last_success_at=row.last_success_at,
                last_success_age_seconds=(
                    max(0, int((now - row.last_success_at).total_seconds()))
                    if row.last_success_at is not None
                    else None
                ),
                last_error_at=row.last_error_at,
                last_error_age_seconds=(
                    max(0, int((now - row.last_error_at).total_seconds()))
                    if row.last_error_at is not None
                    else None
                ),
                last_error_code=row.last_error_code,
                buffered_count=row.buffered_count,
                buffer_capacity=row.buffer_capacity,
                dropped_count=row.dropped_count,
                last_flush_at=row.last_flush_at,
                last_flush_succeeded=row.last_flush_succeeded,
            )
        )
    if degraded:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ObservabilityHealthPage(
        status="degraded" if degraded else "healthy",
        generated_at=now,
        stale_after_seconds=stale_after,
        processes_omitted=omitted,
        processes=processes,
    )


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
    initial = await _enrich_operation_handle(await service.get(operation_id), operator_key=None)
    sequence = _event_sequence(last_event_id, operation_id)

    async def events() -> AsyncIterator[str]:
        nonlocal initial, sequence
        previous: tuple[object, ...] | None = None
        while not await request.is_disconnected():
            snapshot = _snapshot_key(initial)
            if snapshot != previous:
                event = service.event(initial, sequence=sequence)
                payload = event.model_dump(mode="json")
                if initial.observability is not None:
                    payload["trace_id"] = initial.observability.trace_id
                    payload["root_operation_id"] = initial.observability.root_operation_id
                    payload["telemetry_delivery_state"] = (
                        initial.observability.telemetry_delivery_state
                    )
                yield (
                    f"id: {event.event_id}\nevent: progress\ndata: "
                    f"{json.dumps(payload, separators=(',', ':'))}\n\n"
                )
                sequence += 1
                previous = snapshot
            if str(initial.status) in {"completed", "failed", "cancelled"}:
                return
            await asyncio.sleep(0.5)
            initial = await _enrich_operation_handle(
                await service.get(operation_id), operator_key=None
            )

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
        json.dumps(
            handle.observability.model_dump(mode="json")
            if handle.observability is not None
            else None,
            sort_keys=True,
        ),
    )
