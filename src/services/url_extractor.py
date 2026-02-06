"""URL content extraction service.

This service fetches URLs and extracts their content to markdown,
integrating with the existing parser infrastructure.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
from sqlalchemy.orm.attributes import flag_modified

from src.models.content import Content, ContentSource, ContentStatus
from src.utils.content_hash import generate_markdown_hash
from src.utils.logging import get_logger
from src.utils.security import validate_url

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = get_logger(__name__)

# Default timeout for URL fetching
DEFAULT_TIMEOUT = 30.0

# Maximum content size to download (10MB)
MAX_CONTENT_SIZE = 10 * 1024 * 1024

# Allowed content types for HTML extraction
ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml")

# User agent for web requests
USER_AGENT = (
    "Mozilla/5.0 (compatible; NewsletterAggregator/1.0; "
    "+https://github.com/jankneumann/agentic-newsletter-aggregator)"
)


class URLExtractor:
    """Service for extracting content from URLs.

    Uses httpx for async HTTP requests and routes content
    through the existing parser infrastructure.
    """

    def __init__(self, db: "Session") -> None:
        """Initialize the URL extractor.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    async def extract_content(self, content_id: int) -> Content:
        """Extract and parse content from a URL.

        Fetches the URL, parses HTML to markdown, and updates
        the Content record with the extracted content.

        Args:
            content_id: ID of the Content record to process

        Returns:
            Updated Content record

        Raises:
            ValueError: If content not found or has no URL
            httpx.HTTPError: If URL fetch fails
        """
        # Get the content record
        content = self.db.query(Content).filter(Content.id == content_id).first()
        if not content:
            raise ValueError(f"Content not found: {content_id}")

        if not content.source_url:
            raise ValueError(f"Content has no source URL: {content_id}")

        # Update status to parsing
        content.status = ContentStatus.PARSING
        self.db.commit()

        try:
            # Fetch the URL
            html_content, final_url = await self._fetch_url(content.source_url)

            # Parse HTML to markdown
            markdown_content, metadata = await self._parse_html(html_content, final_url)

            # Update content record
            content.markdown_content = markdown_content
            content.content_hash = generate_markdown_hash(markdown_content)
            content.status = ContentStatus.PARSED
            content.parsed_at = datetime.now(UTC)
            content.parser_used = "URLExtractor"

            # Update title if still set to URL placeholder
            if metadata.get("title") and content.title == content.source_url:
                content.title = metadata["title"]

            # Store additional metadata (use flag_modified for JSON mutation tracking)
            if content.metadata_json is None:
                content.metadata_json = {}
            content.metadata_json.update(metadata)
            flag_modified(content, "metadata_json")

            self.db.commit()
            logger.info(f"Successfully extracted content from {content.source_url}")

            return content

        except Exception as e:
            # Mark as failed
            content.status = ContentStatus.FAILED
            # Secure error message to prevent information leakage
            content.error_message = "Content extraction failed. Please try again later."
            self.db.commit()
            logger.error(f"Failed to extract content from {content.source_url}", exc_info=True)
            raise

    async def _fetch_url(self, url: str) -> tuple[str, str]:
        """Fetch content from a URL.

        Args:
            url: URL to fetch

        Returns:
            Tuple of (html_content, final_url after redirects)

        Raises:
            httpx.HTTPError: If fetch fails
            ValueError: If content is too large or not HTML
        """
        # Validate URL to prevent SSRF
        await validate_url(url)

        async def check_redirect(response: httpx.Response) -> None:
            if response.is_redirect:
                target = response.headers.get("Location")
                if target:
                    from urllib.parse import urljoin

                    # Resolve relative URLs
                    target_url = urljoin(str(response.url), target)
                    await validate_url(target_url)

        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            event_hooks={"response": [check_redirect]},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Check content size
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_CONTENT_SIZE:
                raise ValueError(
                    f"Content too large: {content_length} bytes (max {MAX_CONTENT_SIZE})"
                )

            # Check content type
            content_type = response.headers.get("content-type", "")
            if not any(content_type.startswith(ct) for ct in ALLOWED_CONTENT_TYPES):
                raise ValueError(f"Unsupported content type: {content_type} (expected HTML)")

            # Check actual response size
            text = response.text
            if len(text.encode("utf-8")) > MAX_CONTENT_SIZE:
                raise ValueError(f"Response body too large (max {MAX_CONTENT_SIZE} bytes)")

            return text, str(response.url)

    async def _parse_html(self, html_content: str, url: str) -> tuple[str, dict]:
        """Parse HTML content to markdown.

        Uses the existing parser router if available, otherwise
        falls back to basic extraction.

        Args:
            html_content: Raw HTML content
            url: URL for context (e.g., resolving relative links)

        Returns:
            Tuple of (markdown_content, metadata_dict)
        """
        metadata: dict = {}

        try:
            # Use trafilatura for high-quality web content extraction
            import trafilatura

            # Extract main content with metadata
            downloaded = html_content if html_content else trafilatura.fetch_url(url)
            markdown_content = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=True,
                include_links=True,
                output_format="markdown",
            )

            if not markdown_content:
                # Fallback to basic extraction if trafilatura returns nothing
                markdown_content = self._basic_html_extraction(html_content)
                metadata = {
                    "word_count": len(markdown_content.split()),
                    "source_url": url,
                    "parser_fallback": True,
                }
            else:
                metadata = {
                    "word_count": len(markdown_content.split()),
                    "source_url": url,
                }

                # Try to extract title
                extracted_meta = trafilatura.extract_metadata(downloaded)
                if extracted_meta and extracted_meta.title:
                    metadata["title"] = extracted_meta.title

        except ImportError:
            # Fallback to basic extraction if trafilatura not available
            markdown_content = self._basic_html_extraction(html_content)
            metadata = {
                "word_count": len(markdown_content.split()),
                "source_url": url,
                "parser_fallback": True,
            }

        except Exception as e:
            logger.warning(f"Trafilatura extraction failed, using fallback: {e}")
            markdown_content = self._basic_html_extraction(html_content)
            metadata = {
                "word_count": len(markdown_content.split()),
                "source_url": url,
                "parser_fallback": True,
                "parser_error": "Advanced parsing failed, used fallback",
            }

        return markdown_content, metadata

    def _basic_html_extraction(self, html_content: str) -> str:
        """Basic HTML to text extraction fallback.

        Strips HTML tags and normalizes whitespace. This is a simple
        fallback when the parser router is not available.

        Args:
            html_content: Raw HTML content

        Returns:
            Plain text content
        """
        import re

        # Remove script and style elements
        text = re.sub(
            r"<(script|style)[^>]*>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE
        )

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", text)

        # Decode HTML entities
        import html

        text = html.unescape(text)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text


async def extract_url_to_content(
    db: "Session",
    url: str,
    title: str | None = None,
    excerpt: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
    source: str | None = None,
) -> Content:
    """Create a Content record from a URL and extract its content.

    This is a convenience function that creates the Content record
    and immediately starts extraction.

    Args:
        db: SQLAlchemy database session
        url: URL to save and extract
        title: Optional title (extracted if not provided)
        excerpt: Optional excerpt/selection from the page
        tags: Optional list of tags
        notes: Optional user notes
        source: Optional source identifier (e.g., "ios_shortcut")

    Returns:
        Created Content record (extraction may still be in progress)
    """
    # Check for duplicate
    existing = db.query(Content).filter(Content.source_url == url).first()
    if existing:
        return existing

    # Create content record
    metadata = {}
    if excerpt:
        metadata["excerpt"] = excerpt
    if tags:
        metadata["tags"] = tags
    if notes:
        metadata["notes"] = notes
    if source:
        metadata["capture_source"] = source

    content = Content(
        source_type=ContentSource.WEBPAGE,
        source_id=f"webpage:{url}",
        source_url=url,
        title=title or url,  # Use URL as title until extracted
        markdown_content="",  # Placeholder until extraction completes
        content_hash=generate_markdown_hash(""),
        status=ContentStatus.PENDING,
        metadata_json=metadata if metadata else None,
        ingested_at=datetime.now(UTC),
    )

    db.add(content)
    db.commit()
    db.refresh(content)

    return content
