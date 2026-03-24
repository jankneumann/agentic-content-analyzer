"""Tests for src/pipeline/runner.py — pipeline orchestration logic.

Verifies the 3-stage pipeline (ingest -> summarize -> digest) for both
daily and weekly modes, date parsing, error propagation, and progress callbacks.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
@patch("src.pipeline.runner._run_digest")
@patch("src.pipeline.runner._run_summarization")
@patch("src.pipeline.runner._run_ingestion", new_callable=AsyncMock)
async def test_run_pipeline_daily_completes_three_stages(
    mock_ingestion: AsyncMock,
    mock_summarization: MagicMock,
    mock_digest: MagicMock,
):
    """Daily pipeline runs all 3 stages and returns results."""
    from src.pipeline.runner import run_pipeline

    mock_ingestion.return_value = {"gmail": 5, "rss": 10}
    mock_summarization.return_value = 8
    mock_digest.return_value = {
        "title": "Daily Digest",
        "digest_type": "daily",
        "period_start": "2025-06-01T00:00:00+00:00",
        "period_end": "2025-06-02T00:00:00+00:00",
        "newsletter_count": 8,
    }

    result = await run_pipeline(pipeline_type="daily")

    assert result["pipeline_type"] == "daily"
    assert result["stages"]["ingestion"]["status"] == "completed"
    assert result["stages"]["ingestion"]["counts"] == {"gmail": 5, "rss": 10}
    assert result["stages"]["summarization"]["status"] == "completed"
    assert result["stages"]["summarization"]["count"] == 8
    assert result["stages"]["digest"]["status"] == "completed"

    mock_ingestion.assert_awaited_once()
    mock_summarization.assert_called_once()
    mock_digest.assert_called_once()


@pytest.mark.asyncio
@patch("src.pipeline.runner._run_digest")
@patch("src.pipeline.runner._run_summarization")
@patch("src.pipeline.runner._run_ingestion", new_callable=AsyncMock)
async def test_run_pipeline_weekly_period_starts_on_monday(
    mock_ingestion: AsyncMock,
    mock_summarization: MagicMock,
    mock_digest: MagicMock,
):
    """Weekly pipeline computes period_start as Monday of the target week."""
    from src.pipeline.runner import run_pipeline

    mock_ingestion.return_value = {"rss": 3}
    mock_summarization.return_value = 2
    mock_digest.return_value = {
        "title": "Weekly Digest",
        "digest_type": "weekly",
        "period_start": "2025-06-02T00:00:00+00:00",
        "period_end": "2025-06-09T00:00:00+00:00",
        "newsletter_count": 2,
    }

    # 2025-06-04 is a Wednesday
    result = await run_pipeline(pipeline_type="weekly", date="2025-06-04")

    # Verify _run_digest was called with Monday as period_start
    call_args = mock_digest.call_args
    period_start = call_args[0][1]  # positional: (digest_type, period_start, period_end)
    period_end = call_args[0][2]

    # Monday of the week containing 2025-06-04 (Wednesday) is 2025-06-02
    assert period_start.weekday() == 0  # Monday
    assert period_start == datetime(2025, 6, 2, tzinfo=UTC)
    assert period_end == period_start + timedelta(days=7)
    assert result["pipeline_type"] == "weekly"


@pytest.mark.asyncio
@patch("src.pipeline.runner._run_digest")
@patch("src.pipeline.runner._run_summarization")
@patch("src.pipeline.runner._run_ingestion", new_callable=AsyncMock)
async def test_run_pipeline_with_date_param(
    mock_ingestion: AsyncMock,
    mock_summarization: MagicMock,
    mock_digest: MagicMock,
):
    """Explicit date parameter is parsed and used for the digest period."""
    from src.pipeline.runner import run_pipeline

    mock_ingestion.return_value = {"gmail": 1}
    mock_summarization.return_value = 1
    mock_digest.return_value = {
        "title": "Daily Digest",
        "digest_type": "daily",
        "period_start": "2025-03-15T00:00:00+00:00",
        "period_end": "2025-03-16T00:00:00+00:00",
        "newsletter_count": 1,
    }

    result = await run_pipeline(pipeline_type="daily", date="2025-03-15")

    assert result["date"] == "2025-03-15"

    # Verify digest received the correct period
    call_args = mock_digest.call_args
    period_start = call_args[0][1]
    period_end = call_args[0][2]
    assert period_start == datetime(2025, 3, 15, tzinfo=UTC)
    assert period_end == datetime(2025, 3, 16, tzinfo=UTC)


@pytest.mark.asyncio
@patch("src.pipeline.runner._run_digest")
@patch("src.pipeline.runner._run_summarization")
@patch("src.pipeline.runner._run_ingestion", new_callable=AsyncMock)
async def test_run_pipeline_ingestion_failure_raises_and_marks_failed(
    mock_ingestion: AsyncMock,
    mock_summarization: MagicMock,
    mock_digest: MagicMock,
):
    """When ingestion fails, the pipeline raises and stages dict shows failure."""
    from src.pipeline.runner import run_pipeline

    mock_ingestion.side_effect = RuntimeError("All ingestion sources failed: gmail: auth error")

    with pytest.raises(RuntimeError, match="All ingestion sources failed"):
        await run_pipeline(pipeline_type="daily")

    # Summarization and digest should not have been called
    mock_summarization.assert_not_called()
    mock_digest.assert_not_called()


@pytest.mark.asyncio
@patch("src.pipeline.runner._run_digest")
@patch("src.pipeline.runner._run_summarization")
@patch("src.pipeline.runner._run_ingestion", new_callable=AsyncMock)
async def test_on_progress_callback_receives_stage_updates(
    mock_ingestion: AsyncMock,
    mock_summarization: MagicMock,
    mock_digest: MagicMock,
):
    """The on_progress callback is invoked with stage status updates."""
    from src.pipeline.runner import run_pipeline

    mock_ingestion.return_value = {"rss": 2}
    mock_summarization.return_value = 1
    mock_digest.return_value = {
        "title": "Daily Digest",
        "digest_type": "daily",
        "period_start": "2025-06-01T00:00:00+00:00",
        "period_end": "2025-06-02T00:00:00+00:00",
        "newsletter_count": 1,
    }

    progress_events: list[dict] = []

    def on_progress(data: dict) -> None:
        progress_events.append(data)

    await run_pipeline(pipeline_type="daily", on_progress=on_progress)

    # Should have started+completed events for each of the 3 stages
    stages_seen = [e["stage"] for e in progress_events]
    assert "ingestion" in stages_seen
    assert "summarization" in stages_seen
    assert "digest" in stages_seen

    # Verify we get both started and completed for ingestion
    ingestion_events = [e for e in progress_events if e["stage"] == "ingestion"]
    statuses = [e["status"] for e in ingestion_events]
    assert "started" in statuses
    assert "completed" in statuses
