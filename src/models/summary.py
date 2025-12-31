"""Summary data models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from src.models.newsletter import Base


class NewsletterSummary(Base):
    """Newsletter summary database model."""

    __tablename__ = "newsletter_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    newsletter_id = Column(Integer, ForeignKey("newsletters.id"), nullable=False, unique=True)

    # Summary content
    executive_summary = Column(Text, nullable=False)
    key_themes = Column(JSON, nullable=False)  # List[str]
    strategic_insights = Column(JSON, nullable=False)  # List[str]
    technical_details = Column(JSON, nullable=False)  # List[str]
    actionable_items = Column(JSON, nullable=False)  # List[str]
    notable_quotes = Column(JSON, nullable=False)  # List[str]
    relevant_links = Column(JSON, nullable=False, default=list)  # List[Dict[str, str]] - {"title": "...", "url": "..."}

    # Relevance scoring
    relevance_scores = Column(JSON, nullable=False)  # Dict[str, float]

    # Metadata
    agent_framework = Column(String(100), nullable=False)  # claude, openai, google, microsoft
    model_used = Column(String(100), nullable=False)  # General model ID (e.g., "claude-sonnet-4-5")
    model_version = Column(String(20), nullable=True)  # Version (e.g., "20250929")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    token_usage = Column(Integer, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)

    # Relationships
    newsletter = relationship("Newsletter", backref="summary")


class SummaryData(BaseModel):
    """Pydantic model for summary data transfer."""

    newsletter_id: int
    executive_summary: str
    key_themes: list[str] = Field(default_factory=list)
    strategic_insights: list[str] = Field(default_factory=list)
    technical_details: list[str] = Field(default_factory=list)
    actionable_items: list[str] = Field(default_factory=list)
    notable_quotes: list[str] = Field(default_factory=list)
    relevant_links: list[dict[str, str]] = Field(default_factory=list)  # [{"title": "...", "url": "..."}]
    relevance_scores: dict[str, float] = Field(default_factory=dict)
    agent_framework: str
    model_used: str  # General model ID (e.g., "claude-sonnet-4-5")
    model_version: Optional[str] = None  # Version (e.g., "20250929")
    token_usage: Optional[int] = None
    processing_time_seconds: Optional[float] = None
