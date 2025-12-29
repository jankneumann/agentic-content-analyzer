"""Digest data models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column, DateTime, Enum as SQLEnum, Integer, String, Text

from src.models.newsletter import Base


class DigestType(str, Enum):
    """Digest type."""

    DAILY = "daily"
    WEEKLY = "weekly"


class DigestStatus(str, Enum):
    """Digest generation status."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING_REVIEW = "pending_review"  # NEW: Awaiting human review
    APPROVED = "approved"  # NEW: Approved for delivery
    REJECTED = "rejected"  # NEW: Rejected (won't deliver)
    DELIVERED = "delivered"


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
    sources = Column(JSON, nullable=False)  # List[Dict] with newsletter references

    # Historical context
    historical_context = Column(JSON, nullable=True)  # List[Dict] from Graphiti

    # Metadata
    newsletter_count = Column(Integer, nullable=False)
    status = Column(
        SQLEnum(DigestStatus),
        nullable=False,
        default=DigestStatus.PENDING,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)

    # Generation metadata
    agent_framework = Column(String(100), nullable=False)
    model_used = Column(String(100), nullable=False)  # General model ID
    model_version = Column(String(20), nullable=True)  # Version
    token_usage = Column(Integer, nullable=True)
    processing_time_seconds = Column(Integer, nullable=True)

    # Review tracking (NEW)
    reviewed_by = Column(String(200), nullable=True)
    review_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    revision_count = Column(Integer, default=0, nullable=False)
    revision_history = Column(JSON, nullable=True)  # Conversation audit trail


class DigestSection(BaseModel):
    """A section within a digest (strategic insight, technical development, etc.)."""

    title: str = Field(..., description="Section title")
    summary: str = Field(..., description="2-3 sentence summary")
    details: list[str] = Field(default_factory=list, description="Detailed points")
    themes: list[str] = Field(default_factory=list, description="Related theme names")
    continuity: Optional[str] = Field(None, description="Historical continuity text")


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
    historical_context: Optional[list[dict]] = None
    newsletter_count: int
    agent_framework: str
    model_used: str  # General model ID
    model_version: Optional[str] = None  # Version
    token_usage: Optional[int] = None
    processing_time_seconds: Optional[float] = None

    # Review tracking (NEW)
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    revision_count: int = 0
    revision_history: Optional[dict] = None  # Conversation audit trail


class DigestRequest(BaseModel):
    """Request parameters for digest generation."""

    digest_type: DigestType
    period_start: datetime
    period_end: datetime
    max_strategic_insights: int = Field(default=5, description="Max strategic insights")
    max_technical_developments: int = Field(default=5, description="Max technical developments")
    max_emerging_trends: int = Field(default=3, description="Max emerging trends")
    include_historical_context: bool = Field(default=True, description="Include historical context")
