"""Tests for YouTube transcript models."""

from datetime import datetime

from src.models.youtube import (
    TimestampedQuote,
    TranscriptSegment,
    YouTubeTranscript,
    format_timestamp,
    parse_timestamp,
)


class TestFormatTimestamp:
    """Tests for format_timestamp function."""

    def test_seconds_only(self):
        """Test formatting less than a minute."""
        assert format_timestamp(45) == "0:45"

    def test_minutes_and_seconds(self):
        """Test formatting minutes and seconds."""
        assert format_timestamp(125) == "2:05"
        assert format_timestamp(600) == "10:00"

    def test_hours_minutes_seconds(self):
        """Test formatting with hours."""
        assert format_timestamp(3661) == "1:01:01"
        assert format_timestamp(7200) == "2:00:00"

    def test_zero(self):
        """Test formatting zero."""
        assert format_timestamp(0) == "0:00"

    def test_float_truncation(self):
        """Test that floats are truncated."""
        assert format_timestamp(65.9) == "1:05"


class TestParseTimestamp:
    """Tests for parse_timestamp function."""

    def test_seconds_only(self):
        """Test parsing seconds only."""
        assert parse_timestamp("45") == 45.0

    def test_minutes_seconds(self):
        """Test parsing MM:SS format."""
        assert parse_timestamp("2:05") == 125.0
        assert parse_timestamp("10:00") == 600.0

    def test_hours_minutes_seconds(self):
        """Test parsing HH:MM:SS format."""
        assert parse_timestamp("1:01:01") == 3661.0
        assert parse_timestamp("2:00:00") == 7200.0


class TestTranscriptSegment:
    """Tests for TranscriptSegment model."""

    def test_basic_segment(self):
        """Test creating a basic segment."""
        seg = TranscriptSegment(text="Hello world", start=10.0, duration=5.0)

        assert seg.text == "Hello world"
        assert seg.start == 10.0
        assert seg.duration == 5.0
        assert seg.is_generated is False

    def test_end_computed(self):
        """Test end time is computed correctly."""
        seg = TranscriptSegment(text="Test", start=10.0, duration=5.0)
        assert seg.end == 15.0

    def test_start_formatted(self):
        """Test formatted start time."""
        seg = TranscriptSegment(text="Test", start=125.0, duration=5.0)
        assert seg.start_formatted == "2:05"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        seg = TranscriptSegment(text="Test", start=10.0, duration=5.0, is_generated=True)
        d = seg.to_dict()

        assert d["text"] == "Test"
        assert d["start"] == 10.0
        assert d["duration"] == 5.0
        assert d["end"] == 15.0
        assert d["is_generated"] is True


class TestYouTubeTranscript:
    """Tests for YouTubeTranscript model."""

    def test_basic_transcript(self):
        """Test creating a basic transcript."""
        transcript = YouTubeTranscript(
            video_id="abc123xyz45",
            title="Test Video",
            channel_title="Test Channel",
        )

        assert transcript.video_id == "abc123xyz45"
        assert transcript.title == "Test Video"
        assert transcript.video_url == "https://www.youtube.com/watch?v=abc123xyz45"

    def test_full_text(self):
        """Test full text concatenation."""
        transcript = YouTubeTranscript(
            video_id="abc123xyz45",
            title="Test",
            segments=[
                TranscriptSegment(text="Hello", start=0.0, duration=2.0),
                TranscriptSegment(text="world", start=2.0, duration=2.0),
            ],
        )

        assert transcript.full_text == "Hello world"

    def test_get_url_at_timestamp(self):
        """Test URL generation with timestamp."""
        transcript = YouTubeTranscript(video_id="abc123xyz45", title="Test")

        url = transcript.get_url_at_timestamp(125)
        assert url == "https://www.youtube.com/watch?v=abc123xyz45&t=125"

    def test_get_segment_at_time(self):
        """Test finding segment at time."""
        transcript = YouTubeTranscript(
            video_id="abc123xyz45",
            title="Test",
            segments=[
                TranscriptSegment(text="First", start=0.0, duration=5.0),
                TranscriptSegment(text="Second", start=5.0, duration=5.0),
                TranscriptSegment(text="Third", start=10.0, duration=5.0),
            ],
        )

        seg = transcript.get_segment_at_time(7.5)
        assert seg is not None
        assert seg.text == "Second"

        # At boundary
        seg = transcript.get_segment_at_time(5.0)
        assert seg is not None
        assert seg.text == "Second"

        # Out of range
        seg = transcript.get_segment_at_time(100.0)
        assert seg is None

    def test_get_segments_in_range(self):
        """Test getting segments in time range."""
        transcript = YouTubeTranscript(
            video_id="abc123xyz45",
            title="Test",
            segments=[
                TranscriptSegment(text="First", start=0.0, duration=5.0),
                TranscriptSegment(text="Second", start=5.0, duration=5.0),
                TranscriptSegment(text="Third", start=10.0, duration=5.0),
            ],
        )

        segments = transcript.get_segments_in_range(4.0, 12.0)
        assert len(segments) == 2
        assert segments[0].text == "Second"
        assert segments[1].text == "Third"

    def test_search_text(self):
        """Test text search."""
        transcript = YouTubeTranscript(
            video_id="abc123xyz45",
            title="Test",
            segments=[
                TranscriptSegment(text="Hello world", start=0.0, duration=5.0),
                TranscriptSegment(text="Goodbye world", start=5.0, duration=5.0),
                TranscriptSegment(text="Hello again", start=10.0, duration=5.0),
            ],
        )

        results = transcript.search_text("Hello")
        assert len(results) == 2
        assert results[0][0].text == "Hello world"
        assert "t=0" in results[0][1]
        assert results[1][0].text == "Hello again"
        assert "t=10" in results[1][1]

    def test_to_markdown(self):
        """Test markdown generation."""
        transcript = YouTubeTranscript(
            video_id="abc123xyz45",
            title="Test Video",
            channel_title="Test Channel",
            published_date=datetime(2025, 1, 10),
            segments=[
                TranscriptSegment(text="Hello world.", start=0.0, duration=5.0),
                TranscriptSegment(text="This is a test.", start=5.0, duration=5.0),
            ],
        )

        markdown = transcript.to_markdown()

        assert "# Test Video" in markdown
        assert "**Channel**: Test Channel" in markdown
        assert "**Published**: 2025-01-10" in markdown
        assert "[0:00]" in markdown
        assert "Hello world." in markdown

    def test_to_storage_dict(self):
        """Test conversion to storage dictionary."""
        transcript = YouTubeTranscript(
            video_id="abc123xyz45",
            title="Test",
            language="en",
            is_auto_generated=True,
            segments=[TranscriptSegment(text="Test", start=0.0, duration=5.0)],
        )

        d = transcript.to_storage_dict()

        assert d["type"] == "youtube_transcript"
        assert d["video_id"] == "abc123xyz45"
        assert d["language"] == "en"
        assert d["is_auto_generated"] is True
        assert d["segment_count"] == 1
        assert len(d["segments"]) == 1


class TestTimestampedQuote:
    """Tests for TimestampedQuote model."""

    def test_basic_quote(self):
        """Test creating a basic quote."""
        quote = TimestampedQuote(
            text="Important insight",
            video_id="abc123xyz45",
            video_title="Test Video",
            start_seconds=125.0,
        )

        assert quote.text == "Important insight"
        assert quote.timestamp_display == "2:05"

    def test_timestamp_url(self):
        """Test URL with timestamp."""
        quote = TimestampedQuote(
            text="Test",
            video_id="abc123xyz45",
            video_title="Test",
            start_seconds=125.0,
        )

        assert quote.timestamp_url == "https://www.youtube.com/watch?v=abc123xyz45&t=125"

    def test_embed_url(self):
        """Test embed URL."""
        quote = TimestampedQuote(
            text="Test",
            video_id="abc123xyz45",
            video_title="Test",
            start_seconds=125.0,
        )

        assert quote.embed_url == "https://www.youtube.com/embed/abc123xyz45?start=125"

    def test_to_markdown_link(self):
        """Test markdown link generation."""
        quote = TimestampedQuote(
            text="Test",
            video_id="abc123xyz45",
            video_title="Test",
            start_seconds=125.0,
        )

        link = quote.to_markdown_link()
        assert link == "[2:05](https://www.youtube.com/watch?v=abc123xyz45&t=125)"
