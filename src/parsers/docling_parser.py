"""Docling parser implementation for advanced document parsing with table extraction."""

import asyncio
import functools
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
    from docling.datamodel.document import DoclingDocument
    from docling.document_converter import ConversionResult

logger = logging.getLogger(__name__)


class DoclingParser(DocumentParser):
    """Parser using IBM's Docling library for advanced document processing.

    Best for:
    - Complex PDF layouts with multi-column text
    - Documents with tables requiring structured extraction
    - Scanned documents (OCR) when enabled
    - Images containing text
    - Documents needing layout analysis

    Trade-offs:
    - Heavier dependencies (ML models)
    - Slower processing than MarkItDown
    - Higher memory usage
    """

    # Primary supported formats
    supported_formats: ClassVar[set[str]] = {
        "pdf",
        "docx",
        "png",
        "jpg",
        "jpeg",
        "html",
        "pptx",
        "xlsx",
        "md",
    }

    # Formats we can handle but MarkItDown may be sufficient
    fallback_formats: ClassVar[set[str]] = {"txt"}

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
        "png": DocumentFormat.IMAGE,
        "jpg": DocumentFormat.IMAGE,
        "jpeg": DocumentFormat.IMAGE,
        "tiff": DocumentFormat.IMAGE,
        "bmp": DocumentFormat.IMAGE,
    }

    def __init__(
        self,
        enable_ocr: bool = False,
        max_file_size_mb: int = 100,
        timeout_seconds: int = 300,
    ) -> None:
        """Initialize the Docling parser.

        Args:
            enable_ocr: Enable OCR for scanned documents (requires docling[ocr])
            max_file_size_mb: Maximum file size to process
            timeout_seconds: Processing timeout for large documents
        """
        self.enable_ocr = enable_ocr
        self.max_file_size_mb = max_file_size_mb
        self.timeout_seconds = timeout_seconds
        self._converter: object | None = None

    @property
    def converter(self) -> object:
        """Lazy-load the DocumentConverter to defer heavy import."""
        if self._converter is None:
            from docling.document_converter import DocumentConverter

            self._converter = DocumentConverter()
        return self._converter

    @property
    def name(self) -> str:
        """Parser identifier."""
        return "docling"

    async def parse(
        self,
        source: str | Path | BinaryIO | bytes,
        format_hint: str | None = None,
    ) -> DocumentContent:
        """Parse document and return unified content model.

        Args:
            source: File path, URL, or bytes
            format_hint: Optional format override

        Returns:
            DocumentContent with markdown, tables, and metadata
        """
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

        try:
            # Convert document using Docling
            # Offload blocking conversion to executor
            loop = asyncio.get_running_loop()
            result: ConversionResult = await loop.run_in_executor(
                None,
                functools.partial(self.converter.convert, source),  # type: ignore[attr-defined]
            )
            doc: DoclingDocument = result.document  # type: ignore[assignment]

            # Export to markdown as primary content
            markdown_content = doc.export_to_markdown()

            # Extract structured tables
            tables = self._extract_tables(doc)
            if tables:
                logger.debug(f"Extracted {len(tables)} tables from {source_str}")

            # Extract metadata
            metadata = self._extract_metadata(doc, source)

            # Extract links from markdown
            links = self._extract_links(markdown_content)

            # Check for OCR warnings
            if self._likely_needs_ocr(source) and not self.enable_ocr:
                warnings.append(
                    "Document may be scanned but OCR is disabled. "
                    "Enable OCR for better text extraction."
                )

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
        except Exception as e:
            logger.error(f"Docling parsing failed for {source_str}: {e}")
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

    def _likely_needs_ocr(self, source: str | Path | BinaryIO | bytes) -> bool:
        """Heuristic: filename contains OCR indicators or is an image.

        Args:
            source: File path or stream

        Returns:
            True if the source likely needs OCR
        """
        if isinstance(source, bytes | BinaryIO):
            return False

        source_str = str(source).lower()
        name = Path(source_str).stem.lower()

        # Check for OCR indicators in filename
        ocr_indicators = ["scanned", "scan", "ocr"]
        if any(ind in name for ind in ocr_indicators):
            return True

        # Image files typically need OCR for text extraction
        ext = Path(source_str).suffix.lower().lstrip(".")
        image_formats = {"png", "jpg", "jpeg", "tiff", "bmp", "gif"}
        return ext in image_formats

    def _extract_tables(self, doc: "DoclingDocument") -> list[TableData]:
        """Extract structured tables from DoclingDocument.

        Args:
            doc: Parsed Docling document

        Returns:
            List of TableData with headers, rows, and markdown fallback
        """
        tables: list[TableData] = []

        # Access tables from the document
        if not hasattr(doc, "tables") or not doc.tables:
            return tables

        for table in doc.tables:
            try:
                # Extract table as markdown for fallback
                table_md = ""
                if hasattr(table, "export_to_markdown"):
                    table_md = table.export_to_markdown()

                # Try to extract structured data
                headers: list[str] = []
                rows: list[list[str]] = []
                caption: str | None = None

                # Get caption if available
                if hasattr(table, "caption") and table.caption:
                    caption = str(table.caption)

                # Try to get structured table data
                if hasattr(table, "data") and table.data:
                    data = table.data
                    if hasattr(data, "grid") and data.grid:
                        grid = data.grid
                        if len(grid) > 0:
                            # First row as headers
                            headers = [self._cell_to_text(cell) for cell in grid[0]]
                            # Rest as rows
                            rows = [[self._cell_to_text(cell) for cell in row] for row in grid[1:]]

                tables.append(
                    TableData(
                        caption=caption,
                        headers=headers,
                        rows=rows,
                        markdown=table_md,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to extract table structure: {e}")
                # Still add with just markdown fallback
                if table_md:
                    tables.append(TableData(markdown=table_md))

        return tables

    def _cell_to_text(self, cell: object) -> str:
        """Convert a table cell to text.

        Args:
            cell: Table cell object

        Returns:
            Text content of the cell
        """
        if cell is None:
            return ""
        if isinstance(cell, str):
            return cell
        if hasattr(cell, "text"):
            return str(cell.text) if cell.text else ""
        return str(cell)

    def _extract_metadata(
        self, doc: "DoclingDocument", source: str | Path | BinaryIO | bytes
    ) -> DocumentMetadata:
        """Extract document metadata from DoclingDocument.

        Args:
            doc: Parsed Docling document
            source: Original source for fallback title

        Returns:
            DocumentMetadata with available fields
        """
        title = None
        author = None
        page_count = None

        # Try to get title from document
        if hasattr(doc, "name") and doc.name:
            title = str(doc.name)

        # Try to get metadata from origin if available
        if hasattr(doc, "origin") and doc.origin:
            origin = doc.origin
            if hasattr(origin, "filename") and origin.filename:
                if not title:
                    title = Path(str(origin.filename)).stem

        # Try to get page count
        if hasattr(doc, "pages") and doc.pages:
            page_count = len(doc.pages)

        # Fallback to filename for title
        if not title and not isinstance(source, bytes | BinaryIO):
            source_path = Path(str(source))
            if source_path.suffix:
                title = source_path.stem

        # Calculate word count from content
        word_count = None
        if hasattr(doc, "export_to_markdown"):
            md_content = doc.export_to_markdown()
            word_count = len(md_content.split())

        return DocumentMetadata(
            title=title,
            author=author,
            page_count=page_count,
            word_count=word_count,
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
