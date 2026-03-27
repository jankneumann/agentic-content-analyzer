"""Type stub for KreuzbergParser — contract between work packages.

This file defines the public interface that wp-parser-adapter MUST implement
and wp-router-integration MUST consume. It is NOT shipped to production —
it serves as the coordination boundary between parallel agents.
"""

from pathlib import Path
from typing import BinaryIO, ClassVar

from src.models.document import DocumentContent, DocumentFormat
from src.parsers.base import DocumentParser


class KreuzbergParser(DocumentParser):
    """Parser using Kreuzberg for lightweight, high-throughput document extraction.

    Best for:
    - Broad format coverage (91+ formats)
    - High throughput batch processing
    - Lightweight deployment (no ML models)

    Trade-offs:
    - Less structural understanding than Docling for complex layouts
    - No deep table cell extraction (markdown tables only)
    """

    # Primary formats where Kreuzberg excels
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

    # Formats Kreuzberg can handle but others may do better
    fallback_formats: ClassVar[set[str]] = {
        "mp3",
        "wav",
    }

    # Extension to DocumentFormat mapping
    FORMAT_MAP: ClassVar[dict[str, DocumentFormat]] = {
        "pdf": DocumentFormat.PDF,
        "docx": DocumentFormat.DOCX,
        "pptx": DocumentFormat.PPTX,
        "xlsx": DocumentFormat.XLSX,
        "html": DocumentFormat.HTML,
        "htm": DocumentFormat.HTML,
        "epub": DocumentFormat.EPUB,
        "txt": DocumentFormat.TEXT,
        "md": DocumentFormat.MARKDOWN,
        "csv": DocumentFormat.TEXT,
        "json": DocumentFormat.TEXT,
        "xml": DocumentFormat.TEXT,
        "eml": DocumentFormat.OUTLOOK_MSG,
        "msg": DocumentFormat.OUTLOOK_MSG,
        "png": DocumentFormat.IMAGE,
        "jpg": DocumentFormat.IMAGE,
        "jpeg": DocumentFormat.IMAGE,
        "tiff": DocumentFormat.IMAGE,
        "gif": DocumentFormat.IMAGE,
        "webp": DocumentFormat.IMAGE,
    }

    def __init__(
        self,
        max_file_size_mb: int = 100,
        timeout_seconds: int = 120,
    ) -> None:
        """Initialize the Kreuzberg parser.

        Args:
            max_file_size_mb: Maximum file size to process.
            timeout_seconds: Processing timeout per document.
        """
        ...

    @property
    def name(self) -> str:
        """Returns 'kreuzberg'."""
        return "kreuzberg"

    async def parse(
        self,
        source: str | Path | BinaryIO | bytes,
        format_hint: str | None = None,
    ) -> DocumentContent:
        """Parse document using Kreuzberg's async extraction API.

        Uses kreuzberg.extract_file() for path sources and
        kreuzberg.extract_bytes() for bytes/stream sources.
        Configures OutputFormat.MARKDOWN for canonical output.

        Args:
            source: File path, URL, file-like object, or raw bytes.
            format_hint: Optional format override.

        Returns:
            DocumentContent with markdown_content, metadata, tables, links.

        Raises:
            ValueError: If file exceeds size limit.
            RuntimeError: If Kreuzberg extraction fails.
        """
        raise NotImplementedError("Contract stub — implement in wp-parser-adapter")

    def can_parse(
        self,
        source: str | Path,
        format_hint: str | None = None,
    ) -> bool:
        """Check if Kreuzberg can handle the given source format.

        Args:
            source: File path or URL to check.
            format_hint: Optional format override.

        Returns:
            True if format is in supported_formats or fallback_formats.
        """
        raise NotImplementedError("Contract stub — implement in wp-parser-adapter")
