"""Digest data models."""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Boolean, Column, DateTime, Enum as SQLEnum, Integer, String, Text
from sqlalchemy.orm import Mapped, relationship

from src.models.base import Base
from src.models.query import ContentQuery

if TYPE_CHECKING:
    from src.models.audio_digest import AudioDigest


class DigestType(StrEnum):
    """Digest type."""

    DAILY = "daily"
    WEEKLY = "weekly"
    SUB_DIGEST = "sub_digest"  # Sub-digest for hierarchical digest creation


class DigestStatus(StrEnum):
    """Digest generation status."""

    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PENDING_REVIEW = "PENDING_REVIEW"  # NEW: Awaiting human review
    APPROVED = "APPROVED"  # NEW: Approved for delivery
    REJECTED = "REJECTED"  # NEW: Rejected (won't deliver)
    DELIVERED = "DELIVERED"


class Digest(Base):
    """Digest database model."""

    __tablename__ = "digests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    digest_type = Column(SQLEnum(DigestType), nullable=False, index=True)

    # Time period covered
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False, index=True)

    # Content
    title = Column(String(500), nullable=False)
    executive_overview = Column(Text, nullable=False)
    strategic_insights = Column(JSON, nullable=False)  # List[Dict]
    technical_developments = Column(JSON, nullable=False)  # List[Dict]
    emerging_trends = Column(JSON, nullable=False)  # List[Dict]
    actionable_recommendations = Column(JSON, nullable=False)  # Dict[str, List[str]]
    sources = Column(JSON, nullable=False)  # List[Dict] with content references

    # Historical context
    historical_context = Column(JSON, nullable=True)  # List[Dict] from Graphiti

    # Unified content model fields (Phase 4)
    markdown_content = Column(Text, nullable=True)  # Full markdown representation
    theme_tags = Column(JSON, nullable=True)  # List[str] - Extracted theme tags
    source_content_ids = Column(JSON, nullable=True)  # List[int] - Content IDs used in digest

    # Metadata
    newsletter_count = Column(Integer, nullable=False)  # Legacy name, now represents content count
    status = Column(
        SQLEnum(DigestStatus),
        nullable=False,
        default=DigestStatus.PENDING,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)

    # Sharing
    is_public = Column(Boolean, nullable=False, default=False, server_default="false")
    share_token = Column(String(36), nullable=True, unique=True, index=True)

    # Generation metadata
    agent_framework = Column(String(100), nullable=False)
    model_used = Column(String(100), nullable=False)  # General model ID
    model_version = Column(String(20), nullable=True)  # Version
    token_usage = Column(Integer, nullable=True)
    processing_time_seconds = Column(Integer, nullable=True)

    # Review tracking
    reviewed_by = Column(String(200), nullable=True)
    review_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    revision_count = Column(Integer, default=0, nullable=False)
    revision_history = Column(JSON, nullable=True)  # Conversation audit trail

    # Hierarchical digest support (NEW)
    parent_digest_id = Column(Integer, nullable=True, index=True)  # FK added in migration
    child_digest_ids = Column(JSON, nullable=True)  # List[int] of child digest IDs
    is_combined = Column(Boolean, default=False, nullable=False)
    source_digest_count = Column(Integer, nullable=True)  # Number of sub-digests combined

    # Relationships
    audio_digests: Mapped[list["AudioDigest"]] = relationship(
        "AudioDigest",
        back_populates="digest",
        foreign_keys="AudioDigest.digest_id",
    )


class DigestSection(BaseModel):
    """A section within a digest (strategic insight, technical development, etc.)."""

    title: str = Field(..., description="Section title")
    summary: str = Field(..., description="2-3 sentence summary")
    details: list[str] = Field(default_factory=list, description="Detailed points")
    themes: list[str] = Field(default_factory=list, description="Related theme names")
    continuity: str | None = Field(None, description="Historical continuity text")
    followup_prompts: list[str] = Field(
        default_factory=list, description="LLM prompts for deeper analysis"
    )


class DigestData(BaseModel):
    """Pydantic model for digest data transfer."""

    digest_type: DigestType
    period_start: datetime
    period_end: datetime
    title: str
    executive_overview: str
    strategic_insights: list[DigestSection] = Field(default_factory=list)
    technical_developments: list[DigestSection] = Field(default_factory=list)
    emerging_trends: list[DigestSection] = Field(default_factory=list)
    actionable_recommendations: dict[str, list[str]] = Field(default_factory=dict)
    sources: list[dict] = Field(default_factory=list)
    historical_context: list[dict] | None = None

    # Unified content model fields
    markdown_content: str | None = None
    theme_tags: list[str] | None = None
    source_content_ids: list[int] | None = None

    newsletter_count: int
    agent_framework: str
    model_used: str  # General model ID
    model_version: str | None = None  # Version
    token_usage: int | None = None
    processing_time_seconds: float | None = None

    # Review tracking
    reviewed_by: str | None = None
    review_notes: str | None = None
    reviewed_at: datetime | None = None
    revision_count: int = 0
    revision_history: dict | None = None  # Conversation audit trail

    # Hierarchical digest support (NEW)
    parent_digest_id: int | None = None
    child_digest_ids: list[int] | None = None
    is_combined: bool = False
    source_digest_count: int | None = None


class DigestRequest(BaseModel):
    """Request parameters for digest generation."""

    digest_type: DigestType
    period_start: datetime
    period_end: datetime
    max_strategic_insights: int = Field(default=5, description="Max strategic insights")
    max_technical_developments: int = Field(default=5, description="Max technical developments")
    max_emerging_trends: int = Field(default=3, description="Max emerging trends")
    max_followup_prompts: int = Field(default=3, description="Max follow-up prompts per section")
    include_historical_context: bool = Field(default=True, description="Include historical context")
    content_query: "ContentQuery | None" = Field(
        default=None, description="Optional content selection override"
    )
