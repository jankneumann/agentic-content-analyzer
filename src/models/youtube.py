"""YouTube-specific data models for timestamped transcripts."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field


def format_timestamp(seconds: float) -> str:
    """Format seconds as human-readable timestamp.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted string (HH:MM:SS or MM:SS)
    """
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def parse_timestamp(timestamp: str) -> float:
    """Parse human-readable timestamp to seconds.

    Args:
        timestamp: String like "1:23:45" or "5:30"

    Returns:
        Time in seconds
    """
    parts = timestamp.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
        return float(hours * 3600 + minutes * 60 + seconds)
    elif len(parts) == 2:
        minutes, seconds = map(int, parts)
        return float(minutes * 60 + seconds)
    else:
        return float(parts[0])


class TranscriptSegment(BaseModel):
    """A single segment of a YouTube transcript with timestamp."""

    text: str
    start: float  # Start time in seconds
    duration: float  # Duration in seconds
    is_generated: bool = False  # True if auto-generated captions

    @computed_field
    @property
    def end(self) -> float:
        """End time in seconds."""
        return self.start + self.duration

    @computed_field
    @property
    def start_formatted(self) -> str:
        """Human-readable start time (HH:MM:SS or MM:SS)."""
        return format_timestamp(self.start)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "text": self.text,
            "start": self.start,
            "duration": self.duration,
            "end": self.end,
            "is_generated": self.is_generated,
        }


class YouTubeTranscript(BaseModel):
    """Full transcript with metadata and timestamped segments."""

    video_id: str
    title: str
    channel_title: str = ""
    published_date: datetime | None = None
    duration_seconds: float | None = None
    segments: list[TranscriptSegment] = Field(default_factory=list)
    language: str = "en"
    is_auto_generated: bool = False
    thumbnail_url: str | None = None
    playlist_id: str | None = None

    @computed_field
    @property
    def full_text(self) -> str:
        """Concatenated transcript text."""
        return " ".join(seg.text for seg in self.segments)

    @computed_field
    @property
    def video_url(self) -> str:
        """Standard YouTube video URL."""
        return f"https://www.youtube.com/watch?v={self.video_id}"

    def get_url_at_timestamp(self, seconds: float) -> str:
        """Get video URL that starts at specific timestamp."""
        return f"{self.video_url}&t={int(seconds)}"

    def get_segment_at_time(self, seconds: float) -> TranscriptSegment | None:
        """Find the transcript segment at a given timestamp."""
        for seg in self.segments:
            if seg.start <= seconds < seg.end:
                return seg
        return None

    def get_segments_in_range(self, start: float, end: float) -> list[TranscriptSegment]:
        """Get all segments within a time range."""
        return [seg for seg in self.segments if seg.start >= start and seg.start < end]

    def search_text(self, query: str) -> list[tuple[TranscriptSegment, str]]:
        """Search transcript for text matches.

        Returns list of (segment, url_with_timestamp) tuples.
        """
        query_lower = query.lower()
        results = []
        for seg in self.segments:
            if query_lower in seg.text.lower():
                url = self.get_url_at_timestamp(seg.start)
                results.append((seg, url))
        return results

    def to_markdown(self) -> str:
        """Convert transcript to markdown with timestamp links.

        Returns:
            Markdown-formatted transcript with clickable timestamps.
        """
        lines = [f"# {self.title}\n"]

        if self.channel_title:
            lines.append(f"**Channel**: {self.channel_title}\n")
        if self.published_date:
            lines.append(f"**Published**: {self.published_date.strftime('%Y-%m-%d')}\n")
        lines.append(f"**Video**: [{self.video_url}]({self.video_url})\n")
        lines.append("\n---\n\n## Transcript\n")

        # Group segments into paragraphs (every ~30 seconds or punctuation)
        current_paragraph: list[str] = []
        current_start: float | None = None

        for seg in self.segments:
            if current_start is None:
                current_start = seg.start

            current_paragraph.append(seg.text)

            # Start new paragraph on sentence end or time gap
            if seg.text.rstrip().endswith((".", "!", "?")) or seg.end - current_start > 30:
                if current_paragraph:
                    timestamp_link = f"[{format_timestamp(current_start)}]({self.get_url_at_timestamp(current_start)})"
                    paragraph_text = " ".join(current_paragraph)
                    lines.append(f"{timestamp_link} {paragraph_text}\n\n")
                    current_paragraph = []
                    current_start = None

        # Add remaining text
        if current_paragraph and current_start is not None:
            timestamp_link = (
                f"[{format_timestamp(current_start)}]({self.get_url_at_timestamp(current_start)})"
            )
            paragraph_text = " ".join(current_paragraph)
            lines.append(f"{timestamp_link} {paragraph_text}\n")

        return "".join(lines)

    def to_storage_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "type": "youtube_transcript",
            "video_id": self.video_id,
            "duration_seconds": self.duration_seconds,
            "language": self.language,
            "is_auto_generated": self.is_auto_generated,
            "thumbnail_url": self.thumbnail_url,
            "playlist_id": self.playlist_id,
            "segments": [seg.to_dict() for seg in self.segments],
            "segment_count": len(self.segments),
        }


class TimestampedQuote(BaseModel):
    """A quote from a video with timestamp for linking."""

    text: str
    video_id: str
    video_title: str
    start_seconds: float
    end_seconds: float | None = None
    context: str | None = None  # Surrounding text for context

    @computed_field
    @property
    def timestamp_url(self) -> str:
        """URL that links directly to this quote in the video."""
        return f"https://www.youtube.com/watch?v={self.video_id}&t={int(self.start_seconds)}"

    @computed_field
    @property
    def embed_url(self) -> str:
        """Embed URL for iframe with start time."""
        return f"https://www.youtube.com/embed/{self.video_id}?start={int(self.start_seconds)}"

    @computed_field
    @property
    def timestamp_display(self) -> str:
        """Human-readable timestamp."""
        return format_timestamp(self.start_seconds)

    def to_markdown_link(self) -> str:
        """Format as markdown link with timestamp."""
        return f"[{self.timestamp_display}]({self.timestamp_url})"
