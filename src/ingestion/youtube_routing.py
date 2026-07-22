"""Pure decision logic for the duration-routed YouTube ingestion pipeline.

This module is intentionally dependency-light (stdlib only) so the branch-heavy
routing rules — length filtering, the long-video threshold boundary, unknown-
duration fallback, and segment-window planning — can be unit-tested in isolation.
`youtube.py` consumes these helpers and remains a thin orchestrator.

See openspec/changes/redesign-youtube-ingestion-pipeline/.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

# 45 minutes — the default boundary between the short (Gemini file-uri) path and
# the long (grounding/segments) path. Routing is inclusive toward the long path.
DEFAULT_LONG_VIDEO_THRESHOLD_SECONDS = 2700
DEFAULT_VIDEO_FPS = 0.1  # ~1 frame / 10s — suited to talking-head/AI-news content
DEFAULT_SEGMENT_OVERLAP_SECONDS = 15

# YouTube contentDetails durations are ISO-8601, e.g. "PT1H2M3S", "PT45M", "PT30S".
_ISO8601_DURATION = re.compile(
    r"^P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)


class Route(StrEnum):
    """Outcome of a routing decision for a single video."""

    FILTERED = "filtered"  # dropped by the length filter — do not process
    SHORT = "short"  # Gemini file-uri with fps + timestamped segments
    LONG_GROUNDING = "long_grounding"  # URL-in-prompt + Google Search grounding
    LONG_SEGMENTS = "long_segments"  # split into windows, process each, stitch


class LongVideoStrategy(StrEnum):
    GROUNDING = "grounding"
    SEGMENTS = "segments"


class UnknownDurationStrategy(StrEnum):
    """How to route a video whose duration could not be resolved."""

    SHORT = "short"
    GROUNDING = "grounding"
    SEGMENTS = "segments"
    SKIP = "skip"


def parse_iso8601_duration(value: str | None) -> int | None:
    """Parse a YouTube ISO-8601 duration (``PT#H#M#S``) to whole seconds.

    Returns ``None`` when the value is missing or unparseable so callers can
    treat duration as "unknown" rather than silently coercing to 0.
    """
    if not value:
        return None
    match = _ISO8601_DURATION.match(value.strip())
    if not match:
        return None
    parts = {k: int(v) for k, v in match.groupdict(default="0").items()}
    return parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"]


def passes_length_filter(
    duration_seconds: int | float | None,
    min_duration_seconds: int | None,
    max_duration_seconds: int | None,
) -> bool:
    """Return True if the video is within the configured length window.

    Unknown duration (``None``) always passes — the length filter cannot make a
    decision without a duration, so the routing layer's unknown-duration strategy
    takes over instead of silently dropping the video.
    """
    if duration_seconds is None:
        return True
    below_min = min_duration_seconds is not None and duration_seconds < min_duration_seconds
    above_max = max_duration_seconds is not None and duration_seconds > max_duration_seconds
    return not (below_min or above_max)


def decide_route(
    duration_seconds: int | float | None,
    *,
    long_video_threshold_seconds: int = DEFAULT_LONG_VIDEO_THRESHOLD_SECONDS,
    long_video_strategy: str = LongVideoStrategy.GROUNDING,
    min_duration_seconds: int | None = None,
    max_duration_seconds: int | None = None,
    unknown_duration_strategy: str = UnknownDurationStrategy.SHORT,
) -> Route:
    """Decide how to process a video based on its duration and source config.

    Order of precedence:
      1. Length filter (min/max) — drops out-of-range videos.
      2. Unknown duration — routed via ``unknown_duration_strategy``.
      3. Threshold — ``duration >= threshold`` takes the long path (inclusive),
         dispatched by ``long_video_strategy``.
    """
    if not passes_length_filter(duration_seconds, min_duration_seconds, max_duration_seconds):
        return Route.FILTERED

    if duration_seconds is None:
        return _resolve_unknown(unknown_duration_strategy)

    if duration_seconds >= long_video_threshold_seconds:
        if long_video_strategy == LongVideoStrategy.SEGMENTS:
            return Route.LONG_SEGMENTS
        return Route.LONG_GROUNDING

    return Route.SHORT


def _resolve_unknown(strategy: str) -> Route:
    mapping: dict[str, Route] = {
        UnknownDurationStrategy.SHORT.value: Route.SHORT,
        UnknownDurationStrategy.GROUNDING.value: Route.LONG_GROUNDING,
        UnknownDurationStrategy.SEGMENTS.value: Route.LONG_SEGMENTS,
        UnknownDurationStrategy.SKIP.value: Route.FILTERED,
    }
    return mapping.get(strategy, Route.SHORT)


@dataclass(frozen=True)
class Segment:
    """A processing window for the long-video ``segments`` strategy."""

    index: int
    start_seconds: int
    end_seconds: int

    @property
    def start_offset(self) -> str:
        """Gemini VideoMetadata offset string, e.g. ``"0s"``."""
        return f"{self.start_seconds}s"

    @property
    def end_offset(self) -> str:
        return f"{self.end_seconds}s"


def plan_segments(
    duration_seconds: int,
    window_seconds: int = DEFAULT_LONG_VIDEO_THRESHOLD_SECONDS,
    overlap_seconds: int = DEFAULT_SEGMENT_OVERLAP_SECONDS,
) -> list[Segment]:
    """Split ``[0, duration]`` into windows of at most ``window_seconds``.

    Consecutive windows overlap by ``overlap_seconds`` so boundary context is not
    lost; the stitch step de-duplicates the overlap by timestamp. A video at or
    under one window produces a single full-length segment.
    """
    if duration_seconds <= 0:
        return []
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")
    if overlap_seconds < 0 or overlap_seconds >= window_seconds:
        raise ValueError("overlap_seconds must be in [0, window_seconds)")

    segments: list[Segment] = []
    start = 0
    index = 0
    while start < duration_seconds:
        end = min(start + window_seconds, duration_seconds)
        segments.append(Segment(index=index, start_seconds=start, end_seconds=end))
        if end >= duration_seconds:
            break
        start = end - overlap_seconds
        index += 1
    return segments
