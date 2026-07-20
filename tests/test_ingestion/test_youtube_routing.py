"""Unit tests for the pure duration-routing logic.

Covers spec scenarios yt-route.1 (length filter), yt-route.5/6 (routing +
inclusive boundary), yt-route.7/8 (long strategies), and segment planning.
See openspec/changes/redesign-youtube-ingestion-pipeline/.
"""

import pytest

from src.ingestion.youtube_routing import (
    Route,
    Segment,
    decide_route,
    parse_iso8601_duration,
    passes_length_filter,
    plan_segments,
)


class TestParseIso8601Duration:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("PT30S", 30),
            ("PT45M", 2700),
            ("PT1H", 3600),
            ("PT1H2M3S", 3723),
            ("P1DT1H", 90000),
            ("", None),
            (None, None),
            ("garbage", None),
            ("45:00", None),
        ],
    )
    def test_parse(self, value, expected):
        assert parse_iso8601_duration(value) == expected


class TestLengthFilter:
    def test_within_window_passes(self):
        assert passes_length_filter(600, 120, 7200) is True

    def test_too_short_fails(self):
        assert passes_length_filter(30, 120, 7200) is False

    def test_too_long_fails(self):
        assert passes_length_filter(8000, 120, 7200) is False

    def test_unknown_duration_passes(self):
        # Unknown duration can't be filtered; routing's unknown strategy decides.
        assert passes_length_filter(None, 120, 7200) is True

    def test_no_bounds_passes(self):
        assert passes_length_filter(99999, None, None) is True


class TestDecideRoute:
    def test_short_video_routes_short(self):
        assert decide_route(600, long_video_threshold_seconds=2700) == Route.SHORT

    def test_boundary_is_inclusive_toward_long(self):
        # yt-route.6: exactly threshold -> long; one below -> short.
        assert decide_route(2700, long_video_threshold_seconds=2700) == Route.LONG_GROUNDING
        assert decide_route(2699, long_video_threshold_seconds=2700) == Route.SHORT

    def test_long_defaults_to_grounding(self):
        assert decide_route(5400, long_video_strategy="grounding") == Route.LONG_GROUNDING

    def test_long_segments_when_configured(self):
        assert decide_route(5400, long_video_strategy="segments") == Route.LONG_SEGMENTS

    def test_length_filter_takes_precedence(self):
        assert decide_route(30, min_duration_seconds=120) == Route.FILTERED
        assert decide_route(9000, max_duration_seconds=7200) == Route.FILTERED

    @pytest.mark.parametrize(
        ("strategy", "expected"),
        [
            ("short", Route.SHORT),
            ("grounding", Route.LONG_GROUNDING),
            ("segments", Route.LONG_SEGMENTS),
            ("skip", Route.FILTERED),
        ],
    )
    def test_unknown_duration_strategy(self, strategy, expected):
        assert decide_route(None, unknown_duration_strategy=strategy) == expected


class TestPlanSegments:
    def test_single_window_when_under_threshold(self):
        segs = plan_segments(2000, window_seconds=2700, overlap_seconds=15)
        assert segs == [Segment(index=0, start_seconds=0, end_seconds=2000)]

    def test_splits_with_overlap(self):
        segs = plan_segments(6000, window_seconds=2700, overlap_seconds=15)
        # 0-2700, then start = 2700-15 = 2685 -> 2685-5385, then 5370-6000
        assert [(s.start_seconds, s.end_seconds) for s in segs] == [
            (0, 2700),
            (2685, 5385),
            (5370, 6000),
        ]
        assert segs[-1].end_seconds == 6000  # always covers the full video

    def test_offsets_are_duration_strings(self):
        seg = plan_segments(3000, window_seconds=2700, overlap_seconds=15)[0]
        assert seg.start_offset == "0s"
        assert seg.end_offset == "2700s"

    def test_zero_duration_yields_nothing(self):
        assert plan_segments(0) == []

    def test_invalid_overlap_raises(self):
        with pytest.raises(ValueError):
            plan_segments(6000, window_seconds=2700, overlap_seconds=2700)
