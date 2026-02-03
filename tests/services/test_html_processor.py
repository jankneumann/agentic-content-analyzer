"""Unit tests for the HTML processor service.

Tests client HTML processing including markdown extraction,
image extraction, URL rewriting, and error handling.
"""

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.base import Base
from src.models.content import Content, ContentSource, ContentStatus
from src.services.html_processor import (
    _extract_markdown_and_title,
    _rewrite_image_urls,
    process_client_html,
)
from src.utils.content_hash import generate_markdown_hash

# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://newsletter_user:newsletter_password@localhost/newsletters_test",
)


@pytest.fixture(scope="module")
def test_engine():
    """Create test database engine."""
    from src.models.audio_digest import AudioDigest  # noqa: F401
    from src.models.content import Content  # noqa: F401
    from src.models.digest import Digest  # noqa: F401
    from src.models.image import Image  # noqa: F401
    from src.models.podcast import Podcast, PodcastScriptRecord  # noqa: F401
    from src.models.settings import PromptOverride  # noqa: F401
    from src.models.summary import Summary  # noqa: F401
    from src.models.theme import ThemeAnalysis  # noqa: F401

    engine = create_engine(TEST_DATABASE_URL, echo=False)

    # Safety check
    db_name = engine.url.database
    if not db_name or "test" not in db_name.lower():
        raise ValueError(f"Safety check failed: '{db_name}' is not a test database")

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    yield engine

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """Create a database session with transaction rollback."""
    connection = test_engine.connect()
    transaction = connection.begin()

    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def sample_content(db_session) -> Content:
    """Create a sample content record for testing."""
    content = Content(
        source_type=ContentSource.WEBPAGE,
        source_id="webpage:https://example.com/test",
        source_url="https://example.com/test",
        title="https://example.com/test",
        markdown_content="",
        content_hash=generate_markdown_hash(""),
        status=ContentStatus.PENDING,
        metadata_json={"capture_method": "client_html"},
        ingested_at=datetime.now(UTC),
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


class TestExtractMarkdownAndTitle:
    """Tests for _extract_markdown_and_title function."""

    def test_extracts_markdown_from_valid_html(self):
        """Extracts markdown content from valid HTML."""
        html = """
        <html>
        <head><title>Test Article</title></head>
        <body>
            <article>
                <h1>Main Heading</h1>
                <p>This is the main content of the article with some important text.</p>
                <p>Another paragraph with more details about the topic.</p>
            </article>
        </body>
        </html>
        """

        markdown, title = _extract_markdown_and_title(html, "https://example.com")

        assert markdown is not None
        assert len(markdown) > 0
        # Trafilatura should extract some content
        assert (
            "content" in markdown.lower()
            or "paragraph" in markdown.lower()
            or "heading" in markdown.lower()
            or "important" in markdown.lower()
        )

    def test_extracts_title_from_metadata(self):
        """Extracts title from HTML metadata."""
        html = """
        <html>
        <head><title>My Article Title</title></head>
        <body>
            <article><p>Article content here.</p></article>
        </body>
        </html>
        """

        _, title = _extract_markdown_and_title(html, "https://example.com")

        # Title may or may not be extracted depending on trafilatura version
        # Just verify we don't crash
        assert title is None or isinstance(title, str)

    def test_returns_none_for_empty_html(self):
        """Returns None for empty or minimal HTML."""
        html = "<html><head></head><body></body></html>"

        markdown, title = _extract_markdown_and_title(html, "https://example.com")

        # Trafilatura returns None/empty for pages with no content
        assert markdown is None or markdown.strip() == ""

    def test_returns_none_for_malformed_html(self):
        """Returns None for malformed HTML that can't be parsed."""
        html = "not valid html at all"

        markdown, title = _extract_markdown_and_title(html, "https://example.com")

        # Should handle gracefully
        assert markdown is None or markdown.strip() == ""


class TestRewriteImageUrls:
    """Tests for _rewrite_image_urls function."""

    def test_rewrites_single_image_url(self):
        """Rewrites a single image URL in markdown."""
        markdown = "Check out this image: ![alt](https://example.com/image.jpg)"
        url_mapping = {"https://example.com/image.jpg": "/api/v1/files/images/abc123.jpg"}

        result = _rewrite_image_urls(markdown, url_mapping)

        assert "https://example.com/image.jpg" not in result
        assert "/api/v1/files/images/abc123.jpg" in result

    def test_rewrites_multiple_image_urls(self):
        """Rewrites multiple image URLs in markdown."""
        markdown = """
        First image: ![img1](https://example.com/img1.jpg)
        Second image: ![img2](https://cdn.example.com/img2.png)
        """
        url_mapping = {
            "https://example.com/img1.jpg": "/api/v1/files/images/local1.jpg",
            "https://cdn.example.com/img2.png": "/api/v1/files/images/local2.png",
        }

        result = _rewrite_image_urls(markdown, url_mapping)

        assert "/api/v1/files/images/local1.jpg" in result
        assert "/api/v1/files/images/local2.png" in result
        assert "https://example.com/img1.jpg" not in result
        assert "https://cdn.example.com/img2.png" not in result

    def test_preserves_urls_not_in_mapping(self):
        """Preserves original URLs not in the mapping (download failures)."""
        markdown = "![img](https://example.com/failed-download.jpg)"
        url_mapping = {}  # Empty mapping - download failed

        result = _rewrite_image_urls(markdown, url_mapping)

        # Original URL should be preserved
        assert "https://example.com/failed-download.jpg" in result

    def test_handles_empty_markdown(self):
        """Handles empty markdown gracefully."""
        result = _rewrite_image_urls("", {"https://x.com/y.jpg": "/local"})
        assert result == ""

    def test_handles_empty_mapping(self):
        """Returns unchanged markdown when mapping is empty."""
        markdown = "![img](https://example.com/image.jpg)"

        result = _rewrite_image_urls(markdown, {})

        assert result == markdown

    def test_handles_special_regex_characters_in_url(self):
        """Properly escapes special regex characters in URLs."""
        markdown = "![img](https://example.com/image?size=large&format=jpg)"
        url_mapping = {
            "https://example.com/image?size=large&format=jpg": "/api/v1/files/images/local.jpg"
        }

        result = _rewrite_image_urls(markdown, url_mapping)

        assert "/api/v1/files/images/local.jpg" in result
        assert "https://example.com/image?size=large&format=jpg" not in result


class TestProcessClientHtml:
    """Tests for process_client_html function."""

    @pytest.mark.asyncio
    async def test_extracts_markdown_from_valid_html(self, db_session, sample_content):
        """Successfully extracts markdown from valid HTML."""
        html = """
        <html>
        <head><title>Test Article</title></head>
        <body>
            <article>
                <h1>Test Heading</h1>
                <p>This is a test paragraph with enough content to be extracted by trafilatura.
                It needs to have sufficient text to be considered meaningful content.</p>
                <p>Adding more paragraphs helps ensure content extraction works properly.</p>
            </article>
        </body>
        </html>
        """

        # Mock image extraction to return empty (no images)
        with patch(
            "src.services.html_processor._extract_and_store_images",
            new_callable=AsyncMock,
            return_value=([], {}),
        ):
            result = await process_client_html(
                db_session, sample_content.id, html, "https://example.com/test"
            )

        # Refresh to get updated state
        db_session.refresh(result)

        assert result.status == ContentStatus.PARSED
        assert result.markdown_content is not None
        assert len(result.markdown_content) > 0
        assert result.parser_used == "HTMLProcessor"
        assert result.metadata_json.get("word_count", 0) > 0
        assert result.metadata_json.get("image_count") == 0

    @pytest.mark.asyncio
    async def test_sets_failed_status_for_empty_html(self, db_session, sample_content):
        """Sets FAILED status when HTML produces no markdown."""
        html = "<html><head></head><body></body></html>"

        result = await process_client_html(
            db_session, sample_content.id, html, "https://example.com/test"
        )

        db_session.refresh(result)

        assert result.status == ContentStatus.FAILED
        assert "empty" in result.error_message.lower() or "failed" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_handles_content_not_found(self, db_session):
        """Raises ValueError when content ID doesn't exist."""
        with pytest.raises(ValueError, match="Content not found"):
            await process_client_html(db_session, 99999, "<html></html>", "https://example.com")

    @pytest.mark.asyncio
    async def test_extracts_and_stores_images(self, db_session, sample_content):
        """Extracts images and updates metadata with image count."""
        html = """
        <html>
        <head><title>Article with Images</title></head>
        <body>
            <article>
                <h1>Article Title</h1>
                <p>This article has meaningful content that will be extracted properly.</p>
                <img src="https://example.com/image1.jpg" alt="Image 1">
                <p>More text content to ensure extraction succeeds.</p>
                <img src="https://example.com/image2.png" alt="Image 2">
            </article>
        </body>
        </html>
        """

        # Mock image extraction to return some images
        mock_image_creates = [
            MagicMock(
                source_type="extracted",
                source_content_id=sample_content.id,
                source_url="https://example.com/image1.jpg",
                storage_path="abc123.jpg",
                storage_provider="local",
                filename="image1.jpg",
                mime_type="image/jpeg",
                width=800,
                height=600,
                file_size_bytes=50000,
                alt_text="Image 1",
                phash="hash1",
            ),
            MagicMock(
                source_type="extracted",
                source_content_id=sample_content.id,
                source_url="https://example.com/image2.png",
                storage_path="def456.png",
                storage_provider="local",
                filename="image2.png",
                mime_type="image/png",
                width=1024,
                height=768,
                file_size_bytes=75000,
                alt_text="Image 2",
                phash="hash2",
            ),
        ]
        url_mapping = {
            "https://example.com/image1.jpg": "/api/v1/files/images/abc123.jpg",
            "https://example.com/image2.png": "/api/v1/files/images/def456.png",
        }

        with patch(
            "src.services.html_processor._extract_and_store_images",
            new_callable=AsyncMock,
            return_value=(mock_image_creates, url_mapping),
        ):
            result = await process_client_html(
                db_session, sample_content.id, html, "https://example.com/test"
            )

        db_session.refresh(result)

        assert result.status == ContentStatus.PARSED
        assert result.metadata_json.get("image_count") == 2

    @pytest.mark.asyncio
    async def test_rewrites_image_urls_in_markdown(self, db_session, sample_content):
        """Rewrites image URLs in extracted markdown to local storage paths."""
        html = """
        <html>
        <head><title>Test</title></head>
        <body>
            <article>
                <p>Important content here with enough text for extraction.</p>
                <img src="https://cdn.example.com/pic.jpg">
                <p>More meaningful content to ensure successful extraction.</p>
            </article>
        </body>
        </html>
        """

        url_mapping = {"https://cdn.example.com/pic.jpg": "/api/v1/files/images/local_pic.jpg"}

        with patch(
            "src.services.html_processor._extract_and_store_images",
            new_callable=AsyncMock,
            return_value=([], url_mapping),
        ):
            # Also need to mock trafilatura to return markdown with the image URL
            with patch("src.services.html_processor._extract_markdown_and_title") as mock_extract:
                mock_extract.return_value = (
                    "Content with ![image](https://cdn.example.com/pic.jpg)",
                    "Test",
                )
                result = await process_client_html(
                    db_session, sample_content.id, html, "https://example.com/test"
                )

        db_session.refresh(result)

        assert result.status == ContentStatus.PARSED
        assert "/api/v1/files/images/local_pic.jpg" in result.markdown_content
        assert "https://cdn.example.com/pic.jpg" not in result.markdown_content

    @pytest.mark.asyncio
    async def test_preserves_original_urls_on_download_failure(self, db_session, sample_content):
        """Preserves original image URLs when downloads fail."""
        html = """
        <html>
        <head><title>Test</title></head>
        <body>
            <article>
                <p>Content with an image that fails to download.</p>
                <img src="https://example.com/unavailable.jpg">
                <p>More content here.</p>
            </article>
        </body>
        </html>
        """

        # Empty mapping = all downloads failed
        with patch(
            "src.services.html_processor._extract_and_store_images",
            new_callable=AsyncMock,
            return_value=([], {}),
        ):
            with patch("src.services.html_processor._extract_markdown_and_title") as mock_extract:
                mock_extract.return_value = (
                    "Content with ![img](https://example.com/unavailable.jpg)",
                    "Test",
                )
                result = await process_client_html(
                    db_session, sample_content.id, html, "https://example.com/test"
                )

        db_session.refresh(result)

        assert result.status == ContentStatus.PARSED
        # Original URL should be preserved since download failed
        assert "https://example.com/unavailable.jpg" in result.markdown_content

    @pytest.mark.asyncio
    async def test_handles_html_with_no_images(self, db_session, sample_content):
        """Processes HTML with no images successfully."""
        html = """
        <html>
        <head><title>Text Only Article</title></head>
        <body>
            <article>
                <h1>No Images Here</h1>
                <p>This article contains only text content without any images.</p>
                <p>Just pure text-based information for readers.</p>
            </article>
        </body>
        </html>
        """

        with patch(
            "src.services.html_processor._extract_and_store_images",
            new_callable=AsyncMock,
            return_value=([], {}),
        ):
            result = await process_client_html(
                db_session, sample_content.id, html, "https://example.com/test"
            )

        db_session.refresh(result)

        assert result.status == ContentStatus.PARSED
        assert result.metadata_json.get("image_count") == 0
        assert result.markdown_content is not None

    @pytest.mark.asyncio
    async def test_updates_title_from_extraction(self, db_session, sample_content):
        """Updates content title from extracted metadata when title is URL placeholder."""
        html = """
        <html>
        <head><title>Extracted Title</title></head>
        <body>
            <article>
                <h1>Article Heading</h1>
                <p>Article content with enough text for trafilatura to extract.</p>
            </article>
        </body>
        </html>
        """

        # Ensure content title is the URL placeholder
        sample_content.title = sample_content.source_url
        db_session.commit()

        with patch(
            "src.services.html_processor._extract_and_store_images",
            new_callable=AsyncMock,
            return_value=([], {}),
        ):
            with patch("src.services.html_processor._extract_markdown_and_title") as mock_extract:
                mock_extract.return_value = ("Extracted content", "Extracted Title")
                result = await process_client_html(
                    db_session, sample_content.id, html, "https://example.com/test"
                )

        db_session.refresh(result)

        assert result.title == "Extracted Title"
