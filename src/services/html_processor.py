"""Client HTML processing service.

This module processes HTML content captured by the browser extension,
extracting markdown content and images while rewriting image URLs
to point to local storage.
"""

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm.attributes import flag_modified

from src.models.content import Content, ContentStatus
from src.models.image import Image, ImageSource
from src.services.image_extractor import ImageExtractor
from src.utils.content_hash import generate_markdown_hash
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = get_logger(__name__)


async def process_client_html(
    db: "Session",
    content_id: int,
    html: str,
    source_url: str,
) -> Content:
    """Process client-supplied HTML to extract content and images.

    This function:
    1. Parses HTML to markdown using trafilatura
    2. Extracts images from HTML using ImageExtractor
    3. Downloads and stores images server-side
    4. Rewrites image URLs in markdown to point to local storage
    5. Updates the Content record with results

    Args:
        db: SQLAlchemy database session
        content_id: ID of the Content record to update
        html: Raw HTML string from the browser
        source_url: Original page URL (for resolving relative URLs)

    Returns:
        Updated Content record

    Raises:
        ValueError: If content not found
    """
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise ValueError(f"Content not found: {content_id}")

    # Update status to parsing
    content.status = ContentStatus.PARSING
    db.commit()

    try:
        # Parse HTML to markdown
        markdown_content, title = _extract_markdown_and_title(html, source_url)

        if not markdown_content or not markdown_content.strip():
            # Empty markdown indicates extraction failure
            content.status = ContentStatus.FAILED
            content.error_message = (
                "Failed to extract content from HTML (trafilatura returned empty)"
            )
            db.commit()
            logger.warning(f"Empty markdown extracted for content_id={content_id}")
            return content

        # Extract and store images
        image_creates, url_mapping = await _extract_and_store_images(html, source_url, content_id)

        # Rewrite image URLs in markdown
        final_markdown = _rewrite_image_urls(markdown_content, url_mapping)

        # Update content record
        content.markdown_content = final_markdown
        content.content_hash = generate_markdown_hash(final_markdown)
        content.status = ContentStatus.PARSED
        content.parsed_at = datetime.now(UTC)
        content.parser_used = "HTMLProcessor"

        # Update title if extracted and content title is still the URL placeholder
        if title and content.title == content.source_url:
            content.title = title

        # Update metadata
        if content.metadata_json is None:
            content.metadata_json = {}
        content.metadata_json["word_count"] = len(final_markdown.split())
        content.metadata_json["image_count"] = len(image_creates)
        flag_modified(content, "metadata_json")

        # Save image records to database
        for img_create in image_creates:
            image = Image(
                source_type=img_create.source_type,
                source_content_id=img_create.source_content_id,
                source_url=img_create.source_url,
                storage_path=img_create.storage_path,
                storage_provider=img_create.storage_provider,
                filename=img_create.filename,
                mime_type=img_create.mime_type,
                width=img_create.width,
                height=img_create.height,
                file_size_bytes=img_create.file_size_bytes,
                alt_text=img_create.alt_text,
                phash=img_create.phash,
            )
            db.add(image)

        db.commit()
        logger.info(
            f"Successfully processed client HTML for content_id={content_id}, "
            f"images={len(image_creates)}, words={content.metadata_json.get('word_count')}"
        )

        return content

    except Exception as e:
        # Mark as failed
        content.status = ContentStatus.FAILED
        content.error_message = "Failed to process client HTML due to an internal error"
        db.commit()
        logger.error(f"Failed to process client HTML for content_id={content_id}: {e}")
        raise


def _extract_markdown_and_title(html: str, source_url: str) -> tuple[str | None, str | None]:
    """Extract markdown content and title from HTML.

    Args:
        html: Raw HTML string
        source_url: URL for context

    Returns:
        Tuple of (markdown_content, title)
    """
    try:
        import trafilatura

        # Extract main content as markdown
        markdown_content = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_links=True,
            output_format="markdown",
        )

        # Extract title from metadata
        title = None
        extracted_meta = trafilatura.extract_metadata(html)
        if extracted_meta and extracted_meta.title:
            title = extracted_meta.title

        return markdown_content, title

    except ImportError:
        logger.error("trafilatura not installed - cannot process HTML")
        return None, None
    except Exception as e:
        logger.warning(f"Trafilatura extraction failed: {e}")
        return None, None


async def _extract_and_store_images(
    html: str,
    source_url: str,
    content_id: int,
    max_images: int = 20,
) -> tuple[list, dict[str, str]]:
    """Extract images from HTML, download them, and store them.

    Args:
        html: Raw HTML string
        source_url: Base URL for resolving relative image URLs
        content_id: Content ID to associate images with
        max_images: Maximum number of images to extract

    Returns:
        Tuple of (list of ImageCreate objects, mapping of original_url -> storage_url)
    """
    url_mapping: dict[str, str] = {}

    async with ImageExtractor() as extractor:
        # Extract images from HTML
        extracted_images = await extractor.extract_from_html(
            html, base_url=source_url, max_images=max_images
        )

        if not extracted_images:
            return [], url_mapping

        # Save extracted images to storage
        image_creates = await extractor.save_extracted_images(
            extracted_images,
            source_content_id=content_id,
            source_type=ImageSource.EXTRACTED,
        )

        # Build URL mapping for markdown rewriting
        # Match storage paths to original URLs
        for extracted, create in zip(extracted_images, image_creates, strict=False):
            if extracted.source_url and create.storage_path:
                # Map original URL to local storage URL
                storage_url = f"/api/v1/files/images/{create.storage_path}"
                url_mapping[extracted.source_url] = storage_url

    return image_creates, url_mapping


def _rewrite_image_urls(markdown: str, url_mapping: dict[str, str]) -> str:
    """Rewrite image URLs in markdown to point to local storage.

    Handles both standard markdown image syntax and any URLs in the content.
    Images that failed to download (not in mapping) keep their original URLs.

    Args:
        markdown: Markdown content with original image URLs
        url_mapping: Mapping of original_url -> storage_url

    Returns:
        Markdown with rewritten image URLs
    """
    if not url_mapping:
        return markdown

    result = markdown

    # Replace each URL that we successfully downloaded
    for original_url, storage_url in url_mapping.items():
        result = result.replace(original_url, storage_url)

    return result
