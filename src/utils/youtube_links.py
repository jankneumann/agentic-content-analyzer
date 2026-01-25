"""Utilities for YouTube URL generation and parsing."""

import re
from typing import NamedTuple

from src.models.youtube import format_timestamp


class VideoReference(NamedTuple):
    """Parsed YouTube video reference."""

    video_id: str
    timestamp: float | None


def validate_video_id_format(video_id: str) -> bool:
    """Validate that a string looks like a valid YouTube video ID.

    Checks against standard format: 11 characters, alphanumeric + underscores/hyphens.

    Args:
        video_id: The string to check

    Returns:
        True if the format is valid
    """
    return bool(re.match(r"^[a-zA-Z0-9_-]{11}$", video_id))


def extract_video_id(url: str) -> str | None:
    """Extract video ID from various YouTube URL formats.

    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/v/VIDEO_ID

    Args:
        url: YouTube URL

    Returns:
        Video ID or None if not found
    """
    patterns = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/)([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_timestamp(url: str) -> float | None:
    """Extract timestamp from YouTube URL.

    Supports:
    - ?t=125 (seconds)
    - ?t=2m5s (2 minutes 5 seconds)
    - &t=125

    Args:
        url: YouTube URL

    Returns:
        Timestamp in seconds or None
    """
    # Try seconds format
    match = re.search(r"[?&]t=(\d+)(?:s)?(?:&|$)", url)
    if match:
        return float(match.group(1))

    # Try HhMmSs format
    match = re.search(r"[?&]t=(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", url)
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        if hours or minutes or seconds:
            return float(hours * 3600 + minutes * 60 + seconds)

    return None


def parse_youtube_url(url: str) -> VideoReference | None:
    """Parse a YouTube URL into video ID and optional timestamp.

    Args:
        url: YouTube URL

    Returns:
        VideoReference with video_id and optional timestamp
    """
    video_id = extract_video_id(url)
    if not video_id:
        return None

    timestamp = extract_timestamp(url)
    return VideoReference(video_id=video_id, timestamp=timestamp)


def is_youtube_url(url: str) -> bool:
    """Check if a URL is a YouTube video URL.

    Args:
        url: URL to check

    Returns:
        True if it's a YouTube URL
    """
    return extract_video_id(url) is not None


def build_video_url(
    video_id: str,
    timestamp: float | None = None,
    short: bool = False,
) -> str:
    """Build a YouTube video URL.

    Args:
        video_id: YouTube video ID
        timestamp: Optional start time in seconds
        short: Use youtu.be short format

    Returns:
        YouTube URL
    """
    if short:
        base = f"https://youtu.be/{video_id}"
        if timestamp:
            return f"{base}?t={int(timestamp)}"
        return base
    else:
        base = f"https://www.youtube.com/watch?v={video_id}"
        if timestamp:
            return f"{base}&t={int(timestamp)}"
        return base


def build_embed_url(
    video_id: str,
    start: float | None = None,
    end: float | None = None,
    autoplay: bool = False,
) -> str:
    """Build a YouTube embed URL for iframe.

    Args:
        video_id: YouTube video ID
        start: Optional start time in seconds
        end: Optional end time in seconds
        autoplay: Auto-start video

    Returns:
        Embed URL for iframe src
    """
    params = []
    if start:
        params.append(f"start={int(start)}")
    if end:
        params.append(f"end={int(end)}")
    if autoplay:
        params.append("autoplay=1")

    base = f"https://www.youtube.com/embed/{video_id}"
    if params:
        return f"{base}?{'&'.join(params)}"
    return base


def build_embed_html(
    video_id: str,
    start: float | None = None,
    end: float | None = None,
    width: int = 560,
    height: int = 315,
    title: str = "YouTube video player",
) -> str:
    """Build complete HTML for embedded YouTube player.

    Args:
        video_id: YouTube video ID
        start: Optional start time
        end: Optional end time
        width: Player width
        height: Player height
        title: Iframe title for accessibility

    Returns:
        HTML string for embedding
    """
    embed_url = build_embed_url(video_id, start, end)

    return f"""<iframe
    width="{width}"
    height="{height}"
    src="{embed_url}"
    title="{title}"
    frameborder="0"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
    allowfullscreen
></iframe>"""


def format_quote_with_link(
    quote: str,
    video_id: str,
    timestamp: float,
    video_title: str | None = None,
) -> str:
    """Format a quote with a timestamp link for use in digests.

    Args:
        quote: The quoted text
        video_id: YouTube video ID
        timestamp: Time of quote in seconds
        video_title: Optional video title

    Returns:
        Markdown-formatted quote with link
    """
    url = build_video_url(video_id, timestamp)
    time_str = format_timestamp(timestamp)

    if video_title:
        return f'> "{quote}"\n> — [{video_title} @ {time_str}]({url})'
    else:
        return f'> "{quote}"\n> — [@ {time_str}]({url})'
