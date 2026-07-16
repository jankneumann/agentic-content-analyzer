"""Compatibility adapter that submits the canonical durable pipeline."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from src.contracts.workflow_models import PipelineRequest
from src.models.jobs import OperationHandle, OperationType
from src.services.operation_service import OperationService


async def run_pipeline(
    pipeline_type: str = "daily",
    date: str | None = None,
    sources: list[str] | None = None,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    *,
    continue_on_source_error: bool = True,
    operation_service: OperationService | Any | None = None,
) -> OperationHandle:
    """Normalize legacy arguments and submit one ``pipeline.run`` operation."""

    if pipeline_type not in {"daily", "weekly"}:
        raise ValueError("pipeline_type must be daily or weekly")
    if date:
        target = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=UTC)
    else:
        now = datetime.now(UTC)
        target = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if pipeline_type == "weekly":
        period_start = target - timedelta(days=target.weekday())
        period_end = period_start + timedelta(days=7)
    else:
        period_start = target
        period_end = target + timedelta(days=1)

    request = PipelineRequest(
        period=pipeline_type,
        period_start=period_start,
        period_end=period_end,
        sources=sources,
        continue_on_source_error=continue_on_source_error,
    )
    operations = operation_service or OperationService()
    handle = await operations.submit(
        OperationType.PIPELINE_RUN,
        request.model_dump(mode="json"),
    )
    if on_progress is not None:
        on_progress(
            {
                "stage": "submitted",
                "status": handle.status.value,
                "operation_id": handle.operation_id,
            }
        )
    return handle
