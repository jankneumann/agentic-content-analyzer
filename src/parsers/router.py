"""Parser router for intelligent format-based parser selection."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Optional

from src.models.document import DocumentContent

if TYPE_CHECKING:
    from src.parsers.base import DocumentParser

logger = logging.getLogger(__name__)


class ParserRouter:
    """Routes documents to the appropriate parser based on format.

    The router uses a routing table to determine which parser handles
    each format best, with support for fallback parsers and OCR detection.
    """

    # Format → preferred parser mapping
    ROUTING_TABLE: ClassVar[dict[str, str]] = {
        # MarkItDown handles these well (lighter, faster)
        "docx": "markitdown",
        "pptx": "markitdown",
        "xlsx": "markitdown",
        "html": "markitdown",
        "htm": "markitdown",
        "txt": "markitdown",
        "md": "markitdown",
        "epub": "markitdown",
        "msg": "markitdown",
        # YouTube - specialized parser with timestamp support
        "youtube": "youtube",
        # Audio - MarkItDown handles these
        "mp3": "markitdown",
        "wav": "markitdown",
        "m4a": "markitdown",
        # Docling excels at these (when available)
        "pdf": "docling",
        # Images - Docling for OCR (when available)
        "png": "docling",
        "jpg": "docling",
        "jpeg": "docling",
    }

    # Formats requiring OCR should always use Docling
    OCR_REQUIRED_INDICATORS: ClassVar[list[str]] = ["scanned", "scan", "ocr"]

    def __init__(
        self,
        markitdown_parser: "DocumentParser",
        docling_parser: Optional["DocumentParser"] = None,
        youtube_parser: Optional["DocumentParser"] = None,
        kreuzberg_parser: Optional["DocumentParser"] = None,
        kreuzberg_preferred_formats: set[str] | None = None,
        kreuzberg_shadow_formats: set[str] | None = None,
        default_parser: str = "markitdown",
    ):
        """Initialize the parser router.

        Args:
            markitdown_parser: MarkItDown parser instance (always required)
            docling_parser: Optional Docling parser for advanced PDF/OCR
            youtube_parser: Optional YouTube parser for timestamped transcripts
            kreuzberg_parser: Optional Kreuzberg parser for document extraction
            kreuzberg_preferred_formats: Formats that should prefer Kreuzberg
            kreuzberg_shadow_formats: Formats for shadow comparison evaluation
            default_parser: Parser to use for unknown formats
        """
        self.parsers: dict[str, DocumentParser] = {
            "markitdown": markitdown_parser,
        }
        if docling_parser:
            self.parsers["docling"] = docling_parser
        if youtube_parser:
            self.parsers["youtube"] = youtube_parser
        if kreuzberg_parser:
            self.parsers["kreuzberg"] = kreuzberg_parser

        self.default_parser = default_parser
        self._has_docling = docling_parser is not None
        self._has_youtube = youtube_parser is not None
        self._has_kreuzberg = kreuzberg_parser is not None
        self._kreuzberg_preferred: set[str] = kreuzberg_preferred_formats or set()
        self._kreuzberg_shadow: set[str] = kreuzberg_shadow_formats or set()

    def route(
        self,
        source: str | Path,
        format_hint: str | None = None,
        prefer_structured: bool = False,
        ocr_needed: bool = False,
    ) -> "DocumentParser":
        """Select the best parser for the given document.

        Args:
            source: File path or URL
            format_hint: Explicit format override
            prefer_structured: If True, prefer Docling for table extraction
            ocr_needed: If True, force Docling for OCR capability

        Returns:
            The most appropriate parser for the source
        """
        # Detect format
        detected_format = format_hint or self._detect_format(source)

        # OCR always needs Docling (if available)
        if (ocr_needed or self._likely_needs_ocr(source)) and self._has_docling:
            logger.debug(f"Routing {source} to docling (OCR required)")
            return self.parsers["docling"]

        # Prefer structured extraction for PDFs with tables
        if prefer_structured and detected_format == "pdf" and self._has_docling:
            logger.debug(f"Routing {source} to docling (structured extraction preferred)")
            return self.parsers["docling"]

        # Kreuzberg preference (if available and format is preferred)
        if self._has_kreuzberg and detected_format in self._kreuzberg_preferred:
            logger.debug(f"Routing {source} to kreuzberg (format preferred)")
            return self.parsers["kreuzberg"]

        # Use routing table
        parser_name = self.ROUTING_TABLE.get(detected_format, self.default_parser)

        # Fallback to markitdown if specialized parser not available
        if parser_name == "docling" and not self._has_docling:
            logger.debug(f"Routing {source} to markitdown (docling not available)")
            parser_name = "markitdown"
        elif parser_name == "youtube" and not self._has_youtube:
            logger.debug(f"Routing {source} to markitdown (youtube parser not available)")
            parser_name = "markitdown"
        elif parser_name == "kreuzberg" and not self._has_kreuzberg:
            logger.debug(f"Routing {source} to markitdown (kreuzberg not available)")
            parser_name = "markitdown"
        else:
            logger.debug(f"Routing {source} to {parser_name}")

        return self.parsers[parser_name]

    async def parse(
        self,
        source: str | Path | bytes,
        format_hint: str | None = None,
        prefer_structured: bool = False,
        ocr_needed: bool = False,
    ) -> DocumentContent:
        """Route and parse in one call.

        Args:
            source: File path, URL, or bytes
            format_hint: Explicit format override
            prefer_structured: If True, prefer Docling for table extraction
            ocr_needed: If True, force Docling for OCR capability

        Returns:
            Parsed DocumentContent
        """
        # For bytes, use default parser
        if isinstance(source, bytes):
            parser = self.parsers[self.default_parser]
        else:
            parser = self.route(
                source,
                format_hint=format_hint,
                prefer_structured=prefer_structured,
                ocr_needed=ocr_needed,
            )

        result = await parser.parse(source, format_hint=format_hint)

        # Shadow evaluation: fire-and-forget Kreuzberg comparison
        if self._has_kreuzberg and self._kreuzberg_shadow:
            detected_format = format_hint or (
                self._detect_format(source) if not isinstance(source, bytes) else "unknown"
            )
            from src.parsers.shadow import maybe_shadow_parse

            maybe_shadow_parse(
                shadow_parser=self.parsers.get("kreuzberg"),
                shadow_formats=self._kreuzberg_shadow,
                detected_format=detected_format,
                canonical_result=result,
                source=source,
                format_hint=format_hint,
            )

        return result

    def _detect_format(self, source: str | Path) -> str:
        """Detect format from file extension or URL pattern.

        Args:
            source: File path or URL

        Returns:
            Format string (e.g., "pdf", "youtube")
        """
        source_str = str(source)

        # YouTube URL detection
        if "youtube.com" in source_str or "youtu.be" in source_str:
            return "youtube"

        # File extension
        ext = Path(source_str).suffix.lower().lstrip(".")
        return ext or "unknown"

    def _likely_needs_ocr(self, source: str | Path) -> bool:
        """Heuristic: filename contains OCR indicators.

        Args:
            source: File path or URL

        Returns:
            True if the filename suggests OCR is needed
        """
        name = Path(str(source)).stem.lower()
        return any(ind in name for ind in self.OCR_REQUIRED_INDICATORS)

    @property
    def available_parsers(self) -> list[str]:
        """List of available parser names."""
        return list(self.parsers.keys())

    @property
    def has_docling(self) -> bool:
        """Whether Docling parser is available."""
        return self._has_docling

    @property
    def has_youtube(self) -> bool:
        """Whether YouTube parser is available."""
        return self._has_youtube

    @property
    def has_kreuzberg(self) -> bool:
        """Whether Kreuzberg parser is available."""
        return self._has_kreuzberg
