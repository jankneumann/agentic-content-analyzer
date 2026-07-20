"""Tests for the long-video segments extraction + stitch path (yt-route.8)."""

from unittest.mock import AsyncMock, patch

import pytest

from src.ingestion import youtube as yt


@pytest.mark.asyncio
async def test_segments_calls_per_window_and_stitches():
    """Each planned window is processed with its offsets; results are stitched."""
    calls = []

    async def fake_extract(*, video_url, model_step, gemini_resolution, user_prompt, fps, start_offset, end_offset):
        calls.append((start_offset, end_offset))
        return f"content[{start_offset}-{end_offset}]"

    with patch.object(yt, "_extract_video_content_with_gemini", side_effect=fake_extract):
        result = await yt._extract_long_video_with_segments(
            video_url="https://www.youtube.com/watch?v=abc",
            duration_seconds=6000,
            window_seconds=2700,
            overlap_seconds=15,
            fps=0.1,
        )

    # 6000s @ 2700 window / 15 overlap -> 3 windows
    assert calls == [("0s", "2700s"), ("2685s", "5385s"), ("5370s", "6000s")]
    assert result is not None
    assert result.count("content[") == 3
    assert "segment 1/3" in result and "segment 3/3" in result


@pytest.mark.asyncio
async def test_segments_returns_none_when_all_fail():
    with patch.object(yt, "_extract_video_content_with_gemini", AsyncMock(return_value=None)):
        result = await yt._extract_long_video_with_segments(
            video_url="https://www.youtube.com/watch?v=abc",
            duration_seconds=6000,
            window_seconds=2700,
            overlap_seconds=15,
        )
    assert result is None
