"""Contract tests for truthful, correlated YouTube item outcomes."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.contracts.operation_context import OperationOutcome, OperationStage
from src.ingestion.youtube import (
    YouTubeContentIngestionService,
    YouTubeItemOutcome,
    YouTubeStageFailure,
)
from src.models.youtube import TranscriptSegment, YouTubeTranscript


def _video(video_id: str) -> dict[str, object]:
    return {
        "video_id": video_id,
        "title": f"Video {video_id}",
        "channel_title": "Channel",
        "published_date": datetime(2026, 1, 1, tzinfo=UTC),
        "thumbnail_url": None,
    }


@contextmanager
def _db_session(session: MagicMock):
    yield session


def _transcript(video_id: str) -> YouTubeTranscript:
    return YouTubeTranscript(
        video_id=video_id,
        title="Transcript",
        segments=[TranscriptSegment(text="Useful content.", start=0, duration=3)],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stage", "error_code", "dependency"),
    [
        (OperationStage.TRANSCRIPT, "youtube_transcript_failed", "transcript"),
        (OperationStage.MODEL, "youtube_model_failed", "model"),
        (OperationStage.FETCH, "youtube_download_failed", "download"),
        (OperationStage.EXTRACT, "youtube_keyframe_failed", "keyframe"),
        (OperationStage.PERSIST, "youtube_persistence_failed", "persist"),
    ],
)
async def test_real_video_processor_classifies_forced_stage_exceptions(
    stage: OperationStage,
    error_code: str,
    dependency: str,
) -> None:
    service = YouTubeContentIngestionService.__new__(YouTubeContentIngestionService)
    service.client = Mock()
    service.client.get_transcript = Mock(return_value=_transcript("forcedfail1"))
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    common = (
        patch("src.ingestion.youtube.get_db", return_value=_db_session(db)),
        patch("src.ingestion.youtube._resolve_duration", new=AsyncMock(return_value=30)),
        patch("src.ingestion.youtube.settings.youtube_keyframe_extraction", False),
    )
    stage_patch = None
    if dependency == "transcript":
        service.client.get_transcript.side_effect = RuntimeError("token=secret-canary")
    elif dependency == "model":
        stage_patch = patch(
            "src.ingestion.youtube._extract_video_content_with_gemini",
            new=AsyncMock(side_effect=RuntimeError("token=secret-canary")),
        )
    elif dependency in {"download", "keyframe"}:
        stage_patch = patch("src.ingestion.youtube.settings.youtube_keyframe_extraction", True)
        service._extract_keyframes = AsyncMock(  # type: ignore[method-assign]
            side_effect=YouTubeStageFailure(
                stage=stage,
                error_code=error_code,
                retryable=dependency == "download",
                cause=RuntimeError("token=secret-canary"),
            )
        )
    else:
        db.flush.side_effect = RuntimeError("token=secret-canary")

    with common[0], common[1], common[2]:
        if stage_patch is not None:
            with stage_patch:
                outcome = await service._process_video(
                    _video("forcedfail1"),
                    "PL-real",
                    gemini_summary=dependency == "model",
                )
        else:
            outcome = await service._process_video(
                _video("forcedfail1"),
                "PL-real",
                gemini_summary=False,
            )

    assert outcome.outcome in {
        OperationOutcome.RETRYABLE_FAILURE,
        OperationOutcome.PERMANENT_FAILURE,
    }
    assert outcome.stage == stage
    assert outcome.error_code == error_code
    assert "secret-canary" not in repr(outcome)


@pytest.mark.asyncio
async def test_real_metadata_exception_is_a_failed_single_video_outcome() -> None:
    service = YouTubeContentIngestionService.__new__(YouTubeContentIngestionService)
    service.client = Mock()
    service.client.get_video_metadata.side_effect = RuntimeError("token=secret-canary")

    response = await service.ingest_video("dQw4w9WgXcQ")

    assert response.status == "error"
    assert response.items_failed == 1
    assert response.errors[0].code == "youtube_metadata_failed"
    assert "secret-canary" not in response.model_dump_json()


@pytest.mark.asyncio
async def test_playlist_counts_failures_skips_and_filters_without_stopping_batch() -> None:
    service = YouTubeContentIngestionService.__new__(YouTubeContentIngestionService)
    service.client = Mock()
    outcomes = {
        "ok": YouTubeItemOutcome.succeeded(stage=OperationStage.PERSIST),
        "duplicate": YouTubeItemOutcome.skipped_duplicate(),
        "filtered": YouTubeItemOutcome.filtered(error_code="youtube_duration_policy"),
        "transcript": YouTubeItemOutcome.failed(
            stage=OperationStage.TRANSCRIPT,
            error_code="youtube_transcript_failed",
            retryable=True,
        ),
        "metadata": YouTubeItemOutcome.failed(
            stage=OperationStage.METADATA,
            error_code="youtube_metadata_failed",
            retryable=True,
        ),
        "download": YouTubeItemOutcome.failed(
            stage=OperationStage.FETCH,
            error_code="youtube_download_failed",
            retryable=True,
        ),
        "keyframe": YouTubeItemOutcome.failed(
            stage=OperationStage.EXTRACT,
            error_code="youtube_keyframe_failed",
            retryable=False,
        ),
        "model": YouTubeItemOutcome.failed(
            stage=OperationStage.MODEL,
            error_code="youtube_model_failed",
            retryable=True,
        ),
        "persist": YouTubeItemOutcome.failed(
            stage=OperationStage.PERSIST,
            error_code="youtube_persistence_failed",
            retryable=True,
        ),
    }

    async def process(video: dict[str, object], _playlist_id: str, **_: object):
        return outcomes[str(video["video_id"])]

    service._process_video = process  # type: ignore[method-assign]
    videos = [_video(video_id) for video_id in outcomes]

    with (
        patch("src.ingestion.youtube.asyncio.to_thread", return_value=videos),
        patch("src.ingestion.youtube.settings.youtube_max_concurrent_videos", 3),
    ):
        result = await service.ingest_playlist("PL-truthful")

    assert result.items_fetched == 1
    assert result.items_failed == 6
    assert result.items_skipped == 1
    assert result.items_filtered == 1
    assert [error.code for error in result.item_errors] == [
        "youtube_transcript_failed",
        "youtube_metadata_failed",
        "youtube_download_failed",
        "youtube_keyframe_failed",
        "youtube_model_failed",
        "youtube_persistence_failed",
    ]


@pytest.mark.asyncio
async def test_single_video_processing_failure_is_not_reported_as_successful_skip() -> None:
    service = YouTubeContentIngestionService.__new__(YouTubeContentIngestionService)
    service.client = Mock()
    service.client.get_video_metadata = Mock(return_value=_video("dQw4w9WgXcQ"))
    service._process_video = AsyncMock(
        return_value=YouTubeItemOutcome.failed(
            stage=OperationStage.PERSIST,
            error_code="youtube_persistence_failed",
            retryable=True,
        )
    )

    response = await service.ingest_video("dQw4w9WgXcQ")

    assert response.status == "error"
    assert response.items_failed == 1
    assert response.items_skipped == 0
    assert response.errors[0].code == "youtube_persistence_failed"
    assert response.details["outcome"] == OperationOutcome.RETRYABLE_FAILURE
    assert response.details["stage"] == OperationStage.PERSIST
