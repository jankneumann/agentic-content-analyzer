"""Abstract base class for document parsers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, ClassVar

if TYPE_CHECKING:
    from src.models.document import DocumentContent


class DocumentParser(ABC):
    """Abstract interface for document parsers.

    All parsers must implement this interface to enable pluggable
    parsing backends (MarkItDown, Docling, etc.).
    """

    # Formats this parser handles well (primary responsibility)
    supported_formats: ClassVar[set[str]]

    # Formats this parser can handle but another may do better
    fallback_formats: ClassVar[set[str]]

    @abstractmethod
    async def parse(
        self,
        source: str | Path | BinaryIO | bytes,
        format_hint: str | None = None,
    ) -> "DocumentContent":
        """Parse document and return unified content model.

        Args:
            source: File path, URL, file-like object, or raw bytes
            format_hint: Optional format override (e.g., "pdf", "youtube")

        Returns:
            DocumentContent with markdown and optional structured data
        """
        pass

    @abstractmethod
    def can_parse(
        self,
        source: str | Path,
        format_hint: str | None = None,
    ) -> bool:
        """Check if this parser can handle the given source.

        Args:
            source: File path or URL to check
            format_hint: Optional format override

        Returns:
            True if this parser can process the source
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Parser identifier for logging and metrics."""
        pass
