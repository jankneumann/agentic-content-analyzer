"""Tests for RSS ingestion with HTML-to-markdown conversion."""

from datetime import UTC
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.rss import RSSClient
from src.models.content import ContentSource


@pytest.fixture
def rss_client():
    """Create an RSS client for testing."""
    return RSSClient(timeout=10)


@pytest.fixture
def sample_feed_entry():
    """Sample feed entry for testing."""
    entry = MagicMock()
    entry.get = lambda key, default=None: {
        "title": "Test Article: Understanding AI",
        "link": "https://example.com/article/test-ai",
        "author": "John Doe",
        "id": "entry-123",
    }.get(key, default)
    entry.title = "Test Article: Understanding AI"
    entry.link = "https://example.com/article/test-ai"
    entry.author = "John Doe"
    entry.id = "entry-123"
    entry.published_parsed = (2024, 12, 26, 10, 0, 0, 3, 361, 0)
    return entry


@pytest.fixture
def sample_html_content():
    """Sample HTML content for testing extraction."""
    return """
    <html>
    <head><title>Test Article</title></head>
    <body>
    <article>
    <h1>Understanding AI in 2024</h1>
    <p>Artificial Intelligence continues to transform industries worldwide.
    This comprehensive article explores the latest developments.</p>

    <h2>Key Developments</h2>
    <ul>
    <li>Large Language Models have become more capable</li>
    <li>Multimodal AI systems are emerging</li>
    <li>AI safety research is accelerating</li>
    </ul>

    <h2>Industry Impact</h2>
    <p>From healthcare to finance, AI is reshaping how businesses operate.
    Leaders must adapt to remain competitive in this new landscape.</p>

    <p>For more information, visit <a href="https://example.com">our website</a>.</p>
    </article>
    </body>
    </html>
    """


class TestRSSClientContentParsing:
    """Tests for RSS content parsing with Trafilatura extraction."""

    def test_parse_entry_content_with_feed_html(
        self, rss_client, sample_feed_entry, sample_html_content
    ):
        """Test parsing entry using feed HTML content."""
        # Mock _extract_entry_content to return sample HTML
        with patch.object(rss_client, "_extract_entry_content", return_value=sample_html_content):
            # Mock URL extraction to fail (to test feed fallback)
            with patch(
                "src.ingestion.rss.convert_html_to_markdown",
                side_effect=lambda url=None, html=None: (
                    None if url else "# Understanding AI\n\nArtificial Intelligence content here..."
                ),
            ):
                content_data = rss_client._parse_entry_content(
                    sample_feed_entry, "Test Publication", "https://example.com/feed"
                )

        assert content_data is not None
        assert content_data.source_type == ContentSource.RSS
        assert content_data.title == "Test Article: Understanding AI"
        assert content_data.publication == "Test Publication"
        assert content_data.parser_used == "trafilatura"
        assert "extraction_method" in content_data.metadata_json
        assert content_data.metadata_json["extraction_method"] == "feed"

    def test_parse_entry_content_with_url_extraction(
        self, rss_client, sample_feed_entry, sample_html_content
    ):
        """Test parsing entry using URL-based extraction (primary method)."""
        # Mock _extract_entry_content
        with patch.object(rss_client, "_extract_entry_content", return_value=sample_html_content):
            # Mock URL extraction to succeed with good content
            url_markdown = (
                """# Full Article from URL

This is the complete article content fetched directly from the source URL.
It contains much more content than the feed excerpt would have.

## Section One
Detailed information about AI developments...

## Section Two
More comprehensive coverage of the topic with additional context.
"""
                * 3
            )  # Make it longer than 200 chars

            with patch(
                "src.ingestion.rss.convert_html_to_markdown",
                side_effect=lambda url=None, html=None: url_markdown if url else "Feed content",
            ):
                content_data = rss_client._parse_entry_content(
                    sample_feed_entry, "Test Publication", "https://example.com/feed"
                )

        assert content_data is not None
        assert content_data.parser_used == "trafilatura"
        assert content_data.metadata_json["extraction_method"] == "url"
        assert "Full Article from URL" in content_data.markdown_content

    def test_parse_entry_content_url_extraction_too_short(
        self, rss_client, sample_feed_entry, sample_html_content
    ):
        """Test fallback when URL extraction returns insufficient content."""
        with patch.object(rss_client, "_extract_entry_content", return_value=sample_html_content):
            # URL extraction returns too little content (< 200 chars)
            with patch(
                "src.ingestion.rss.convert_html_to_markdown",
                side_effect=lambda url=None, html=None: (
                    "Short" if url else "Feed content is longer and better"
                ),
            ):
                content_data = rss_client._parse_entry_content(
                    sample_feed_entry, "Test Publication", "https://example.com/feed"
                )

        # Should fall back to feed content
        assert content_data.metadata_json["extraction_method"] == "feed"
        assert "Feed content" in content_data.markdown_content

    def test_parse_entry_content_url_extraction_fails(
        self, rss_client, sample_feed_entry, sample_html_content
    ):
        """Test fallback when URL extraction raises an exception."""
        with patch.object(rss_client, "_extract_entry_content", return_value=sample_html_content):
            # URL extraction fails with exception
            def mock_convert(url=None, html=None):
                if url:
                    raise Exception("Network error")
                return "Fallback feed content"

            with patch("src.ingestion.rss.convert_html_to_markdown", side_effect=mock_convert):
                content_data = rss_client._parse_entry_content(
                    sample_feed_entry, "Test Publication", "https://example.com/feed"
                )

        # Should fall back to feed content
        assert content_data.metadata_json["extraction_method"] == "feed"

    def test_parse_entry_date_utc_aware(self, rss_client, sample_feed_entry):
        """Test that parsed dates are UTC-aware."""
        parsed_date = rss_client._parse_entry_date(sample_feed_entry)

        assert parsed_date is not None
        assert parsed_date.tzinfo == UTC
        assert parsed_date.year == 2024
        assert parsed_date.month == 12
        assert parsed_date.day == 26


class TestRSSClientExtraction:
    """Tests for RSS feed extraction methods."""

    def test_extract_entry_content_from_content_field(self, rss_client):
        """Test extraction from entry.content field."""
        entry = MagicMock()
        entry.content = [{"type": "text/html", "value": "<p>HTML content</p>"}]

        result = rss_client._extract_entry_content(entry)
        assert result == "<p>HTML content</p>"

    def test_extract_entry_content_from_summary(self, rss_client):
        """Test extraction from entry.summary field when content is empty."""

        # Use a simple object instead of MagicMock for cleaner behavior
        class FeedEntry:
            def __init__(self):
                self.content = []  # Empty content list
                self.summary_detail = None
                self.summary = "<p>Summary content</p>"
                self.description = None

        entry = FeedEntry()
        result = rss_client._extract_entry_content(entry)

        # When content is empty list, it should fall through to summary
        assert result == "<p>Summary content</p>"

    def test_generate_source_id_from_entry_id(self, rss_client):
        """Test source ID generation from entry.id."""
        entry = MagicMock()
        entry.id = "unique-entry-id-123"
        entry.link = "https://example.com/article"

        result = rss_client._generate_source_id(entry)
        assert result == "unique-entry-id-123"

    def test_generate_source_id_from_link(self, rss_client):
        """Test source ID generation from entry.link when id is missing."""
        entry = MagicMock()
        entry.id = None
        entry.link = "https://example.com/article"

        result = rss_client._generate_source_id(entry)
        assert result == "https://example.com/article"


class TestRSSIntegrationWithTrafilatura:
    """Integration tests with actual Trafilatura library."""

    @pytest.mark.integration
    def test_real_html_extraction(self, rss_client, sample_html_content):
        """Test actual HTML extraction with Trafilatura."""
        from src.parsers.html_markdown import convert_html_to_markdown

        result = convert_html_to_markdown(html=sample_html_content)

        # Trafilatura should extract meaningful content
        assert result is not None
        assert len(result) > 100
        # Content mentions AI
        assert "ai" in result.lower() or "artificial" in result.lower()
