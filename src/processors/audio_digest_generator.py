"""Audio digest generator for direct digest-to-audio conversion.

This module provides simple, single-voice narration of digest content,
bypassing the full podcast script generation workflow.
"""

import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from src.config import settings
from src.delivery.audio_utils import concatenate_mp3_files
from src.delivery.text_chunker import TextChunker
from src.delivery.tts_service import TTSService
from src.models.audio_digest import AudioDigest, AudioDigestStatus
from src.models.digest import Digest
from src.models.podcast import VoiceProvider
from src.processors.digest_text_preparer import DigestTextPreparer
from src.services.file_storage import get_storage
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Character threshold for single-chunk synthesis (with safety margin)
SINGLE_CHUNK_THRESHOLD = 3800


class AudioDigestGenerator:
    """Generate audio narration from digest content.

    Unlike the podcast workflow (which requires script generation and review),
    this provides direct digest-to-audio conversion with single-voice narration.

    Example:
        >>> generator = AudioDigestGenerator(provider="openai", voice="nova")
        >>> audio_digest = await generator.generate(digest_id=123)
        >>> print(f"Audio URL: {audio_digest.audio_url}")
    """

    def __init__(
        self,
        provider: str = "openai",
        voice: str | None = None,
        speed: float = 1.0,
    ):
        """Initialize audio digest generator.

        Args:
            provider: TTS provider name ("openai", "elevenlabs")
            voice: Voice ID or preset name (uses settings default if None)
            speed: Speech speed (0.25 to 4.0)
        """
        self.provider = provider
        self.voice = voice or settings.get_effective_voice()
        self.speed = speed

        # Map provider string to VoiceProvider enum
        provider_map = {
            "openai": VoiceProvider.OPENAI_TTS,
            "elevenlabs": VoiceProvider.ELEVENLABS,
        }
        voice_provider = provider_map.get(provider, VoiceProvider.OPENAI_TTS)

        # Initialize TTS service
        self.tts = TTSService(provider=voice_provider)

        # Check SSML support for text preparation
        self.use_ssml = self.tts._provider.supports_ssml()
        self.text_preparer = DigestTextPreparer(use_ssml=self.use_ssml)

        logger.info(
            f"Initialized AudioDigestGenerator with {provider}, "
            f"voice={self.voice}, speed={speed}, ssml={self.use_ssml}"
        )

    async def generate(
        self,
        digest_id: int,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> AudioDigest:
        """Generate audio digest from a digest.

        Args:
            digest_id: ID of the digest to convert to audio
            progress_callback: Optional callback(current, total, message)

        Returns:
            AudioDigest record with audio information

        Raises:
            ValueError: If digest not found
            RuntimeError: If generation fails
        """
        logger.info(f"Generating audio digest for digest {digest_id}")

        # Load digest and create AudioDigest record
        with get_db() as db:
            digest = db.query(Digest).filter(Digest.id == digest_id).first()
            if not digest:
                raise ValueError(f"Digest {digest_id} not found")

            # Create AudioDigest record with PROCESSING status
            audio_digest = AudioDigest(
                digest_id=digest_id,
                voice=self.voice,
                speed=self.speed,
                provider=self.provider,
                status=AudioDigestStatus.PROCESSING,
            )
            db.add(audio_digest)
            db.commit()
            db.refresh(audio_digest)
            audio_digest_id = audio_digest.id

            # Prepare text from digest
            prepared_text = self.text_preparer.prepare_digest(digest)
            text_char_count = len(prepared_text)

        try:
            if progress_callback:
                progress_callback(0, 100, "Preparing text...")

            # Resolve voice ID from preset or direct voice name
            voice_id = settings.get_audio_digest_voice_id(self.voice)

            if progress_callback:
                progress_callback(10, 100, "Synthesizing audio...")

            # Choose synthesis method based on text length
            if text_char_count <= SINGLE_CHUNK_THRESHOLD:
                # Single chunk - direct synthesis
                audio_bytes, chunk_count = await self._synthesize_short(
                    prepared_text, voice_id, progress_callback
                )
            else:
                # Long text - chunked synthesis
                audio_bytes, chunk_count = await self._synthesize_long(
                    prepared_text, voice_id, progress_callback
                )

            if progress_callback:
                progress_callback(90, 100, "Uploading audio...")

            # Upload to storage
            storage = get_storage(bucket="audio-digests")
            filename = f"audio_digest_{audio_digest_id}.mp3"
            storage_path = await storage.save(
                data=audio_bytes,
                filename=filename,
                content_type="audio/mpeg",
            )

            # Calculate duration estimate
            estimated_duration = self.text_preparer.estimate_duration(prepared_text)

            # Update record with success
            with get_db() as db:
                audio_digest = (
                    db.query(AudioDigest).filter(AudioDigest.id == audio_digest_id).first()
                )
                if audio_digest:
                    audio_digest.audio_url = storage_path
                    audio_digest.duration_seconds = estimated_duration
                    audio_digest.file_size_bytes = len(audio_bytes)
                    audio_digest.text_char_count = text_char_count
                    audio_digest.chunk_count = chunk_count
                    audio_digest.status = AudioDigestStatus.COMPLETED
                    audio_digest.completed_at = datetime.now(UTC)
                    db.commit()
                    db.refresh(audio_digest)

            if progress_callback:
                progress_callback(100, 100, "Complete!")

            logger.info(
                f"Audio digest {audio_digest_id} generated successfully: "
                f"{len(audio_bytes) / 1024:.1f} KB, ~{estimated_duration:.0f}s, "
                f"{chunk_count} chunk(s)"
            )

            return audio_digest

        except Exception as e:
            logger.error(f"Audio digest generation failed: {e}")
            # Update record with failure status
            with get_db() as db:
                audio_digest = (
                    db.query(AudioDigest).filter(AudioDigest.id == audio_digest_id).first()
                )
                if audio_digest:
                    audio_digest.status = AudioDigestStatus.FAILED
                    audio_digest.error_message = "An internal error occurred during generation."
                    db.commit()
            raise RuntimeError(f"Audio digest generation failed: {e}") from e

    async def _synthesize_short(
        self,
        text: str,
        voice_id: str,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> tuple[bytes, int]:
        """Synthesize short text in a single API call.

        Args:
            text: Text to synthesize (must be under chunk threshold)
            voice_id: Provider-specific voice ID
            progress_callback: Optional progress callback

        Returns:
            Tuple of (audio_bytes, chunk_count=1)
        """
        if progress_callback:
            progress_callback(50, 100, "Synthesizing single chunk...")

        audio_bytes = await self.tts._provider.synthesize(
            text=text,
            voice_id=voice_id,
            speed=self.speed,
        )

        return audio_bytes, 1

    async def _synthesize_long(
        self,
        text: str,
        voice_id: str,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> tuple[bytes, int]:
        """Synthesize long text with chunking and concatenation.

        Args:
            text: Text to synthesize
            voice_id: Provider-specific voice ID
            progress_callback: Optional progress callback

        Returns:
            Tuple of (concatenated_audio_bytes, chunk_count)
        """
        chunker = TextChunker(provider=self.provider)
        chunks = chunker.chunk(text)

        logger.info(f"Synthesizing long text: {len(text)} chars, {len(chunks)} chunks")

        audio_segments: list[bytes] = []
        for i, chunk in enumerate(chunks):
            if progress_callback:
                # Map chunk progress to 10-90% range
                pct = 10 + int(80 * (i + 1) / len(chunks))
                progress_callback(pct, 100, f"Synthesizing chunk {i + 1}/{len(chunks)}")

            audio = await self.tts._provider.synthesize(
                text=chunk.text,
                voice_id=voice_id,
                speed=self.speed,
            )
            audio_segments.append(audio)

        # Single chunk - no concatenation needed
        if len(audio_segments) == 1:
            return audio_segments[0], 1

        # Multiple chunks - concatenate using ffmpeg
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            concatenate_mp3_files(audio_segments, tmp_path)
            result = tmp_path.read_bytes()
            return result, len(chunks)
        finally:
            tmp_path.unlink(missing_ok=True)

    async def get_audio_digest(self, audio_digest_id: int) -> AudioDigest | None:
        """Retrieve an existing audio digest by ID.

        Args:
            audio_digest_id: ID of the audio digest to retrieve

        Returns:
            AudioDigest record or None if not found
        """
        with get_db() as db:
            return db.query(AudioDigest).filter(AudioDigest.id == audio_digest_id).first()

    async def list_audio_digests(
        self,
        digest_id: int | None = None,
        status: AudioDigestStatus | None = None,
        limit: int = 50,
    ) -> list[AudioDigest]:
        """List audio digests with optional filtering.

        Args:
            digest_id: Filter by digest ID
            status: Filter by status
            limit: Maximum number of results

        Returns:
            List of AudioDigest records
        """
        with get_db() as db:
            query = db.query(AudioDigest)

            if digest_id is not None:
                query = query.filter(AudioDigest.digest_id == digest_id)

            if status is not None:
                query = query.filter(AudioDigest.status == status)

            query = query.order_by(AudioDigest.created_at.desc())
            query = query.limit(limit)

            return list(query.all())
