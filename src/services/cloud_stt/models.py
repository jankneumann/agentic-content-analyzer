"""Transcript result models for cloud STT providers."""

from enum import StrEnum

from pydantic import BaseModel, Field


class TranscriptResultType(StrEnum):
    """Type of transcript result from a cloud STT provider."""

    INTERIM = "interim"  # Partial, in-progress transcript
    FINAL = "final"  # Completed transcript segment
    ERROR = "error"  # Provider error


class TranscriptResult(BaseModel):
    """A single transcript result from a cloud STT provider.

    Attributes:
        type: Whether this is an interim, final, or error result
        text: The transcript text (or error message for error type)
        cleaned: Whether the text has been cleaned by the provider
                 (e.g., Gemini with cleanup prompt returns cleaned=True)
        confidence: Optional confidence score from the provider (0.0-1.0)
    """

    type: TranscriptResultType
    text: str
    cleaned: bool = False
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
