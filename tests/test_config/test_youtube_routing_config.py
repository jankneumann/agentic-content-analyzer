"""Config tests for YouTube duration-routing fields (yt-route.9, yt-route.10)."""

import pytest

from src.config.models import ModelStep, get_model_config
from src.config.sources import (
    YouTubeChannelSource,
    YouTubePlaylistSource,
    YouTubeRSSSource,
)


class TestRoutingDefaults:
    def test_rss_defaults(self):
        src = YouTubeRSSSource(url="https://example.com/feed")
        assert src.long_video_threshold_seconds == 2700
        assert src.long_video_strategy == "grounding"
        assert src.video_fps == pytest.approx(0.1)
        assert src.segment_overlap_seconds == 15
        assert src.unknown_duration_strategy == "short"
        assert src.min_duration_seconds is None
        assert src.max_duration_seconds is None

    def test_playlist_and_channel_share_routing_fields(self):
        pl = YouTubePlaylistSource(id="PL123")
        ch = YouTubeChannelSource(channel_id="UC123")
        for src in (pl, ch):
            assert src.long_video_threshold_seconds == 2700
            assert src.long_video_strategy == "grounding"
            assert src.video_fps == pytest.approx(0.1)


class TestRoutingOverrides:
    def test_per_source_overrides_apply(self):
        src = YouTubePlaylistSource(
            id="PL123",
            long_video_strategy="segments",
            video_fps=0.5,
            min_duration_seconds=120,
            max_duration_seconds=7200,
            long_video_threshold_seconds=1800,
        )
        assert src.long_video_strategy == "segments"
        assert src.video_fps == pytest.approx(0.5)
        assert src.min_duration_seconds == 120
        assert src.max_duration_seconds == 7200
        assert src.long_video_threshold_seconds == 1800

    def test_fps_can_be_disabled(self):
        # video_fps=None restores Gemini's default sampling (rollback path).
        src = YouTubeRSSSource(url="https://example.com/feed", video_fps=None)
        assert src.video_fps is None


class TestModelRegistry:
    def test_youtube_processing_supports_video(self):
        mc = get_model_config()
        model = mc.get_model_for_step(ModelStep.YOUTUBE_PROCESSING)
        assert mc.get_model_info(model).supports_video is True

    def test_youtube_long_processing_resolves(self):
        mc = get_model_config()
        assert mc.get_model_for_step(ModelStep.YOUTUBE_LONG_PROCESSING)
