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


# Patch flag_modified to avoid AttributeError with mocks
@pytest.fixture(autouse=True)
def mock_flag_modified():
    with patch("src.services.url_extractor.flag_modified") as m:
        yield m


class TestURLExtractorInit:
    """Tests for URLExtractor initialization."""

    def test_init_with_session(self):
        """URLExtractor initializes with database session."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)
        assert extractor.db == mock_db


class TestFetchURL:
    """Tests for URL fetching functionality."""

    @pytest.fixture
    def mock_stream_client(self):
        """Fixture for mocking httpx stream context."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = (
                MagicMock()
            )  # Use MagicMock, not AsyncMock, to control method types
            mock_client.return_value = mock_client_instance

            # AsyncClient is an async context manager
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)

            # Setup stream mock - stream() is a sync method returning an async context manager
            mock_stream_ctx = MagicMock()
            mock_client_instance.stream.return_value = mock_stream_ctx

            mock_response = MagicMock()
            mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

            yield mock_client, mock_client_instance, mock_response

    @pytest.mark.asyncio
    async def test_fetch_url_success(self, mock_stream_client):
        """Fetches URL content with proper headers."""
        mock_client, mock_client_instance, mock_response = mock_stream_client
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        mock_response.url = "https://example.com/article"
        mock_response.headers = {
            "content-type": "text/html; charset=utf-8",
            "content-length": "100",
        }
        mock_response.encoding = "utf-8"

        # Mock streaming content
        content_bytes = b"<html><body><h1>Test Article</h1></body></html>"

        async def iter_bytes():
            yield content_bytes

        mock_response.aiter_bytes.return_value = iter_bytes()

        html, final_url = await extractor._fetch_url("https://example.com/article")

        assert html == "<html><body><h1>Test Article</h1></body></html>"
        assert final_url == "https://example.com/article"

        # Verify arguments
        call_kwargs = mock_client.call_args.kwargs
        assert call_kwargs["timeout"] == DEFAULT_TIMEOUT
        assert call_kwargs["follow_redirects"] is True
        assert call_kwargs["headers"] == {"User-Agent": USER_AGENT}
        assert "event_hooks" in call_kwargs

        mock_client_instance.stream.assert_called_with("GET", "https://example.com/article")

    @pytest.mark.asyncio
    async def test_fetch_url_follows_redirects(self, mock_stream_client):
        """URL fetching follows redirects and returns final URL."""
        _, _, mock_response = mock_stream_client
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        mock_response.url = "https://example.com/final-url"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.encoding = "utf-8"

        async def iter_bytes():
            yield b"<html><body>Content</body></html>"

        mock_response.aiter_bytes.return_value = iter_bytes()

        _html, final_url = await extractor._fetch_url("https://example.com/redirect")

        assert final_url == "https://example.com/final-url"

    @pytest.mark.asyncio
    async def test_fetch_url_raises_on_http_error(self, mock_stream_client):
        """Raises exception for HTTP errors (404, 500, etc.)."""
        _, _, mock_response = mock_stream_client
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        )

        with pytest.raises(httpx.HTTPStatusError):
            await extractor._fetch_url("https://example.com/not-found")

    @pytest.mark.asyncio
    async def test_fetch_url_rejects_oversized_content_header(self, mock_stream_client):
        """Rejects responses with Content-Length header exceeding the limit."""
        _, _, mock_response = mock_stream_client
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        mock_response.headers = {"content-type": "text/html", "content-length": "999999999"}
        mock_response.url = "https://example.com/huge-page"

        with pytest.raises(ValueError, match="Content too large"):
            await extractor._fetch_url("https://example.com/huge-page")

    @pytest.mark.asyncio
    async def test_fetch_url_rejects_oversized_content_body(self, mock_stream_client):
        """Rejects responses with body size exceeding limit (when header is missing/small)."""
        _, _, mock_response = mock_stream_client
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        mock_response.headers = {"content-type": "text/html"}
        mock_response.url = "https://example.com/huge-page"

        # Generate huge content
        chunk_size = 1024 * 1024  # 1MB

        async def iter_bytes():
            # Yield 11 chunks of 1MB (limit is 10MB)
            for _ in range(11):
                yield b"x" * chunk_size

        mock_response.aiter_bytes.return_value = iter_bytes()

        with pytest.raises(ValueError, match="Response body too large"):
            await extractor._fetch_url("https://example.com/huge-page")

    @pytest.mark.asyncio
    async def test_fetch_url_rejects_non_html_content(self, mock_stream_client):
        """Rejects responses with non-HTML content types."""
        _, _, mock_response = mock_stream_client
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.url = "https://example.com/document.pdf"

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
    async def test_parse_html_fallback_on_extraction_error(self):
        """Falls back to basic extraction when trafilatura raises an error."""
        mock_db = MagicMock()
        extractor = URLExtractor(mock_db)

        html_content = "<html><body><p>Content with error</p></body></html>"

        with patch("trafilatura.extract") as mock_extract:
            mock_extract.side_effect = Exception("Trafilatura internal error")

            markdown, metadata = await extractor._parse_html(html_content, "https://example.com")

            assert "Content with error" in markdown
            assert metadata.get("parser_fallback") is True
            assert "parser_error" in metadata


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
    async def test_extract_content_transitions_to_parsing_status(self):
        """Verifies status transitions to PARSING before extraction begins."""
        mock_db = MagicMock()
        mock_content = MagicMock(spec=Content)
        mock_content.id = 1
        mock_content.source_url = "https://example.com/article"
        mock_content.title = "https://example.com/article"
        mock_content.metadata_json = None

        status_history = []

        def track_status(value):
            status_history.append(value)

        type(mock_content).status = property(
            lambda self: status_history[-1] if status_history else ContentStatus.PENDING,
            lambda self, v: track_status(v),
        )

        mock_db.query.return_value.filter.return_value.first.return_value = mock_content

        extractor = URLExtractor(mock_db)

        with patch.object(extractor, "_fetch_url", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = (
                "<html><body>Content</body></html>",
                "https://example.com/article",
            )
            with patch.object(extractor, "_parse_html", new_callable=AsyncMock) as mock_parse:
                mock_parse.return_value = ("# Article", {"word_count": 1})
                await extractor.extract_content(1)

        # First status change should be PARSING, then PARSED
        assert ContentStatus.PARSING in status_history
        assert ContentStatus.PARSED in status_history
        assert status_history.index(ContentStatus.PARSING) < status_history.index(
            ContentStatus.PARSED
        )

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

    @pytest.mark.asyncio
    async def test_extract_content_prevents_information_leakage(self):
        """Verifies that exception details are NOT leaked to error_message."""
        mock_db = MagicMock()
        mock_content = MagicMock(spec=Content)
        mock_content.id = 1
        mock_content.source_url = "https://example.com/article"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_content

        extractor = URLExtractor(mock_db)

        secret_key = "sk_live_SECRET_KEY_12345"
        error_msg = f"Connection failed to database at postgres://user:{secret_key}@host:5432/db"

        with patch.object(extractor, "_fetch_url", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception(error_msg)

            with pytest.raises(Exception, match="Connection failed"):
                await extractor.extract_content(1)

            assert mock_content.status == ContentStatus.FAILED
            assert secret_key not in mock_content.error_message
            assert (
                mock_content.error_message == "Content extraction failed. Please try again later."
            )


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
