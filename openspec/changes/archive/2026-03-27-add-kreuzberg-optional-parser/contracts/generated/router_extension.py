"""Type stub for ParserRouter extension — contract for wp-router-integration.

Shows the DELTA to the existing ParserRouter interface. Only new/changed
signatures are listed here.
"""

from typing import Optional

from src.parsers.base import DocumentParser


class ParserRouter:
    """Extended constructor signature and routing additions."""

    def __init__(
        self,
        markitdown_parser: "DocumentParser",
        docling_parser: Optional["DocumentParser"] = None,
        youtube_parser: Optional["DocumentParser"] = None,
        kreuzberg_parser: Optional["DocumentParser"] = None,  # NEW
        default_parser: str = "markitdown",
        kreuzberg_preferred_formats: set[str] | None = None,  # NEW
    ) -> None:
        """Initialize with optional Kreuzberg parser.

        Args:
            markitdown_parser: MarkItDown parser instance (always required).
            docling_parser: Optional Docling parser for advanced PDF/OCR.
            youtube_parser: Optional YouTube parser for transcripts.
            kreuzberg_parser: Optional Kreuzberg parser for broad format support.
            default_parser: Parser to use for unknown formats.
            kreuzberg_preferred_formats: Formats where Kreuzberg takes precedence
                over the ROUTING_TABLE default (e.g., {"docx", "epub", "html"}).
        """
        ...

    @property
    def has_kreuzberg(self) -> bool:
        """Whether Kreuzberg parser is available."""
        raise NotImplementedError("Contract stub — implement in wp-router-integration")
