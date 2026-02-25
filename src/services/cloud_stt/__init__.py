"""Cloud Speech-to-Text service abstraction.

Provides real-time audio transcription via multiple cloud providers:
- Gemini (default) — native audio input with built-in transcript cleanup
- OpenAI Whisper — raw transcription
- Deepgram — real-time streaming transcription

Provider selection is implicit from the CLOUD_STT pipeline step model family.
"""

from src.services.cloud_stt.models import TranscriptResult, TranscriptResultType
from src.services.cloud_stt.provider import CloudSTTProvider
from src.services.cloud_stt.service import CloudSTTService

__all__ = [
    "CloudSTTProvider",
    "CloudSTTService",
    "TranscriptResult",
    "TranscriptResultType",
]
