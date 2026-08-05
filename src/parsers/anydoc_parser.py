"""Anydoc parser implementation for fast Rust-based office document conversion."""

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
    import anydoc

logger = logging.getLogger(__name__)


class AnydocParser(DocumentParser):
    """Parser using Firecrawl's anydoc for fast office document conversion.

    Best for:
    - Office formats (Word, PowerPoint, Excel, OpenDocument, RTF, EPUB, CSV)
    - Speed: pure Rust core, single-digit-millisecond conversions
    - Consistent GitHub-Flavored Markdown output across all input formats
    - Fully local processing (no ML models, no external services)

    Trade-offs:
    - Text-based PDFs only — no OCR for scanned documents (use Docling)
    - Images render as alt text; no image/layout understanding
    - No document metadata extraction (title falls back to filename)
    """

    # Primary supported formats (anydoc's native format list)
    supported_formats: ClassVar[set[str]] = {
        "doc",
        "docx",
        "docm",
        "ppt",
        "pps",
        "pot",
        "pptx",
        "pptm",
        "ppsx",
        "ppsm",
        "xls",
        "xlsx",
        "xlsm",
        "xlsb",
        "odt",
        "ods",
        "odp",
        "rtf",
        "epub",
        "csv",
    }

    # PDF works for text-based files but Docling handles scans/OCR better
    fallback_formats: ClassVar[set[str]] = {"pdf"}

    # Extension to DocumentFormat mapping
    FORMAT_MAP: ClassVar[dict[str, DocumentFormat]] = {
        "pdf": DocumentFormat.PDF,
        "doc": DocumentFormat.DOCX,
        "docx": DocumentFormat.DOCX,
        "docm": DocumentFormat.DOCX,
        "ppt": DocumentFormat.PPTX,
        "pps": DocumentFormat.PPTX,
        "pot": DocumentFormat.PPTX,
        "pptx": DocumentFormat.PPTX,
        "pptm": DocumentFormat.PPTX,
        "ppsx": DocumentFormat.PPTX,
        "ppsm": DocumentFormat.PPTX,
        "xls": DocumentFormat.XLSX,
        "xlsx": DocumentFormat.XLSX,
        "xlsm": DocumentFormat.XLSX,
        "xlsb": DocumentFormat.XLSX,
        "epub": DocumentFormat.EPUB,
        "csv": DocumentFormat.TEXT,
        "rtf": DocumentFormat.TEXT,
    }

    def __init__(
        self,
        max_file_size_mb: int = 100,
        timeout_seconds: int = 60,
        extract_tables: bool = True,
    ) -> None:
        """Initialize the Anydoc parser.

        Args:
            max_file_size_mb: Maximum file size to process
            timeout_seconds: Processing timeout (anydoc is fast; this is a safety net)
            extract_tables: Whether to extract structured tables via the document model

        Raises:
            ImportError: If anydoc is not installed
        """
        self.max_file_size_mb = max_file_size_mb
        self.timeout_seconds = timeout_seconds
        self.extract_tables = extract_tables

        # Verify anydoc is available at init time
        try:
            import anydoc as _anydoc  # noqa: F401
        except ImportError:
            raise ImportError(
                "anydoc is required for AnydocParser. Install it with: pip install firecrawl-anydoc"
            )

    @property
    def name(self) -> str:
        """Parser identifier."""
        return "anydoc"

    async def parse(
        self,
        source: str | Path | BinaryIO | bytes,
        format_hint: str | None = None,
    ) -> DocumentContent:
        """Parse document and return unified content model.

        Args:
            source: File path, file-like object, or raw bytes (URLs unsupported)
            format_hint: Optional format override

        Returns:
            DocumentContent with markdown, tables, and metadata
        """
        start_time = time.time()
        warnings: list[str] = []

        source_str = (
            str(source) if not (isinstance(source, bytes) or hasattr(source, "read")) else "stream"
        )
        detected_format = format_hint or self._detect_format(source)

        # Resolve source to bytes: anydoc converts in-memory, and having the
        # bytes lets us reuse them for structured table extraction.
        if isinstance(source, bytes):
            data = source
        elif hasattr(source, "read"):
            data = source.read()
        else:
            if str(source).startswith(("http://", "https://")):
                raise ValueError(
                    f"AnydocParser does not fetch URLs: {source_str}. "
                    "Download the file first or route to another parser."
                )
            path = Path(source)
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > self.max_file_size_mb:
                raise ValueError(
                    f"File size ({size_mb:.1f}MB) exceeds limit ({self.max_file_size_mb}MB)"
                )
            data = path.read_bytes()

        # Only pass a format anydoc recognizes; content auto-detection covers
        # the rest (CSV is signature-less and needs the explicit hint).
        anydoc_format = (
            detected_format
            if detected_format in self.supported_formats | self.fallback_formats
            else None
        )

        try:
            markdown_content = await asyncio.wait_for(
                asyncio.to_thread(self._convert, data, anydoc_format),
                timeout=self.timeout_seconds,
            )

            # anydoc's document model does not support PDF (PDF converts
            # straight to markdown), so skip structured table extraction.
            is_pdf = detected_format == "pdf" or data[:5] == b"%PDF-"
            tables: list[TableData] = []
            if self.extract_tables and not is_pdf:
                try:
                    tables = await asyncio.wait_for(
                        asyncio.to_thread(self._extract_tables, data, anydoc_format),
                        timeout=self.timeout_seconds,
                    )
                except Exception as e:
                    warnings.append(f"Structured table extraction failed: {e}")
                    logger.warning(f"Anydoc table extraction failed for {source_str}: {e}")

            metadata = self._build_metadata(markdown_content, source)
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
                f"Anydoc parsing timed out after {self.timeout_seconds}s "
                f"for {source_str} (format: {detected_format})"
            )
            raise
        except Exception as e:
            logger.error(f"Anydoc parsing failed for {source_str} (format: {detected_format}): {e}")
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
        if str(source).startswith(("http://", "https://")):
            return False
        detected_format = format_hint or self._detect_format(source)
        return detected_format in (self.supported_formats | self.fallback_formats)

    def _convert(self, data: bytes, anydoc_format: str | None) -> str:
        """Convert document bytes to markdown (runs in a worker thread)."""
        import anydoc

        return anydoc.to_markdown_bytes(data, anydoc_format)

    def _detect_format(self, source: str | Path | BinaryIO | bytes) -> str:
        """Detect document format from source.

        Args:
            source: File path, URL, or stream

        Returns:
            Format string (e.g., "pdf", "docx")
        """
        if isinstance(source, bytes) or hasattr(source, "read"):
            return "unknown"

        ext = Path(str(source)).suffix.lower().lstrip(".")
        return ext or "unknown"

    def _extract_tables(self, data: bytes, anydoc_format: str | None) -> list[TableData]:
        """Extract structured tables via anydoc's document model (worker thread).

        Args:
            data: Raw document bytes
            anydoc_format: Explicit anydoc format string, or None for auto-detect

        Returns:
            List of TableData with headers, rows, and markdown rendering
        """
        import anydoc

        document = anydoc.to_document(data)
        tables: list[TableData] = []
        for block in self._walk_blocks(document.blocks):
            if block.kind != "table" or block.table is None:
                continue
            grid: list[list[str]] = []
            for row in block.table.grid:
                grid.append(
                    [
                        self._block_text(slot.cell.blocks) if slot.cell is not None else ""
                        for slot in row
                    ]
                )
            if not grid:
                continue

            # anydoc reports how many leading rows are headers; treat the
            # first row as the header when the source marked none.
            header_rows = block.table.header_rows or 1
            headers = grid[0] if grid else []
            rows = grid[header_rows:]
            tables.append(
                TableData(
                    caption=None,
                    headers=headers,
                    rows=rows,
                    markdown=self._cells_to_markdown(grid),
                )
            )
        return tables

    def _walk_blocks(self, blocks: "list[anydoc.Block]") -> "list[anydoc.Block]":
        """Flatten the block tree depth-first (tables can nest in lists/cells)."""
        flat: list = []
        for block in blocks or []:
            flat.append(block)
            if block.blocks:
                flat.extend(self._walk_blocks(block.blocks))
        return flat

    def _inline_text(self, inlines: "list[anydoc.Inline] | None") -> str:
        """Concatenate text from an inline tree."""
        parts: list[str] = []
        for inline in inlines or []:
            if inline.text:
                parts.append(inline.text)
            if inline.content:
                parts.append(self._inline_text(inline.content))
        return "".join(parts)

    def _block_text(self, blocks: "list[anydoc.Block] | None") -> str:
        """Concatenate text from a block tree (used for table cells)."""
        parts: list[str] = []
        for block in blocks or []:
            if block.text:
                parts.append(block.text)
            if block.content:
                parts.append(self._inline_text(block.content))
            if block.blocks:
                parts.append(self._block_text(block.blocks))
        return " ".join(p for p in parts if p)

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
        header = [str(cell) for cell in cells[0]]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join("---" for _ in header) + " |")
        for row in cells[1:]:
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")

        return "\n".join(lines)

    def _build_metadata(
        self, markdown: str, source: str | Path | BinaryIO | bytes
    ) -> DocumentMetadata:
        """Build metadata from markdown content and source.

        anydoc's document model carries no document properties, so title
        falls back to the filename and word count is computed from content.

        Args:
            markdown: Converted markdown content
            source: Original source for fallback title

        Returns:
            DocumentMetadata with available fields
        """
        title = None
        if not (isinstance(source, bytes) or hasattr(source, "read")):
            source_path = Path(str(source))
            if source_path.suffix:
                title = source_path.stem

        word_count = len(markdown.split()) if markdown else None

        return DocumentMetadata(title=title, word_count=word_count)

    def _extract_links(self, markdown: str) -> list[str]:
        """Extract URLs from markdown content.

        Args:
            markdown: Markdown text content

        Returns:
            List of unique URLs found
        """
        link_pattern = r"\[([^\]]*)\]\(([^)]+)\)"
        links = re.findall(link_pattern, markdown)
        urls = [url for _, url in links]

        url_pattern = r"https?://[^\s\)\]>\"']+"
        urls.extend(re.findall(url_pattern, markdown))

        seen: set[str] = set()
        unique_urls: list[str] = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls
