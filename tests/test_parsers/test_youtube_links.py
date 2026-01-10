"""Tests for YouTube URL utilities."""

from src.utils.youtube_links import (
    VideoReference,
    build_embed_html,
    build_embed_url,
    build_video_url,
    extract_timestamp,
    extract_video_id,
    format_quote_with_link,
    is_youtube_url,
    parse_youtube_url,
)


class TestExtractVideoId:
    """Tests for extract_video_id function."""

    def test_standard_url(self):
        """Test standard youtube.com URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_short_url(self):
        """Test youtu.be short URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_embed_url(self):
        """Test embed URL."""
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_with_timestamp(self):
        """Test URL with timestamp."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=125"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_with_playlist(self):
        """Test URL with playlist parameter."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLxxxxxxx"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_invalid_url(self):
        """Test invalid URL returns None."""
        assert extract_video_id("https://example.com") is None
        assert extract_video_id("not a url") is None

    def test_url_with_extra_params(self):
        """Test URL with multiple parameters."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=share&t=100"
        assert extract_video_id(url) == "dQw4w9WgXcQ"


class TestExtractTimestamp:
    """Tests for extract_timestamp function."""

    def test_seconds_format(self):
        """Test ?t=125 format."""
        url = "https://www.youtube.com/watch?v=abc&t=125"
        assert extract_timestamp(url) == 125.0

    def test_seconds_with_s_suffix(self):
        """Test ?t=125s format."""
        url = "https://www.youtube.com/watch?v=abc&t=125s"
        assert extract_timestamp(url) == 125.0

    def test_minutes_seconds_format(self):
        """Test ?t=2m5s format."""
        url = "https://www.youtube.com/watch?v=abc&t=2m5s"
        assert extract_timestamp(url) == 125.0

    def test_hours_minutes_seconds(self):
        """Test ?t=1h2m5s format."""
        url = "https://www.youtube.com/watch?v=abc&t=1h2m5s"
        assert extract_timestamp(url) == 3725.0

    def test_no_timestamp(self):
        """Test URL without timestamp."""
        url = "https://www.youtube.com/watch?v=abc"
        assert extract_timestamp(url) is None


class TestIsYouTubeUrl:
    """Tests for is_youtube_url function."""

    def test_youtube_urls(self):
        """Test valid YouTube URLs."""
        assert is_youtube_url("https://www.youtube.com/watch?v=abc123xyz45") is True
        assert is_youtube_url("https://youtu.be/abc123xyz45") is True
        assert is_youtube_url("https://youtube.com/embed/abc123xyz45") is True

    def test_non_youtube_urls(self):
        """Test non-YouTube URLs."""
        assert is_youtube_url("https://example.com/video") is False
        assert is_youtube_url("https://vimeo.com/12345") is False
        assert is_youtube_url("not a url") is False


class TestParseYouTubeUrl:
    """Tests for parse_youtube_url function."""

    def test_url_without_timestamp(self):
        """Test parsing URL without timestamp."""
        ref = parse_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert ref is not None
        assert ref.video_id == "dQw4w9WgXcQ"
        assert ref.timestamp is None

    def test_url_with_timestamp(self):
        """Test parsing URL with timestamp."""
        ref = parse_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=125")

        assert ref is not None
        assert ref.video_id == "dQw4w9WgXcQ"
        assert ref.timestamp == 125.0

    def test_invalid_url(self):
        """Test parsing invalid URL."""
        ref = parse_youtube_url("https://example.com")
        assert ref is None

    def test_returns_namedtuple(self):
        """Test that result is a VideoReference namedtuple."""
        ref = parse_youtube_url("https://youtu.be/dQw4w9WgXcQ")

        assert isinstance(ref, VideoReference)
        assert ref.video_id == "dQw4w9WgXcQ"


class TestBuildVideoUrl:
    """Tests for build_video_url function."""

    def test_basic_url(self):
        """Test building basic URL."""
        url = build_video_url("dQw4w9WgXcQ")
        assert url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def test_with_timestamp(self):
        """Test building URL with timestamp."""
        url = build_video_url("dQw4w9WgXcQ", timestamp=125)
        assert url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=125"

    def test_short_format(self):
        """Test building short URL."""
        url = build_video_url("dQw4w9WgXcQ", short=True)
        assert url == "https://youtu.be/dQw4w9WgXcQ"

    def test_short_with_timestamp(self):
        """Test building short URL with timestamp."""
        url = build_video_url("dQw4w9WgXcQ", timestamp=125, short=True)
        assert url == "https://youtu.be/dQw4w9WgXcQ?t=125"


class TestBuildEmbedUrl:
    """Tests for build_embed_url function."""

    def test_basic_embed(self):
        """Test basic embed URL."""
        url = build_embed_url("dQw4w9WgXcQ")
        assert url == "https://www.youtube.com/embed/dQw4w9WgXcQ"

    def test_with_start(self):
        """Test embed with start time."""
        url = build_embed_url("dQw4w9WgXcQ", start=125)
        assert url == "https://www.youtube.com/embed/dQw4w9WgXcQ?start=125"

    def test_with_start_and_end(self):
        """Test embed with start and end times."""
        url = build_embed_url("dQw4w9WgXcQ", start=125, end=200)
        assert "start=125" in url
        assert "end=200" in url

    def test_with_autoplay(self):
        """Test embed with autoplay."""
        url = build_embed_url("dQw4w9WgXcQ", autoplay=True)
        assert "autoplay=1" in url


class TestBuildEmbedHtml:
    """Tests for build_embed_html function."""

    def test_basic_html(self):
        """Test basic embed HTML."""
        html = build_embed_html("dQw4w9WgXcQ")

        assert "<iframe" in html
        assert "dQw4w9WgXcQ" in html
        assert 'width="560"' in html
        assert 'height="315"' in html

    def test_custom_dimensions(self):
        """Test custom dimensions."""
        html = build_embed_html("dQw4w9WgXcQ", width=800, height=450)

        assert 'width="800"' in html
        assert 'height="450"' in html

    def test_with_title(self):
        """Test custom title."""
        html = build_embed_html("dQw4w9WgXcQ", title="My Video")
        assert 'title="My Video"' in html


class TestFormatQuoteWithLink:
    """Tests for format_quote_with_link function."""

    def test_basic_quote(self):
        """Test basic quote formatting."""
        result = format_quote_with_link(
            quote="Important insight here",
            video_id="dQw4w9WgXcQ",
            timestamp=125.0,
        )

        assert '"Important insight here"' in result
        assert "t=125" in result
        assert "@ 2:05" in result

    def test_quote_with_title(self):
        """Test quote with video title."""
        result = format_quote_with_link(
            quote="Important insight",
            video_id="dQw4w9WgXcQ",
            timestamp=125.0,
            video_title="Great Talk",
        )

        assert "Great Talk @ 2:05" in result
        assert '"Important insight"' in result
