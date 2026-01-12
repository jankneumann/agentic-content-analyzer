"""Unified Content model for all ingested content.

This module provides a unified Content model that replaces the separate
Newsletter and Document models. All content is stored with markdown as
the canonical format, aligning with parser output.

Content Sources:
- GMAIL: Email newsletters via Gmail API
- RSS: RSS/Atom feed articles
- FILE_UPLOAD: Uploaded documents (PDF, DOCX, etc.)
- YOUTUBE: YouTube video transcripts
- MANUAL: Manually created content via API
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, relationship

from src.models.newsletter import Base


class ContentSource(str, Enum):
    """Content source types.

    Unified enum replacing NewsletterSource with additional values
    for future content sources.
    """

    GMAIL = "gmail"
    RSS = "rss"
    FILE_UPLOAD = "file_upload"
    YOUTUBE = "youtube"
    MANUAL = "manual"  # Manually created via API
    WEBPAGE = "webpage"  # Future: scraped web pages
    OTHER = "other"


class ContentStatus(str, Enum):
    """Processing status for content."""

    PENDING = "pending"  # Ingested, awaiting parsing
    PARSING = "parsing"  # Parser running
    PARSED = "parsed"  # Parsed, awaiting summarization
    PROCESSING = "processing"  # Summarization in progress
    COMPLETED = "completed"  # Fully processed
    FAILED = "failed"  # Processing failed


class Content(Base):  # type: ignore[valid-type, misc]
    """Unified content model for all ingested content.

    Stores content from all sources (Gmail, RSS, file uploads, YouTube)
    with markdown as the canonical format. This replaces the previous
    Newsletter + Document model combination.

    Key design decisions:
    - markdown_content is the primary content field (always populated)
    - raw_content preserves original format for re-parsing if needed
    - Structured data (tables, links) stored in JSON for querying
    - content_hash enables deduplication across all sources
    """

    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Source identification
    # Note: values_callable ensures SQLAlchemy uses enum .value (lowercase)
    # instead of .name (uppercase) to match the database enum definition
    source_type = Column(
        SQLEnum(ContentSource, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    source_id = Column(String(500), nullable=False)  # Unique ID from source
    source_url = Column(String(2000), nullable=True)  # Original URL if available

    # Identity / Metadata
    title = Column(String(1000), nullable=False)
    author = Column(String(500), nullable=True)  # Sender for email, channel for YouTube
    publication = Column(String(500), nullable=True, index=True)  # Newsletter/channel name
    published_date = Column(DateTime, nullable=True, index=True)

    # Canonical content - MARKDOWN FIRST
    markdown_content = Column(Text, nullable=False)  # Primary content, always populated

    # Structured extractions (parsed from markdown or source)
    tables_json = Column(JSON, nullable=True)  # List of TableData for complex tables
    links_json = Column(JSON, nullable=True)  # Extracted URLs for link analysis
    metadata_json = Column(
        JSON, nullable=True
    )  # Additional metadata (page_count, word_count, etc.)

    # Raw preservation (optional, for re-parsing)
    raw_content = Column(Text, nullable=True)  # Original HTML, transcript JSON, etc.
    raw_format = Column(String(50), nullable=True)  # "html", "text", "transcript_json"

    # Parsing metadata
    parser_used = Column(String(100), nullable=True)  # "DoclingParser", "YouTubeParser", etc.
    parser_version = Column(String(50), nullable=True)  # For tracking re-parsing needs

    # Deduplication
    content_hash = Column(String(64), nullable=False, index=True)  # SHA-256 of normalized markdown
    canonical_id = Column(
        Integer,
        ForeignKey("contents.id", ondelete="SET NULL"),
        nullable=True,
    )  # FK to canonical Content if duplicate

    # Processing status
    # Note: values_callable ensures SQLAlchemy uses enum .value (lowercase)
    # instead of .name (uppercase) to match the database enum definition
    status = Column(
        SQLEnum(ContentStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ContentStatus.PENDING,
        index=True,
    )
    error_message = Column(Text, nullable=True)

    # Timestamps
    ingested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    parsed_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)  # When summarization completed

    # Relationships
    canonical: Mapped["Content | None"] = relationship(
        "Content",
        remote_side="Content.id",
        foreign_keys=[canonical_id],
    )
    # Note: Summary relationship will be added in Phase 2 when we create
    # a new Summary model that links to Content instead of Newsletter

    # Composite unique constraint on source_type + source_id
    __table_args__ = (
        Index("idx_contents_source", "source_type", "source_id", unique=True),
        Index("idx_contents_publication_date", "publication", "published_date"),
    )

    def __repr__(self) -> str:
        return f"<Content(id={self.id}, source={self.source_type.value}, title='{self.title[:50]}...')>"


# --- Pydantic Schemas ---


class ContentCreate(BaseModel):
    """Schema for creating new content."""

    source_type: ContentSource
    source_id: str
    source_url: str | None = None

    title: str
    author: str | None = None
    publication: str | None = None
    published_date: datetime | None = None

    markdown_content: str
    tables_json: list[dict] | None = None
    links_json: list[str] | None = None
    metadata_json: dict | None = None

    raw_content: str | None = None
    raw_format: str | None = None

    parser_used: str | None = None
    parser_version: str | None = None

    content_hash: str


class ContentUpdate(BaseModel):
    """Schema for updating content."""

    title: str | None = None
    author: str | None = None
    publication: str | None = None
    published_date: datetime | None = None

    markdown_content: str | None = None
    tables_json: list[dict] | None = None
    links_json: list[str] | None = None
    metadata_json: dict | None = None

    status: ContentStatus | None = None
    error_message: str | None = None


class ContentResponse(BaseModel):
    """Schema for content API responses."""

    id: int
    source_type: ContentSource
    source_id: str
    source_url: str | None = None

    title: str
    author: str | None = None
    publication: str | None = None
    published_date: datetime | None = None

    markdown_content: str
    tables_json: list[dict] | None = None
    links_json: list[str] | None = None
    metadata_json: dict | None = None

    parser_used: str | None = None
    content_hash: str
    canonical_id: int | None = None

    status: ContentStatus
    error_message: str | None = None

    ingested_at: datetime
    parsed_at: datetime | None = None
    processed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ContentListItem(BaseModel):
    """Lightweight schema for listing content."""

    id: int
    source_type: ContentSource
    title: str
    publication: str | None = None
    published_date: datetime | None = None
    status: ContentStatus
    ingested_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContentListResponse(BaseModel):
    """Paginated content list response."""

    items: list[ContentListItem]
    total: int
    page: int
    page_size: int
    has_next: bool = Field(default=False)
    has_prev: bool = Field(default=False)
