"""Newsletter data models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column, DateTime, Enum as SQLEnum, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class NewsletterSource(str, Enum):
    """Newsletter source types."""

    GMAIL = "gmail"
    RSS = "rss"
    SUBSTACK_RSS = "substack_rss"  # Deprecated: Use RSS instead
    OTHER = "other"


class ProcessingStatus(str, Enum):
    """Processing status for newsletters."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Newsletter(Base):
    """Newsletter database model."""

    __tablename__ = "newsletters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(SQLEnum(NewsletterSource), nullable=False, index=True)
    source_id = Column(String(500), nullable=False, unique=True)  # Email ID or RSS guid

    # Metadata
    title = Column(String(1000), nullable=False)
    sender = Column(String(500))
    publication = Column(String(500), index=True)
    published_date = Column(DateTime, nullable=False, index=True)
    url = Column(String(2000))

    # Content
    raw_html = Column(Text)
    raw_text = Column(Text)
    extracted_links = Column(JSON)  # List of URLs found in content

    # Deduplication
    content_hash = Column(String(64), nullable=True, index=True)  # SHA-256 of normalized content
    canonical_newsletter_id = Column(
        Integer, nullable=True
    )  # Links to canonical version if duplicate

    # Processing
    status = Column(
        SQLEnum(ProcessingStatus),
        nullable=False,
        default=ProcessingStatus.PENDING,
        index=True,
    )
    ingested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class NewsletterData(BaseModel):
    """Pydantic model for newsletter data transfer."""

    source: NewsletterSource
    source_id: str
    title: str
    sender: str | None = None
    publication: str | None = None
    published_date: datetime
    url: str | None = None
    raw_html: str | None = None
    raw_text: str | None = None
    extracted_links: list[str] = Field(default_factory=list)
    content_hash: str | None = None
    status: ProcessingStatus = ProcessingStatus.PENDING
