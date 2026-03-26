"""Kreuzberg parser implementation for async document extraction with broad format support."""

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, ClassVar

from src.models.document import (
    DocumentContent,
    DocumentFormat,
    DocumentMetadata,
    TableData,
)
from src.parsers.base import DocumentParser

if TYPE_CHECKING:
    import kreuzberg

logger = logging.getLogger(__name__)


# MIME type mapping for bytes-based extraction
EXTENSION_MIME_MAP: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "html": "text/html",
    "htm": "text/html",
    "epub": "application/epub+zip",
    "txt": "text/plain",
    "md": "text/markdown",
    "csv": "text/csv",
    "json": "application/json",
    "xml": "application/xml",
    "eml": "message/rfc822",
    "msg": "application/vnd.ms-outlook",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tiff": "image/tiff",
    "gif": "image/gif",
    "webp": "image/webp",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
}


class KreuzbergParser(DocumentParser):
    """Parser using Kreuzberg for async-native document extraction.

    Best for:
    - Broad format support (56+ formats including office, email, images, audio)
    - Async-native processing (no executor overhead)
    - OCR for scanned documents and images
    - Lightweight alternative to Docling for many formats

    Trade-offs:
    - Less sophisticated table structure extraction than Docling
    - May not handle complex PDF layouts as well as Docling
    """

    # Primary supported formats
    supported_formats: ClassVar[set[str]] = {
        "pdf",
        "docx",
        "pptx",
        "xlsx",
        "html",
        "htm",
        "epub",
        "txt",
        "md",
        "csv",
        "json",
        "xml",
        "eml",
        "msg",
        "png",
        "jpg",
        "jpeg",
        "tiff",
        "gif",
        "webp",
    }

    # Formats we can handle but another parser may do better
    fallback_formats: ClassVar[set[str]] = {"mp3", "wav"}

    # Extension to DocumentFormat mapping
    FORMAT_MAP: ClassVar[dict[str, DocumentFormat]] = {
        "pdf": DocumentFormat.PDF,
        "docx": DocumentFormat.DOCX,
        "pptx": DocumentFormat.PPTX,
        "xlsx": DocumentFormat.XLSX,
        "html": DocumentFormat.HTML,
        "htm": DocumentFormat.HTML,
        "epub": DocumentFormat.EPUB,
        "md": DocumentFormat.MARKDOWN,
        "markdown": DocumentFormat.MARKDOWN,
        "txt": DocumentFormat.TEXT,
        "csv": DocumentFormat.TEXT,
        "json": DocumentFormat.TEXT,
        "xml": DocumentFormat.TEXT,
        "eml": DocumentFormat.TEXT,
        "msg": DocumentFormat.OUTLOOK_MSG,
        "png": DocumentFormat.IMAGE,
        "jpg": DocumentFormat.IMAGE,
        "jpeg": DocumentFormat.IMAGE,
        "tiff": DocumentFormat.IMAGE,
        "gif": DocumentFormat.IMAGE,
        "webp": DocumentFormat.IMAGE,
        "mp3": DocumentFormat.AUDIO,
        "wav": DocumentFormat.AUDIO,
    }

    def __init__(
        self,
        max_file_size_mb: int = 100,
        timeout_seconds: int = 300,
    ) -> None:
        """Initialize the Kreuzberg parser.

        Args:
            max_file_size_mb: Maximum file size to process
            timeout_seconds: Processing timeout for large documents

        Raises:
            ImportError: If kreuzberg is not installed
        """
        self.max_file_size_mb = max_file_size_mb
        self.timeout_seconds = timeout_seconds

        # Verify kreuzberg is available at init time
        try:
            import kreuzberg as _kreuzberg  # noqa: F401
        except ImportError:
            raise ImportError(
                "kreuzberg is required for KreuzbergParser. Install it with: pip install kreuzberg"
            )

    @property
    def name(self) -> str:
        """Parser identifier."""
        return "kreuzberg"

    async def parse(
        self,
        source: str | Path | BinaryIO | bytes,
        format_hint: str | None = None,
    ) -> DocumentContent:
        """Parse document and return unified content model.

        Args:
            source: File path, URL, file-like object, or raw bytes
            format_hint: Optional format override

        Returns:
            DocumentContent with markdown, tables, and metadata
        """
        from kreuzberg import ExtractionConfig, OutputFormat, extract_bytes, extract_file

        start_time = time.time()
        warnings: list[str] = []

        source_str = str(source) if not isinstance(source, bytes | BinaryIO) else "stream"
        detected_format = format_hint or self._detect_format(source)

        # Check file size for path sources
        if isinstance(source, str | Path):
            path = Path(source)
            if path.exists():
                size_mb = path.stat().st_size / (1024 * 1024)
                if size_mb > self.max_file_size_mb:
                    raise ValueError(
                        f"File size ({size_mb:.1f}MB) exceeds limit ({self.max_file_size_mb}MB)"
                    )

        config = ExtractionConfig(output_format=OutputFormat.MARKDOWN)

        try:
            result: kreuzberg.ExtractionResult
            if isinstance(source, bytes):
                # Determine MIME type from format hint or default
                mime_type = EXTENSION_MIME_MAP.get(detected_format, "application/octet-stream")
                result = await asyncio.wait_for(
                    extract_bytes(source, mime_type=mime_type, config=config),
                    timeout=self.timeout_seconds,
                )
            elif isinstance(source, BinaryIO):
                # Read bytes from file-like object
                data = source.read()
                mime_type = EXTENSION_MIME_MAP.get(detected_format, "application/octet-stream")
                result = await asyncio.wait_for(
                    extract_bytes(data, mime_type=mime_type, config=config),
                    timeout=self.timeout_seconds,
                )
            else:
                # Path or URL string
                file_source: str | Path = (
                    Path(source)
                    if not str(source).startswith(("http://", "https://"))
                    else str(source)
                )
                result = await asyncio.wait_for(
                    extract_file(file_source, config=config),
                    timeout=self.timeout_seconds,
                )

            markdown_content = result.content

            # Extract tables
            tables = self._extract_tables(result)
            if tables:
                logger.debug(f"Extracted {len(tables)} tables from {source_str}")

            # Extract metadata
            metadata = self._extract_metadata(result, source)

            # Extract links from markdown
            links = self._extract_links(markdown_content)

            processing_time = int((time.time() - start_time) * 1000)

            return DocumentContent(
                markdown_content=markdown_content,
                source_path=source_str,
                source_format=self.FORMAT_MAP.get(detected_format, DocumentFormat.UNKNOWN),
                parser_used=self.name,
                metadata=metadata,
                tables=tables,
                links=links,
                processing_time_ms=processing_time,
                warnings=warnings,
            )
        except TimeoutError:
            logger.error(
                f"Kreuzberg parsing timed out after {self.timeout_seconds}s "
                f"for {source_str} (format: {detected_format})"
            )
            raise
        except Exception as e:
            logger.error(
                f"Kreuzberg parsing failed for {source_str} (format: {detected_format}): {e}"
            )
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
            Format string (e.g., "pdf", "docx")
        """
        if isinstance(source, bytes | BinaryIO):
            return "unknown"

        source_str = str(source)

        # File extension
        ext = Path(source_str).suffix.lower().lstrip(".")
        return ext or "unknown"

    def _extract_tables(self, result: "kreuzberg.ExtractionResult") -> list[TableData]:
        """Extract tables from Kreuzberg extraction result.

        Args:
            result: Kreuzberg extraction result

        Returns:
            List of TableData with markdown rendering
        """
        tables: list[TableData] = []

        if not hasattr(result, "tables") or not result.tables:
            return tables

        for table in result.tables:
            try:
                table_md = ""
                headers: list[str] = []
                rows: list[list[str]] = []

                # Get markdown rendering
                if hasattr(table, "markdown") and table.markdown:
                    table_md = table.markdown
                elif hasattr(table, "cells") and table.cells:
                    # Build markdown from cells (2D array)
                    table_md = self._cells_to_markdown(table.cells)

                # Extract structured data from cells if available
                if hasattr(table, "cells") and table.cells and len(table.cells) > 0:
                    headers = [str(cell) for cell in table.cells[0]]
                    rows = [[str(cell) for cell in row] for row in table.cells[1:]]

                # Ensure we have at least markdown content
                if not table_md and headers:
                    all_rows: list[list[str]] = [headers, *rows]
                    table_md = self._cells_to_markdown(all_rows)

                if table_md or headers:
                    tables.append(
                        TableData(
                            caption=None,
                            headers=headers,
                            rows=rows,
                            markdown=table_md,
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to extract table structure: {e}")
                if table_md:
                    tables.append(TableData(markdown=table_md))

        return tables

    def _cells_to_markdown(self, cells: list[list[str]]) -> str:
        """Convert a 2D cell array to markdown table format.

        Args:
            cells: 2D array of cell values

        Returns:
            Markdown-formatted table string
        """
        if not cells:
            return ""

        lines: list[str] = []

        # Header row
        header = [str(cell) for cell in cells[0]]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join("---" for _ in header) + " |")

        # Data rows
        for row in cells[1:]:
            row_strs = [str(cell) for cell in row]
            lines.append("| " + " | ".join(row_strs) + " |")

        return "\n".join(lines)

    def _extract_metadata(
        self, result: "kreuzberg.ExtractionResult", source: str | Path | BinaryIO | bytes
    ) -> DocumentMetadata:
        """Extract document metadata from Kreuzberg result.

        Args:
            result: Kreuzberg extraction result
            source: Original source for fallback title

        Returns:
            DocumentMetadata with available fields
        """
        title = None
        author = None
        page_count = None
        word_count = None
        language = None

        metadata = result.metadata

        # Extract title
        if hasattr(metadata, "get"):
            # Dict-like metadata access
            title = metadata.get("title")
            page_count = metadata.get("page_count")
            language = metadata.get("language")
            authors = metadata.get("authors")
            if authors and isinstance(authors, list):
                author = ", ".join(str(a) for a in authors)
            elif authors:
                author = str(authors)
        else:
            # Object-attribute metadata access
            if hasattr(metadata, "title") and metadata.title:
                title = str(metadata.title)
            if hasattr(metadata, "page_count") and metadata.page_count is not None:
                page_count = metadata.page_count
            if hasattr(metadata, "language") and metadata.language:
                language = str(metadata.language)
            if hasattr(metadata, "authors") and metadata.authors:
                if isinstance(metadata.authors, list):
                    author = ", ".join(str(a) for a in metadata.authors)
                else:
                    author = str(metadata.authors)

        # Try get_page_count() method if page_count not found
        if page_count is None and hasattr(result, "get_page_count"):
            try:
                count = result.get_page_count()
                if count and count > 0:
                    page_count = count
            except Exception:
                pass

        # Fallback to filename for title
        if not title and not isinstance(source, bytes | BinaryIO):
            source_path = Path(str(source))
            if source_path.suffix:
                title = source_path.stem

        # Calculate word count from content
        if result.content:
            word_count = len(result.content.split())

        # Extract language from detected_languages if not in metadata
        if not language and hasattr(result, "detected_languages") and result.detected_languages:
            language = result.detected_languages[0]

        return DocumentMetadata(
            title=title,
            author=author,
            page_count=page_count,
            word_count=word_count,
            language=language,
        )

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
        seen: set[str] = set()
        unique_urls: list[str] = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls
