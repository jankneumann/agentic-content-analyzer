"""Document content models for unified parser output."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DocumentFormat(str, Enum):
    """Supported input document formats."""

    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    HTML = "html"
    MARKDOWN = "md"
    TEXT = "txt"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    YOUTUBE = "youtube"
    OUTLOOK_MSG = "msg"
    EPUB = "epub"
    UNKNOWN = "unknown"


class TableData(BaseModel):
    """Extracted table with optional structure.

    When a parser provides structured data (like Docling), headers and rows
    will be populated. The markdown field is always available as a fallback.
    """

    caption: str | None = None
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    markdown: str = Field(description="Table rendered as markdown (always available)")


class DocumentMetadata(BaseModel):
    """Document metadata extracted during parsing."""

    title: str | None = None
    author: str | None = None
    created_date: datetime | None = None
    modified_date: datetime | None = None
    page_count: int | None = None
    word_count: int | None = None
    language: str | None = None


class DocumentContent(BaseModel):
    """Unified document representation from any parser.

    Markdown is the PRIMARY content format - optimized for LLM consumption.
    Structured data (tables, metadata) is OPTIONAL and parser-dependent.

    This model provides a common interface regardless of which parser
    (MarkItDown, Docling, etc.) produced the content.
    """

    # === Required: Always populated ===
    markdown_content: str = Field(description="Primary content as markdown - the main LLM input")
    source_path: str = Field(description="Original file path, URL, or identifier")
    source_format: DocumentFormat = Field(description="Detected or specified input format")
    parser_used: str = Field(
        description="Which parser produced this content (markitdown/docling/youtube)"
    )

    # === Optional: Populated when available ===
    metadata: DocumentMetadata = Field(
        default_factory=DocumentMetadata,
        description="Document metadata (title, author, etc.)",
    )
    tables: list[TableData] = Field(
        default_factory=list,
        description="Extracted tables with structure (parser-dependent)",
    )
    links: list[str] = Field(default_factory=list, description="URLs extracted from document")

    # === Processing info ===
    processing_time_ms: int = Field(default=0, description="Time spent parsing")
    warnings: list[str] = Field(default_factory=list, description="Non-fatal issues during parsing")

    def to_newsletter_content(self) -> tuple[str, str, list[str]]:
        """Convert to newsletter model fields.

        Returns:
            Tuple of (raw_text, raw_html, extracted_links)
        """
        return (
            self.markdown_content,  # Goes to raw_text
            self.markdown_content,  # Also raw_html (markdown is valid)
            self.links,
        )
