"""MarkItDown parser implementation for document to markdown conversion."""

import logging
import re
import time
from pathlib import Path
from typing import BinaryIO, ClassVar

from markitdown import MarkItDown

from src.models.document import DocumentContent, DocumentFormat, DocumentMetadata
from src.parsers.base import DocumentParser

logger = logging.getLogger(__name__)


class MarkItDownParser(DocumentParser):
    """Parser using Microsoft's MarkItDown library.

    Best for:
    - Simple document conversions (DOCX, PPTX, XLSX)
    - YouTube transcript extraction
    - Audio transcription
    - Outlook MSG files
    - EPUB ebooks
    - Lightweight/fast processing

    Trade-offs:
    - No structured data extraction (markdown only)
    - Basic PDF handling (no layout analysis)
    - No OCR support
    """

    # Primary supported formats
    supported_formats: ClassVar[set[str]] = {
        "docx",
        "pptx",
        "xlsx",
        "html",
        "youtube",
        "mp3",
        "wav",
        "msg",
        "epub",
        "txt",
        "md",
    }

    # Formats we can handle but Docling may do better
    fallback_formats: ClassVar[set[str]] = {"pdf"}

    # Extension to DocumentFormat mapping
    FORMAT_MAP: ClassVar[dict[str, DocumentFormat]] = {
        "pdf": DocumentFormat.PDF,
        "docx": DocumentFormat.DOCX,
        "pptx": DocumentFormat.PPTX,
        "xlsx": DocumentFormat.XLSX,
        "html": DocumentFormat.HTML,
        "htm": DocumentFormat.HTML,
        "md": DocumentFormat.MARKDOWN,
        "markdown": DocumentFormat.MARKDOWN,
        "txt": DocumentFormat.TEXT,
        "mp3": DocumentFormat.AUDIO,
        "wav": DocumentFormat.AUDIO,
        "m4a": DocumentFormat.AUDIO,
        "msg": DocumentFormat.OUTLOOK_MSG,
        "epub": DocumentFormat.EPUB,
        "youtube": DocumentFormat.YOUTUBE,
        "png": DocumentFormat.IMAGE,
        "jpg": DocumentFormat.IMAGE,
        "jpeg": DocumentFormat.IMAGE,
        "gif": DocumentFormat.IMAGE,
    }

    def __init__(self, llm_client: object | None = None) -> None:
        """Initialize the MarkItDown parser.

        Args:
            llm_client: Optional LLM client for image description.
                       Can be used for describing images found in documents.
        """
        self.md = MarkItDown(llm_client=llm_client)

    @property
    def name(self) -> str:
        """Parser identifier."""
        return "markitdown"

    async def parse(
        self,
        source: str | Path | BinaryIO | bytes,
        format_hint: str | None = None,
    ) -> DocumentContent:
        """Parse document and return unified content model.

        Args:
            source: File path, URL (including YouTube), file-like object, or bytes
            format_hint: Optional format override

        Returns:
            DocumentContent with markdown and extracted metadata
        """
        start_time = time.time()
        warnings: list[str] = []

        source_str = str(source) if not isinstance(source, bytes | BinaryIO) else "stream"
        detected_format = format_hint or self._detect_format(source)

        try:
            result = self.md.convert(source)
            markdown_content = result.text_content or ""

            # Extract links from the markdown content
            links = self._extract_links(markdown_content)

            # Extract metadata from the result if available
            metadata = self._extract_metadata(result, source)

            processing_time = int((time.time() - start_time) * 1000)

            return DocumentContent(
                markdown_content=markdown_content,
                source_path=source_str,
                source_format=self.FORMAT_MAP.get(detected_format, DocumentFormat.UNKNOWN),
                parser_used=self.name,
                metadata=metadata,
                links=links,
                processing_time_ms=processing_time,
                warnings=warnings,
            )
        except Exception as e:
            logger.error(f"MarkItDown parsing failed for {source_str}: {e}")
            raise

    def can_parse(
        self,
        source: str | Path,
        format_hint: str | None = None,
    ) -> bool:
        """Check if this parser can handle the given source.

        Args:
            source: File path or URL
            format_hint: Optional format override

        Returns:
            True if this parser can process the source
        """
        detected_format = format_hint or self._detect_format(source)
        return detected_format in (self.supported_formats | self.fallback_formats)

    def _detect_format(self, source: str | Path | BinaryIO | bytes) -> str:
        """Detect document format from source.

        Args:
            source: File path, URL, or stream

        Returns:
            Format string (e.g., "pdf", "youtube", "docx")
        """
        if isinstance(source, bytes | BinaryIO):
            return "unknown"

        source_str = str(source)

        # YouTube URL detection
        if "youtube.com" in source_str or "youtu.be" in source_str:
            return "youtube"

        # File extension
        ext = Path(source_str).suffix.lower().lstrip(".")
        return ext or "unknown"

    def _extract_links(self, markdown: str) -> list[str]:
        """Extract URLs from markdown content.

        Args:
            markdown: Markdown text content

        Returns:
            List of unique URLs found
        """
        # Match markdown links: [text](url)
        link_pattern = r"\[([^\]]*)\]\(([^)]+)\)"
        links = re.findall(link_pattern, markdown)
        urls = [url for _, url in links]

        # Also match bare URLs
        url_pattern = r"https?://[^\s\)\]>\"']+"
        bare_urls = re.findall(url_pattern, markdown)
        urls.extend(bare_urls)

        # Deduplicate while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    def _extract_metadata(
        self, result: object, source: str | Path | BinaryIO | bytes
    ) -> DocumentMetadata:
        """Extract document metadata from parse result.

        Args:
            result: MarkItDown conversion result
            source: Original source for fallback title

        Returns:
            DocumentMetadata with available fields
        """
        title = None

        # Try to extract title from result if available
        if hasattr(result, "title") and result.title:
            title = result.title

        # Fallback to filename for file sources
        if not title and not isinstance(source, bytes | BinaryIO):
            source_path = Path(str(source))
            if source_path.suffix:
                title = source_path.stem

        return DocumentMetadata(title=title)
