"""Summary data models."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from src.models.base import Base


class Summary(Base):
    """Content summary database model.

    Summaries are linked to Content records via content_id.
    """

    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Content FK - links summary to source content
    content_id = Column(
        Integer, ForeignKey("contents.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Summary content
    executive_summary = Column(Text, nullable=False)
    key_themes = Column(JSON, nullable=False)  # List[str]
    strategic_insights = Column(JSON, nullable=False)  # List[str]
    technical_details = Column(JSON, nullable=False)  # List[str]
    actionable_items = Column(JSON, nullable=False)  # List[str]
    notable_quotes = Column(JSON, nullable=False)  # List[str]
    relevant_links = Column(
        JSON, nullable=False, default=list
    )  # List[Dict[str, str]] - {"title": "...", "url": "..."}

    # Relevance scoring
    relevance_scores = Column(JSON, nullable=False)  # Dict[str, float]

    # Unified content model fields (Phase 4)
    markdown_content = Column(Text, nullable=True)  # Full markdown representation
    theme_tags = Column(JSON, nullable=True)  # List[str] - Extracted theme tags

    # Metadata
    agent_framework = Column(String(100), nullable=False)  # claude, openai, google, microsoft
    model_used = Column(String(100), nullable=False)  # General model ID (e.g., "claude-sonnet-4-5")
    model_version = Column(String(20), nullable=True)  # Version (e.g., "20250929")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    token_usage = Column(Integer, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)

    # Relationships
    content = relationship("Content", back_populates="summaries")


# Backwards compatibility alias (deprecated)
NewsletterSummary = Summary


class SummaryData(BaseModel):
    """Pydantic model for summary data transfer."""

    content_id: int | None = None  # FK to contents table
    executive_summary: str
    key_themes: list[str] = Field(default_factory=list)
    strategic_insights: list[str] = Field(default_factory=list)
    technical_details: list[str] = Field(default_factory=list)
    actionable_items: list[str] = Field(default_factory=list)
    notable_quotes: list[str] = Field(default_factory=list)
    relevant_links: list[dict[str, str]] = Field(
        default_factory=list
    )  # [{"title": "...", "url": "..."}]
    relevance_scores: dict[str, float] = Field(default_factory=dict)

    # Unified content model fields
    markdown_content: str | None = None
    theme_tags: list[str] | None = None

    agent_framework: str
    model_used: str  # General model ID (e.g., "claude-sonnet-4-5")
    model_version: str | None = None  # Version (e.g., "20250929")
    token_usage: int | None = None
    processing_time_seconds: float | None = None
