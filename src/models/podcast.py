"""Podcast data models for digest-to-audio conversion.

This module provides models for:
- Podcast script generation and caching
- Script review workflow with section-based feedback
- Audio generation with configurable voice personas
- TTS provider abstraction
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.models.newsletter import Base


# --- Enums ---


class PodcastLength(str, Enum):
    """Podcast duration options."""

    BRIEF = "brief"  # 5 minutes (~750-1000 words)
    STANDARD = "standard"  # 15 minutes (~2250-3000 words)
    EXTENDED = "extended"  # 30 minutes (~4500-6000 words)


class PodcastStatus(str, Enum):
    """Status of podcast script/audio generation."""

    PENDING = "pending"
    SCRIPT_GENERATING = "script_generating"
    SCRIPT_PENDING_REVIEW = "script_pending_review"  # Script ready for human review
    SCRIPT_REVISION_REQUESTED = "script_revision_requested"  # Reviewer requested changes
    SCRIPT_APPROVED = "script_approved"  # Script approved, ready for audio
    AUDIO_GENERATING = "audio_generating"
    COMPLETED = "completed"
    FAILED = "failed"


class VoiceProvider(str, Enum):
    """Text-to-speech provider options."""

    ELEVENLABS = "elevenlabs"
    GOOGLE_TTS = "google_tts"
    AWS_POLLY = "aws_polly"
    OPENAI_TTS = "openai_tts"


class VoicePersona(str, Enum):
    """Voice persona options - each persona available in male/female variants.

    Alex Chen: VP of Engineering - Strategic perspective
    Sam Rodriguez: Distinguished Engineer - Technical deep-dives
    """

    ALEX_MALE = "alex_male"  # VP Engineering - Male voice
    ALEX_FEMALE = "alex_female"  # VP Engineering - Female voice
    SAM_MALE = "sam_male"  # Distinguished Engineer - Male voice
    SAM_FEMALE = "sam_female"  # Distinguished Engineer - Female voice


class ScriptReviewAction(str, Enum):
    """Actions available during script review."""

    APPROVE = "approve"
    REQUEST_REVISION = "request_revision"
    REJECT = "reject"


# --- Pydantic Models ---


class DialogueTurn(BaseModel):
    """Single turn in the podcast dialogue."""

    speaker: str = Field(..., description="Speaker identifier: 'alex' or 'sam'")
    text: str = Field(..., description="The spoken content")
    emphasis: Optional[str] = Field(
        None, description="Emotional tone: 'excited', 'thoughtful', 'concerned', 'amused'"
    )
    pause_after: float = Field(default=0.5, description="Seconds of pause after this turn")


class PodcastSection(BaseModel):
    """Section of the podcast with dialogue turns."""

    section_type: str = Field(
        ..., description="Section type: 'intro', 'strategic', 'technical', 'trend', 'outro'"
    )
    title: str = Field(..., description="Section title")
    dialogue: list[DialogueTurn] = Field(default_factory=list, description="Dialogue turns")
    sources_cited: list[int] = Field(
        default_factory=list, description="Newsletter IDs referenced in this section"
    )


class PodcastScript(BaseModel):
    """Complete podcast script ready for TTS."""

    title: str = Field(..., description="Podcast episode title")
    length: PodcastLength = Field(..., description="Target podcast length")
    estimated_duration_seconds: int = Field(..., description="Estimated duration in seconds")
    word_count: int = Field(..., description="Total word count of script")
    sections: list[PodcastSection] = Field(default_factory=list, description="Script sections")
    intro: Optional[PodcastSection] = Field(None, description="Intro section (convenience)")
    outro: Optional[PodcastSection] = Field(None, description="Outro section (convenience)")
    sources_summary: list[dict] = Field(
        default_factory=list,
        description="Summary of sources: [{id, title, publication, url}]",
    )


class PodcastRequest(BaseModel):
    """Request to generate a podcast script from a digest."""

    digest_id: int = Field(..., description="ID of the digest to convert")
    length: PodcastLength = Field(
        default=PodcastLength.STANDARD, description="Target podcast length"
    )
    enable_web_search: bool = Field(
        default=True, description="Allow model to use web search tool for grounding"
    )
    voice_provider: VoiceProvider = Field(
        default=VoiceProvider.OPENAI_TTS, description="TTS provider for audio generation"
    )
    alex_voice: VoicePersona = Field(
        default=VoicePersona.ALEX_MALE, description="Voice for Alex persona"
    )
    sam_voice: VoicePersona = Field(
        default=VoicePersona.SAM_FEMALE, description="Voice for Sam persona"
    )
    custom_focus_topics: list[str] = Field(
        default_factory=list, description="Optional topics to emphasize"
    )


class ScriptRevisionRequest(BaseModel):
    """Request to revise a specific section of a script."""

    script_id: int = Field(..., description="ID of the script to revise")
    section_index: int = Field(..., description="Index of section to revise (0-based)")
    feedback: str = Field(..., description="Reviewer feedback for this section")
    replacement_dialogue: Optional[list[DialogueTurn]] = Field(
        None, description="If provided, replace section dialogue entirely"
    )


class ScriptReviewRequest(BaseModel):
    """Request to review a complete script."""

    script_id: int = Field(..., description="ID of the script to review")
    action: ScriptReviewAction = Field(..., description="Review action")
    reviewer: str = Field(..., description="Reviewer identifier")
    section_feedback: dict[int, str] = Field(
        default_factory=dict,
        description="Section-specific feedback (key = section index, value = feedback)",
    )
    general_notes: Optional[str] = Field(None, description="General review notes")


class PodcastGenerationMetadata(BaseModel):
    """Metadata about podcast script generation for tracking and debugging."""

    newsletter_ids_fetched: list[int] = Field(
        default_factory=list, description="Newsletter IDs fetched via tool"
    )
    web_searches: list[str] = Field(
        default_factory=list, description="Web search queries executed"
    )
    tool_call_count: int = Field(default=0, description="Total tool invocations")
    total_tokens_used: int = Field(default=0, description="Total tokens consumed")


class AudioGenerationRequest(BaseModel):
    """Request to generate audio from an approved script."""

    script_id: int = Field(..., description="ID of the approved script")
    voice_provider: VoiceProvider = Field(
        default=VoiceProvider.OPENAI_TTS, description="TTS provider"
    )
    alex_voice: VoicePersona = Field(
        default=VoicePersona.ALEX_MALE, description="Voice for Alex persona"
    )
    sam_voice: VoicePersona = Field(
        default=VoicePersona.SAM_FEMALE, description="Voice for Sam persona"
    )


# --- Database Models ---


class PodcastScriptRecord(Base):
    """Cached podcast script - can be reused for multiple audio generations.

    Scripts go through a review workflow before audio generation:
    1. SCRIPT_GENERATING - LLM generating script
    2. SCRIPT_PENDING_REVIEW - Ready for human review
    3. SCRIPT_REVISION_REQUESTED - Reviewer requested changes (loops back to step 2)
    4. SCRIPT_APPROVED - Ready for audio generation
    """

    __tablename__ = "podcast_scripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    digest_id = Column(Integer, ForeignKey("digests.id"), nullable=False, index=True)
    length = Column(SQLEnum(PodcastLength), nullable=False)

    # Script content
    title = Column(String(500), nullable=True)
    script_json = Column(JSON, nullable=True)  # PodcastScript Pydantic model serialized
    word_count = Column(Integer, nullable=True)
    estimated_duration_seconds = Column(Integer, nullable=True)

    # Review workflow
    status = Column(
        SQLEnum(PodcastStatus),
        nullable=False,
        default=PodcastStatus.PENDING,
        index=True,
    )
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    revision_count = Column(Integer, default=0, nullable=False)
    revision_history = Column(
        JSON, nullable=True
    )  # List of {section_index, section_type, feedback, timestamp}

    # Context & Tool Usage Tracking
    newsletter_ids_available = Column(JSON, nullable=True)  # All newsletter IDs in digest period
    newsletter_ids_fetched = Column(
        JSON, nullable=True
    )  # IDs fetched via get_newsletter_content tool
    theme_ids = Column(JSON, nullable=True)  # Themes incorporated
    web_search_queries = Column(JSON, nullable=True)  # Web searches performed via tool
    tool_call_count = Column(Integer, nullable=True)  # Total tool invocations

    # Generation metadata
    model_used = Column(String(100), nullable=True)
    model_version = Column(String(50), nullable=True)
    token_usage = Column(JSON, nullable=True)
    processing_time_seconds = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)

    # Relationships
    digest = relationship("Digest", backref="podcast_scripts")
    podcasts = relationship("Podcast", back_populates="script")


class Podcast(Base):
    """Podcast audio generated from an approved script.

    Multiple audio versions can be generated from the same script
    with different voice configurations.
    """

    __tablename__ = "podcasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    script_id = Column(Integer, ForeignKey("podcast_scripts.id"), nullable=False, index=True)

    # Audio output
    audio_url = Column(String(1000), nullable=True)  # Local path (S3/SharePoint future)
    audio_format = Column(String(20), default="mp3", nullable=False)
    duration_seconds = Column(Integer, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)

    # Voice configuration
    voice_provider = Column(SQLEnum(VoiceProvider), nullable=True)
    alex_voice = Column(SQLEnum(VoicePersona), nullable=True)
    sam_voice = Column(SQLEnum(VoicePersona), nullable=True)
    voice_config = Column(JSON, nullable=True)  # Provider-specific voice IDs used

    # Status
    status = Column(String(50), default="generating", nullable=False)  # generating, completed, failed
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    script = relationship("PodcastScriptRecord", back_populates="podcasts")
