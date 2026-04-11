"""Theme analysis data models."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column, DateTime, Enum, Float, Index, Integer, String, Text

from src.models.base import Base


class ThemeCategory(StrEnum):
    """Theme categorization."""

    ML_AI = "ml_ai"  # LLMs, agents, RAG, fine-tuning
    DEVOPS_INFRA = "devops_infra"  # Cloud, containers, orchestration
    DATA_ENGINEERING = "data_engineering"  # Pipelines, lakes, processing
    BUSINESS_STRATEGY = "business_strategy"  # Adoption, ROI, governance
    TOOLS_PRODUCTS = "tools_products"  # New releases, updates
    RESEARCH_ACADEMIA = "research_academia"  # Papers, breakthroughs
    SECURITY = "security"  # Security, privacy, compliance
    OTHER = "other"  # Miscellaneous


class ThemeTrend(StrEnum):
    """Theme trend classification."""

    EMERGING = "emerging"  # New topic, recent mentions
    GROWING = "growing"  # Increasing frequency
    ESTABLISHED = "established"  # Consistent mentions over time
    DECLINING = "declining"  # Decreasing mentions
    ONE_OFF = "one_off"  # Single mention


class AnalysisStatus(StrEnum):
    """Theme analysis lifecycle status."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ThemeAnalysis(Base):
    """Theme analysis results database model."""

    __tablename__ = "theme_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Lifecycle status
    status = Column(
        Enum(
            AnalysisStatus,
            name="analysisstatus",
            create_type=False,
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AnalysisStatus.QUEUED,
        index=True,
    )

    # Time range for analysis
    analysis_date = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    # Analysis scope (renamed from newsletter_*)
    content_count = Column(Integer, nullable=False, default=0)
    content_ids = Column(JSON, nullable=False, default=list)  # List[int]

    # Detected themes
    themes = Column(JSON, nullable=False, default=list)  # List[ThemeData dict]

    # Summary statistics
    total_themes = Column(Integer, nullable=False, default=0)
    emerging_themes_count = Column(Integer, nullable=False, default=0)
    top_theme = Column(String(500), nullable=True)

    # Metadata
    agent_framework = Column(String(100), nullable=False, default="")
    model_used = Column(String(100), nullable=False, default="")
    model_version = Column(String(20), nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    token_usage = Column(Integer, nullable=True)

    # New persistence fields
    cross_theme_insights = Column(JSON, nullable=True)  # List[str]
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)

    __table_args__ = (Index("ix_theme_analyses_status_created", "status", "created_at"),)


class HistoricalMention(BaseModel):
    """Historical mention of a theme."""

    date: datetime = Field(..., description="Date of mention")
    newsletter_id: int = Field(..., description="Content ID (legacy field name)")
    newsletter_title: str = Field(..., description="Content title (legacy field name)")
    publication: str = Field(..., description="Publication name")
    context: str = Field(..., description="Context snippet about the theme")
    sentiment: str | None = Field(
        None, description="Sentiment/stance (positive, neutral, negative)"
    )


class ThemeEvolution(BaseModel):
    """How a theme has evolved over time."""

    theme_name: str = Field(..., description="Theme name")
    first_mention: datetime = Field(..., description="When first discussed")
    total_mentions: int = Field(..., description="Total historical mentions")
    mention_frequency: str = Field(
        ..., description="Frequency (rare, occasional, frequent, constant)"
    )

    # Evolution narrative
    evolution_summary: str = Field(..., description="How the theme has evolved (1-2 sentences)")
    previous_discussions: list[str] = Field(
        default_factory=list, description="Key points from previous discussions"
    )

    # Change tracking
    stance_change: str | None = Field(
        None, description="How stance/sentiment has changed over time"
    )

    # Historical mentions
    recent_mentions: list[HistoricalMention] = Field(
        default_factory=list, description="Recent mentions (last 3-5)"
    )


class ThemeData(BaseModel):
    """Individual theme data."""

    name: str = Field(..., description="Theme name (e.g., 'RAG Architecture')")
    description: str = Field(..., description="Brief description of the theme")
    category: ThemeCategory = Field(..., description="Theme category")

    # Frequency and recency
    mention_count: int = Field(..., description="Number of content items mentioning this theme")
    content_ids: list[int] = Field(
        default_factory=list,
        description="IDs of content items mentioning this theme",
    )
    first_seen: datetime = Field(..., description="First mention date")
    last_seen: datetime = Field(..., description="Most recent mention date")

    # Trend classification
    trend: ThemeTrend = Field(..., description="Theme trend (emerging, growing, etc.)")

    # Relevance scoring
    relevance_score: float = Field(..., description="Overall relevance (0-1)")
    strategic_relevance: float = Field(..., description="Strategic/leadership relevance (0-1)")
    tactical_relevance: float = Field(..., description="Tactical/developer relevance (0-1)")
    novelty_score: float = Field(..., description="How novel vs. established (0-1)")
    cross_functional_impact: float = Field(..., description="Cross-team impact (0-1)")

    # Related themes
    related_themes: list[str] = Field(default_factory=list, description="Names of related themes")

    # Key insights
    key_points: list[str] = Field(
        default_factory=list, description="Key points about this theme from content items"
    )

    # Historical context
    historical_context: ThemeEvolution | None = Field(
        None, description="Historical context and evolution of this theme"
    )

    # Continuity text
    continuity_text: str | None = Field(
        None, description="Human-readable continuity statement (e.g., 'Previously discussed in...')"
    )


class ThemeAnalysisRequest(BaseModel):
    """Request parameters for theme analysis."""

    start_date: datetime
    end_date: datetime
    min_newsletters: int = Field(default=1, description="Minimum content items to analyze")
    max_themes: int = Field(default=20, description="Maximum themes to return")
    relevance_threshold: float = Field(default=0.3, description="Minimum relevance score (0-1)")
    use_large_context_model: bool = Field(
        default=False, description="Use large context model (Gemini Flash) for analysis"
    )


class ThemeAnalysisResult(BaseModel):
    """Complete theme analysis results."""

    id: int | None = None
    analysis_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    start_date: datetime
    end_date: datetime

    # Content items analyzed (renamed from newsletter_*)
    content_count: int = 0
    content_ids: list[int] = Field(default_factory=list)

    # Themes
    themes: list[ThemeData] = Field(default_factory=list)
    total_themes: int = 0
    emerging_themes_count: int = 0

    # Top theme
    top_theme: str | None = None

    # Performance metrics
    processing_time_seconds: float = 0.0
    token_usage: int | None = None
    model_used: str = ""  # General model ID
    model_version: str | None = None  # Version
    agent_framework: str = ""

    # Insights
    cross_theme_insights: list[str] = Field(
        default_factory=list, description="Insights about connections between themes"
    )
