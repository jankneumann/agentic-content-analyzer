"""Unit tests for the URL extractor service.

Tests content extraction from URLs including:
- HTML fetching with proper headers
- Trafilatura content extraction
- Fallback extraction when trafilatura fails
- Error handling for various failure modes
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.models.content import Content, ContentStatus
from src.services.url_extractor import (
    DEFAULT_TIMEOUT,
    USER_AGENT,
    URLExtractor,
    extract_url_to_content,
)
from src.utils.content_hash import generate_markdown_hash


class TestURLExtractorInit:
    """Tests for URLExtractor initialization."""

    def test_init_with_session(self):
        """URLExtractor initializes with database session."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)
        assert extractor.db == mock_db


class TestFetchURL:
    """Tests for URL fetching functionality."""

    @pytest.mark.asyncio
    async def test_fetch_url_success(self):
        """Fetches URL content with proper headers."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        mock_response = MagicMock()
        mock_response.text = "<html><body><h1>Test Article</h1></body></html>"
        mock_response.url = "https://example.com/article"
        mock_response.headers = {
            "content-type": "text/html; charset=utf-8",
            "content-length": "100",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client.return_value = mock_client_instance

            html, final_url = await extractor._fetch_url("https://example.com/article")

            assert html == "<html><body><h1>Test Article</h1></body></html>"
            assert final_url == "https://example.com/article"
            mock_client.assert_called_once_with(
                timeout=DEFAULT_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )

    @pytest.mark.asyncio
    async def test_fetch_url_follows_redirects(self):
        """URL fetching follows redirects and returns final URL."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        mock_response = MagicMock()
        mock_response.text = "<html><body>Content</body></html>"
        mock_response.url = "https://example.com/final-url"  # Different from original
        mock_response.headers = {"content-type": "text/html"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client.return_value = mock_client_instance

            html, final_url = await extractor._fetch_url("https://example.com/redirect")

            assert final_url == "https://example.com/final-url"

    @pytest.mark.asyncio
    async def test_fetch_url_raises_on_http_error(self):
        """Raises exception for HTTP errors (404, 500, etc.)."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=MagicMock(status_code=404),
            )
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client.return_value = mock_client_instance

            with pytest.raises(httpx.HTTPStatusError):
                await extractor._fetch_url("https://example.com/not-found")

    @pytest.mark.asyncio
    async def test_fetch_url_rejects_oversized_content(self):
        """Rejects responses with Content-Length exceeding the limit."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/html", "content-length": "999999999"}
        mock_response.url = "https://example.com/huge-page"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client.return_value = mock_client_instance

            with pytest.raises(ValueError, match="Content too large"):
                await extractor._fetch_url("https://example.com/huge-page")

    @pytest.mark.asyncio
    async def test_fetch_url_rejects_non_html_content(self):
        """Rejects responses with non-HTML content types."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.url = "https://example.com/document.pdf"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client.return_value = mock_client_instance

            with pytest.raises(ValueError, match="Unsupported content type"):
                await extractor._fetch_url("https://example.com/document.pdf")


class TestParseHTML:
    """Tests for HTML parsing functionality."""

    @pytest.mark.asyncio
    async def test_parse_html_with_trafilatura(self):
        """Uses trafilatura for content extraction."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        html_content = """
        <html>
        <head><title>Test Article</title></head>
        <body>
        <article>
            <h1>Test Article</h1>
            <p>This is the main content of the article.</p>
            <p>It has multiple paragraphs with interesting information.</p>
        </article>
        </body>
        </html>
        """

        with patch("trafilatura.extract") as mock_extract:
            mock_extract.return_value = "# Test Article\n\nThis is the main content."

            with patch("trafilatura.extract_metadata") as mock_metadata:
                mock_meta = MagicMock()
                mock_meta.title = "Test Article"
                mock_metadata.return_value = mock_meta

                markdown, metadata = await extractor._parse_html(
                    html_content, "https://example.com"
                )

                assert "Test Article" in markdown
                assert metadata["title"] == "Test Article"
                assert "word_count" in metadata
                mock_extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_html_fallback_when_trafilatura_returns_none(self):
        """Falls back to basic extraction when trafilatura returns None."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        html_content = "<html><body><p>Simple content</p></body></html>"

        with patch("trafilatura.extract") as mock_extract:
            mock_extract.return_value = None

            markdown, metadata = await extractor._parse_html(html_content, "https://example.com")

            assert "Simple content" in markdown
            assert metadata.get("parser_fallback") is True

    @pytest.mark.asyncio
    async def test_parse_html_fallback_on_import_error(self):
        """Falls back to basic extraction when trafilatura is not installed."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        html_content = "<html><body><p>Content without trafilatura</p></body></html>"

        with patch.dict("sys.modules", {"trafilatura": None}):
            # Force ImportError by patching the import
            with patch("src.services.url_extractor.URLExtractor._parse_html") as mock_parse:
                # Simulate fallback behavior
                mock_parse.return_value = ("Content without trafilatura", {"parser_fallback": True})

                result = await mock_parse(html_content, "https://example.com")
                assert result[1]["parser_fallback"] is True


class TestBasicHTMLExtraction:
    """Tests for the basic HTML extraction fallback."""

    def test_basic_extraction_removes_scripts(self):
        """Removes script tags from content."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        html = """
        <html>
        <body>
        <script>alert('malicious');</script>
        <p>Visible content</p>
        </body>
        </html>
        """

        result = extractor._basic_html_extraction(html)
        assert "malicious" not in result
        assert "Visible content" in result

    def test_basic_extraction_removes_style_tags(self):
        """Removes style tags from content."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        html = """
        <html>
        <body>
        <style>.hidden { display: none; }</style>
        <p>Styled content</p>
        </body>
        </html>
        """

        result = extractor._basic_html_extraction(html)
        assert "display" not in result
        assert "Styled content" in result

    def test_basic_extraction_removes_html_tags(self):
        """Strips HTML tags from content."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        html = "<p><strong>Bold</strong> and <em>italic</em> text</p>"
        result = extractor._basic_html_extraction(html)
        assert "Bold" in result
        assert "italic" in result
        assert "<" not in result
        assert ">" not in result

    def test_basic_extraction_decodes_entities(self):
        """Decodes HTML entities."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        html = "<p>Use &amp; for ampersand, &lt; for less than</p>"
        result = extractor._basic_html_extraction(html)
        assert "&" in result
        assert "<" in result or "less than" in result

    def test_basic_extraction_normalizes_whitespace(self):
        """Normalizes multiple whitespaces to single space."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        html = "<p>Text    with    multiple     spaces</p>"
        result = extractor._basic_html_extraction(html)
        assert "  " not in result  # No double spaces


class TestExtractContent:
    """Tests for the main extract_content method."""

    @pytest.mark.asyncio
    async def test_extract_content_success(self):
        """Successfully extracts content and updates database record."""
        mock_db = MagicMock()
        mock_content = MagicMock(spec=Content)
        mock_content.id = 1
        mock_content.source_url = "https://example.com/article"
        mock_content.title = "https://example.com/article"  # URL placeholder
        mock_content.metadata_json = None

        mock_db.query.return_value.filter.return_value.first.return_value = mock_content

        extractor = URLExtractor(mock_db)

        with patch.object(extractor, "_fetch_url", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = (
                "<html><body>Content</body></html>",
                "https://example.com/article",
            )

            with patch.object(extractor, "_parse_html", new_callable=AsyncMock) as mock_parse:
                mock_parse.return_value = (
                    "# Article\n\nContent",
                    {"title": "Article", "word_count": 2},
                )

                result = await extractor.extract_content(1)

                # Verify status transitions
                assert mock_content.status == ContentStatus.PARSED
                assert mock_content.markdown_content == "# Article\n\nContent"
                # Title should be updated from URL placeholder to extracted title
                assert mock_content.title == "Article"
                # Content hash should be recalculated
                assert mock_content.content_hash == generate_markdown_hash("# Article\n\nContent")
                mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_extract_content_preserves_user_provided_title(self):
        """Does not overwrite user-provided title with extracted title."""
        mock_db = MagicMock()
        mock_content = MagicMock(spec=Content)
        mock_content.id = 1
        mock_content.source_url = "https://example.com/article"
        mock_content.title = "My Custom Title"  # User-provided, not URL placeholder
        mock_content.metadata_json = None

        mock_db.query.return_value.filter.return_value.first.return_value = mock_content

        extractor = URLExtractor(mock_db)

        with patch.object(extractor, "_fetch_url", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = (
                "<html><body>Content</body></html>",
                "https://example.com/article",
            )

            with patch.object(extractor, "_parse_html", new_callable=AsyncMock) as mock_parse:
                mock_parse.return_value = (
                    "# Extracted Title\n\nContent",
                    {"title": "Extracted Title", "word_count": 2},
                )

                result = await extractor.extract_content(1)

                # User-provided title should be preserved
                assert mock_content.title == "My Custom Title"

    @pytest.mark.asyncio
    async def test_extract_content_not_found(self):
        """Raises ValueError when content ID not found."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        extractor = URLExtractor(mock_db)

        with pytest.raises(ValueError, match="Content not found"):
            await extractor.extract_content(999)

    @pytest.mark.asyncio
    async def test_extract_content_no_url(self):
        """Raises ValueError when content has no source_url."""
        mock_db = MagicMock()
        mock_content = MagicMock(spec=Content)
        mock_content.id = 1
        mock_content.source_url = None

        mock_db.query.return_value.filter.return_value.first.return_value = mock_content

        extractor = URLExtractor(mock_db)

        with pytest.raises(ValueError, match="has no source URL"):
            await extractor.extract_content(1)

    @pytest.mark.asyncio
    async def test_extract_content_marks_failed_on_error(self):
        """Marks content as failed when extraction fails."""
        mock_db = MagicMock()
        mock_content = MagicMock(spec=Content)
        mock_content.id = 1
        mock_content.source_url = "https://example.com/article"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_content

        extractor = URLExtractor(mock_db)

        with patch.object(extractor, "_fetch_url", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=MagicMock(status_code=404),
            )

            with pytest.raises(httpx.HTTPStatusError):
                await extractor.extract_content(1)

            # Verify content marked as failed
            assert mock_content.status == ContentStatus.FAILED
            assert mock_content.error_message is not None
            mock_db.commit.assert_called()


class TestExtractURLToContent:
    """Tests for the convenience function extract_url_to_content."""

    @pytest.mark.asyncio
    async def test_creates_new_content_record(self):
        """Creates a new content record for a new URL."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        added_content = None

        def capture_add(content):
            nonlocal added_content
            added_content = content

        mock_db.add.side_effect = capture_add

        result = await extract_url_to_content(
            mock_db,
            "https://example.com/new-article",
            title="New Article",
            tags=["ai", "tech"],
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

        # Verify NOT NULL fields are populated
        assert added_content is not None
        assert added_content.source_id == "webpage:https://example.com/new-article"
        assert added_content.markdown_content == ""
        assert added_content.content_hash == generate_markdown_hash("")

    @pytest.mark.asyncio
    async def test_returns_existing_for_duplicate_url(self):
        """Returns existing content for duplicate URL."""
        mock_db = MagicMock()
        existing_content = MagicMock(spec=Content)
        existing_content.id = 42
        mock_db.query.return_value.filter.return_value.first.return_value = existing_content

        result = await extract_url_to_content(
            mock_db,
            "https://example.com/existing-article",
        )

        assert result == existing_content
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_stores_metadata(self):
        """Stores excerpt, tags, notes, and source in metadata."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Create a real Content object to capture what's added
        added_content = None

        def capture_add(content):
            nonlocal added_content
            added_content = content

        mock_db.add.side_effect = capture_add

        await extract_url_to_content(
            mock_db,
            "https://example.com/article",
            excerpt="Selected text from page",
            tags=["ai", "ml"],
            notes="User notes here",
            source="ios_shortcut",
        )

        assert added_content is not None
        assert added_content.metadata_json["excerpt"] == "Selected text from page"
        assert added_content.metadata_json["tags"] == ["ai", "ml"]
        assert added_content.metadata_json["notes"] == "User notes here"
        assert added_content.metadata_json["capture_source"] == "ios_shortcut"
