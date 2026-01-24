"""AudioDigest model for tracking audio digest generation.

This module provides models for tracking text-to-speech generation
of digest content, supporting multiple TTS providers (OpenAI, ElevenLabs, etc.)
with configurable voice and speed options.
"""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.models.base import Base


class AudioDigestStatus(str, Enum):
    """Status of audio digest generation."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AudioDigest(Base):
    """Audio digest database model.

    Tracks text-to-speech generation of digest content.
    Each digest can have multiple audio versions with different
    voice/speed configurations.
    """

    __tablename__ = "audio_digests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    digest_id = Column(Integer, ForeignKey("digests.id"), nullable=False, index=True)

    # Generation config
    voice = Column(String(50), nullable=False)  # e.g., "nova", "alloy"
    speed = Column(Float, default=1.0)
    provider = Column(String(50), default="openai")  # TTS provider

    # Status tracking
    status = Column(
        SQLEnum(AudioDigestStatus, values_callable=lambda x: [e.value for e in x]),
        default=AudioDigestStatus.PENDING,
        nullable=False,
        index=True,
    )
    error_message = Column(Text, nullable=True)

    # Output
    audio_url = Column(String(500), nullable=True)  # Storage path
    duration_seconds = Column(Float, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)

    # Analytics
    text_char_count = Column(Integer, nullable=True)
    chunk_count = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    digest = relationship("Digest", back_populates="audio_digests")


# --- Pydantic Schemas ---


class AudioDigestCreate(BaseModel):
    """Schema for creating a new audio digest."""

    voice: str = Field(default="nova", description="Voice to use for TTS")
    speed: float = Field(default=1.0, ge=0.25, le=4.0, description="Playback speed")
    provider: str = Field(default="openai", description="TTS provider")


class AudioDigestResponse(BaseModel):
    """Schema for audio digest API responses."""

    id: int
    digest_id: int
    voice: str
    speed: float
    provider: str
    status: AudioDigestStatus
    error_message: str | None = None
    audio_url: str | None = None
    duration_seconds: float | None = None
    file_size_bytes: int | None = None
    text_char_count: int | None = None
    chunk_count: int | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AudioDigestListItem(BaseModel):
    """Lightweight schema for listing audio digests."""

    id: int
    digest_id: int
    voice: str
    provider: str
    status: AudioDigestStatus
    duration_seconds: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
