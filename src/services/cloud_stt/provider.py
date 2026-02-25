"""Abstract base class for cloud STT providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from src.services.cloud_stt.models import TranscriptResult


class CloudSTTProvider(ABC):
    """Abstract base class for cloud speech-to-text providers.

    Each provider implements a streaming interface:
    1. start_stream() — initialize the provider connection
    2. send_audio() — send audio chunks for transcription
    3. get_results() — async iterate over transcript results
    4. stop_stream() — clean up the provider connection

    Providers that support built-in cleanup (e.g., Gemini with a cleanup prompt)
    return TranscriptResult with cleaned=True on final results.
    """

    @abstractmethod
    async def start_stream(self, language: str = "auto") -> None:
        """Initialize the streaming transcription session.

        Args:
            language: BCP-47 language tag or "auto" for auto-detection
        """

    @abstractmethod
    async def send_audio(self, chunk: bytes) -> None:
        """Send an audio chunk for transcription.

        Audio must be PCM 16-bit mono at 16kHz sample rate.

        Args:
            chunk: Raw PCM audio data
        """

    @abstractmethod
    def get_results(self) -> AsyncIterator[TranscriptResult]:
        """Async iterate over transcript results.

        Yields:
            TranscriptResult with interim, final, or error types
        """

    @abstractmethod
    async def stop_stream(self) -> None:
        """Stop the streaming session and clean up resources."""
