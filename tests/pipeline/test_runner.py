from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.models.jobs import OperationType
from src.pipeline.runner import run_pipeline


@pytest.mark.asyncio
async def test_run_pipeline_submits_canonical_daily_operation() -> None:
    operations = SimpleNamespace(submit=AsyncMock(return_value=SimpleNamespace(operation_id="42")))

    handle = await run_pipeline(
        pipeline_type="daily",
        date="2026-07-13",
        sources=["rss"],
        operation_service=operations,
    )

    assert handle.operation_id == "42"
    operation_type, normalized = operations.submit.await_args.args
    assert operation_type is OperationType.PIPELINE_RUN
    assert normalized == {
        "period": "daily",
        "period_start": "2026-07-13T00:00:00Z",
        "period_end": "2026-07-14T00:00:00Z",
        "sources": ["rss"],
        "continue_on_source_error": True,
    }


@pytest.mark.asyncio
async def test_run_pipeline_weekly_period_starts_on_monday() -> None:
    operations = SimpleNamespace(submit=AsyncMock(return_value=SimpleNamespace(operation_id="43")))

    await run_pipeline(pipeline_type="weekly", date="2025-06-04", operation_service=operations)

    request = operations.submit.await_args.args[1]
    period_start = datetime.fromisoformat(request["period_start"].replace("Z", "+00:00"))
    period_end = datetime.fromisoformat(request["period_end"].replace("Z", "+00:00"))
    assert period_start == datetime(2025, 6, 2, tzinfo=UTC)
    assert period_end == period_start + timedelta(days=7)


@pytest.mark.asyncio
async def test_run_pipeline_rejects_invalid_period() -> None:
    with pytest.raises(ValueError, match="daily or weekly"):
        await run_pipeline(pipeline_type="monthly")
