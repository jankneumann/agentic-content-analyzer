"""Text-to-Speech service abstraction for podcast audio generation.

Provides a unified interface for multiple TTS providers:
- OpenAI TTS (primary - good cost/quality balance)
- ElevenLabs (premium - best voice quality)
- Google Cloud TTS (optional)
- AWS Polly (optional)

Each provider requires specific API keys and configuration.
"""

import tempfile
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

from src.config import settings
from src.models.podcast import VoicePersona, VoiceProvider
from src.utils.logging import get_logger

logger = get_logger(__name__)


# Voice persona mappings per provider
# Maps VoicePersona to provider-specific voice IDs
VOICE_PERSONA_CONFIG = {
    VoiceProvider.OPENAI_TTS: {
        VoicePersona.ALEX_MALE: "onyx",  # Deep, confident
        VoicePersona.ALEX_FEMALE: "nova",  # Warm, professional
        VoicePersona.SAM_MALE: "fable",  # Expressive, warm
        VoicePersona.SAM_FEMALE: "shimmer",  # Clear, bright
    },
    VoiceProvider.ELEVENLABS: {
        # These should be configured with actual ElevenLabs voice IDs
        # from the user's account. Placeholder defaults provided.
        VoicePersona.ALEX_MALE: settings.elevenlabs_voice_alex_male
        or "nPczCjzI2devNBz1zQrb",  # Brian - Deep, Resonant and Comforting
        VoicePersona.ALEX_FEMALE: settings.elevenlabs_voice_alex_female
        or "XrExE9yKIg1WjnnlVkGX",  # Matilda - Knowledgable, Professional
        VoicePersona.SAM_MALE: settings.elevenlabs_voice_sam_male
        or "CwhRBWXzGAHq8TQ4Fs17",  # Roger - Resonant,Laid-back, Casual
        VoicePersona.SAM_FEMALE: settings.elevenlabs_voice_sam_female
        or "SAz9YHcvj6GT2YYXdXww",  # River - Relaxed, Neutral, Informative
    },
    VoiceProvider.GOOGLE_TTS: {
        VoicePersona.ALEX_MALE: "en-US-Studio-M",
        VoicePersona.ALEX_FEMALE: "en-US-Studio-O",
        VoicePersona.SAM_MALE: "en-US-Studio-Q",
        VoicePersona.SAM_FEMALE: "en-US-Studio-N",
    },
    VoiceProvider.AWS_POLLY: {
        VoicePersona.ALEX_MALE: "Matthew",
        VoicePersona.ALEX_FEMALE: "Joanna",
        VoicePersona.SAM_MALE: "Stephen",
        VoicePersona.SAM_FEMALE: "Salli",
    },
}


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        **kwargs: Any,
    ) -> bytes:
        """Synthesize text to audio bytes.

        Args:
            text: Text to synthesize
            voice_id: Provider-specific voice identifier
            **kwargs: Provider-specific options

        Returns:
            Audio data as bytes (typically MP3)
        """
        pass

    @abstractmethod
    def synthesize_stream(
        self,
        text: str,
        voice_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Stream audio synthesis for long content.

        Args:
            text: Text to synthesize
            voice_id: Provider-specific voice identifier
            **kwargs: Provider-specific options

        Yields:
            Audio data chunks as bytes
        """
        ...

    @abstractmethod
    def get_voice_id(self, persona: VoicePersona) -> str:
        """Get provider-specific voice ID for a persona.

        Args:
            persona: Voice persona enum

        Returns:
            Provider-specific voice ID string
        """
        pass

    def supports_ssml(self) -> bool:
        """Check if provider supports SSML markup.

        Returns:
            True if SSML is supported, False otherwise
        """
        return False  # Default: no SSML support


class OpenAITTSProvider(TTSProvider):
    """OpenAI TTS implementation.

    Uses OpenAI's tts-1 and tts-1-hd models.
    Good balance of cost and quality.
    """

    def __init__(self, api_key: str | None = None):
        """Initialize OpenAI TTS provider.

        Args:
            api_key: OpenAI API key (defaults to settings.openai_api_key)
        """
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            logger.warning("OpenAI API key not configured for TTS")

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        model: str = "tts-1",
        speed: float = 1.0,
        response_format: str = "mp3",
        **kwargs: Any,
    ) -> bytes:
        """Synthesize text using OpenAI TTS.

        Args:
            text: Text to synthesize
            voice_id: OpenAI voice name (alloy, echo, fable, onyx, nova, shimmer)
            model: TTS model (tts-1 or tts-1-hd)
            speed: Speech speed (0.25 to 4.0)
            response_format: Audio format (mp3, opus, aac, flac)

        Returns:
            Audio data as bytes
        """
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)

        logger.debug(f"OpenAI TTS: synthesizing {len(text)} chars with voice {voice_id}")

        response = await client.audio.speech.create(
            model=model,
            voice=voice_id,  # type: ignore[arg-type]
            input=text,
            speed=speed,
            response_format=response_format,  # type: ignore[arg-type]
        )

        return bytes(response.content)

    async def synthesize_stream(
        self,
        text: str,
        voice_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Stream audio synthesis.

        Note: OpenAI TTS doesn't support true streaming,
        so we synthesize and yield the full result.
        """
        audio = await self.synthesize(text, voice_id, **kwargs)
        yield audio

    def get_voice_id(self, persona: VoicePersona) -> str:
        """Get OpenAI voice ID for a persona."""
        return VOICE_PERSONA_CONFIG[VoiceProvider.OPENAI_TTS][persona]


class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs TTS implementation.

    Premium voice quality with natural prosody.
    Requires ElevenLabs API subscription.
    """

    def __init__(self, api_key: str | None = None):
        """Initialize ElevenLabs TTS provider.

        Args:
            api_key: ElevenLabs API key (defaults to settings.elevenlabs_api_key)
        """
        self.api_key = api_key or settings.elevenlabs_api_key
        self.base_url = "https://api.elevenlabs.io/v1"

        if not self.api_key:
            logger.warning("ElevenLabs API key not configured for TTS")

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        model_id: str = "eleven_turbo_v2_5",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
        use_speaker_boost: bool = True,
        **kwargs: Any,
    ) -> bytes:
        """Synthesize text using ElevenLabs.

        Args:
            text: Text to synthesize
            voice_id: ElevenLabs voice ID
            model_id: Model to use (eleven_turbo_v2_5, eleven_multilingual_v2)
            stability: Voice stability (0-1)
            similarity_boost: Voice clarity/similarity (0-1)
            style: Style exaggeration (0-1)
            use_speaker_boost: Enhance speaker similarity

        Returns:
            Audio data as bytes (MP3)
        """
        import aiohttp

        if not self.api_key:
            raise RuntimeError("ElevenLabs API key not configured")

        logger.debug(f"ElevenLabs TTS: synthesizing {len(text)} chars with voice {voice_id}")

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.base_url}/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": model_id,
                    "voice_settings": {
                        "stability": stability,
                        "similarity_boost": similarity_boost,
                        "style": style,
                        "use_speaker_boost": use_speaker_boost,
                    },
                },
            ) as response,
        ):
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"ElevenLabs TTS failed ({response.status}): {error_text}")
            return bytes(await response.read())

    async def synthesize_stream(
        self,
        text: str,
        voice_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Stream audio synthesis from ElevenLabs.

        ElevenLabs supports true streaming for lower latency.
        """
        import aiohttp

        if not self.api_key:
            raise RuntimeError("ElevenLabs API key not configured")

        model_id = kwargs.get("model_id", "eleven_turbo_v2_5")

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.base_url}/text-to-speech/{voice_id}/stream",
                headers={
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": model_id,
                    "voice_settings": {
                        "stability": kwargs.get("stability", 0.5),
                        "similarity_boost": kwargs.get("similarity_boost", 0.75),
                    },
                },
            ) as response,
        ):
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(
                    f"ElevenLabs TTS stream failed ({response.status}): {error_text}"
                )

            async for chunk in response.content.iter_chunked(4096):
                yield chunk

    def get_voice_id(self, persona: VoicePersona) -> str:
        """Get ElevenLabs voice ID for a persona."""
        return VOICE_PERSONA_CONFIG[VoiceProvider.ELEVENLABS][persona]

    def supports_ssml(self) -> bool:
        """ElevenLabs supports SSML markup for pauses and prosody."""
        return True


class GoogleTTSProvider(TTSProvider):
    """Google Cloud TTS implementation.

    Uses Google Cloud Text-to-Speech API.
    Requires Google Cloud credentials.

    Note: Stub implementation - requires google-cloud-texttospeech package.
    """

    def __init__(self, credentials_path: str | None = None):
        """Initialize Google Cloud TTS provider."""
        self.credentials_path = credentials_path
        logger.info("GoogleTTSProvider initialized (implementation pending)")

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        **kwargs: Any,
    ) -> bytes:
        """Synthesize text using Google Cloud TTS.

        Note: Implementation pending - requires google-cloud-texttospeech.
        """
        raise NotImplementedError(
            "Google Cloud TTS requires google-cloud-texttospeech package. "
            "Install with: pip install google-cloud-texttospeech"
        )

    async def synthesize_stream(
        self,
        text: str,
        voice_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Stream audio synthesis from Google Cloud TTS."""
        raise NotImplementedError("Google Cloud TTS streaming not implemented")
        yield b""  # Make it a generator for type checking

    def get_voice_id(self, persona: VoicePersona) -> str:
        """Get Google Cloud voice ID for a persona."""
        return VOICE_PERSONA_CONFIG[VoiceProvider.GOOGLE_TTS][persona]


class AWSPollyTTSProvider(TTSProvider):
    """AWS Polly TTS implementation.

    Uses AWS Polly for text-to-speech.
    Requires AWS credentials.

    Note: Stub implementation - requires boto3 package.
    """

    def __init__(self, region: str = "us-east-1"):
        """Initialize AWS Polly TTS provider."""
        self.region = region
        logger.info("AWSPollyTTSProvider initialized (implementation pending)")

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        **kwargs: Any,
    ) -> bytes:
        """Synthesize text using AWS Polly.

        Note: Implementation pending - requires boto3.
        """
        raise NotImplementedError(
            "AWS Polly requires boto3 package. Install with: pip install boto3"
        )

    async def synthesize_stream(
        self,
        text: str,
        voice_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Stream audio synthesis from AWS Polly."""
        raise NotImplementedError("AWS Polly streaming not implemented")
        yield b""  # Make it a generator for type checking

    def get_voice_id(self, persona: VoicePersona) -> str:
        """Get AWS Polly voice ID for a persona."""
        return VOICE_PERSONA_CONFIG[VoiceProvider.AWS_POLLY][persona]


class TTSService:
    """High-level TTS service with provider abstraction.

    Provides a unified interface for synthesizing speech across
    multiple TTS providers with automatic voice persona mapping.
    """

    def __init__(
        self,
        provider: VoiceProvider = VoiceProvider.OPENAI_TTS,
        alex_voice: VoicePersona = VoicePersona.ALEX_MALE,
        sam_voice: VoicePersona = VoicePersona.SAM_FEMALE,
    ):
        """Initialize TTS service.

        Args:
            provider: TTS provider to use
            alex_voice: Voice persona for Alex
            sam_voice: Voice persona for Sam
        """
        self.provider_type = provider
        self.alex_voice = alex_voice
        self.sam_voice = sam_voice

        # Initialize provider
        self._provider = self._create_provider(provider)

        logger.info(
            f"Initialized TTSService with {provider.value}, "
            f"alex={alex_voice.value}, sam={sam_voice.value}"
        )

    def _create_provider(self, provider: VoiceProvider) -> TTSProvider:
        """Create TTS provider instance.

        Args:
            provider: Provider type

        Returns:
            TTSProvider instance
        """
        if provider == VoiceProvider.OPENAI_TTS:
            return OpenAITTSProvider()
        elif provider == VoiceProvider.ELEVENLABS:
            return ElevenLabsTTSProvider()
        elif provider == VoiceProvider.GOOGLE_TTS:
            return GoogleTTSProvider()
        elif provider == VoiceProvider.AWS_POLLY:
            return AWSPollyTTSProvider()
        else:
            raise ValueError(f"Unknown TTS provider: {provider}")

    def get_voice_id_for_speaker(self, speaker: str) -> str:
        """Get voice ID for a speaker.

        Args:
            speaker: Speaker name ("alex" or "sam")

        Returns:
            Provider-specific voice ID
        """
        persona = self.alex_voice if speaker.lower() == "alex" else self.sam_voice
        return self._provider.get_voice_id(persona)

    async def synthesize(
        self,
        text: str,
        speaker: str,
        **kwargs: Any,
    ) -> bytes:
        """Synthesize speech for a speaker.

        Args:
            text: Text to synthesize
            speaker: Speaker name ("alex" or "sam")
            **kwargs: Provider-specific options

        Returns:
            Audio data as bytes
        """
        voice_id = self.get_voice_id_for_speaker(speaker)
        return await self._provider.synthesize(text, voice_id, **kwargs)

    async def synthesize_stream(
        self,
        text: str,
        speaker: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Stream speech synthesis for a speaker.

        Args:
            text: Text to synthesize
            speaker: Speaker name ("alex" or "sam")
            **kwargs: Provider-specific options

        Yields:
            Audio data chunks as bytes
        """
        voice_id = self.get_voice_id_for_speaker(speaker)
        async for chunk in self._provider.synthesize_stream(text, voice_id, **kwargs):
            yield chunk

    def get_voice_config(self) -> dict[str, str]:
        """Get current voice configuration.

        Returns:
            Dict with voice configuration details
        """
        return {
            "provider": self.provider_type.value,
            "alex_persona": self.alex_voice.value,
            "sam_persona": self.sam_voice.value,
            "alex_voice_id": self.get_voice_id_for_speaker("alex"),
            "sam_voice_id": self.get_voice_id_for_speaker("sam"),
        }

    def _get_provider_name(self) -> str:
        """Get provider name for TextChunker.

        Returns:
            Provider name string compatible with TextChunker.
        """
        # Map VoiceProvider values to TextChunker provider names
        provider_map = {
            "openai_tts": "openai",
            "openai-tts": "openai",
            "elevenlabs": "elevenlabs",
            "google_tts": "google",
            "google-tts": "google",
            "aws_polly": "aws_polly",
            "aws-polly": "aws_polly",
        }
        provider_value = self.provider_type.value.lower()
        return provider_map.get(provider_value, "openai")

    async def synthesize_long(
        self,
        text: str,
        speaker: str,
        progress_callback: Callable[[int, int, str], None] | None = None,
        **kwargs: Any,
    ) -> bytes:
        """Synthesize long-form text, automatically handling chunking.

        For text that exceeds provider character limits, this method
        automatically chunks the text, synthesizes each chunk, and
        concatenates the resulting audio into a single output.

        Args:
            text: Text of any length to synthesize.
            speaker: Speaker name ("alex" or "sam").
            progress_callback: Optional callback(current, total, message)
                called after each chunk is synthesized.
            **kwargs: Provider-specific options (speed, model, etc.)

        Returns:
            Combined audio data as bytes (MP3 format).

        Example:
            >>> service = TTSService(provider=VoiceProvider.OPENAI_TTS)
            >>> def on_progress(current, total, msg):
            ...     print(f"{current}/{total}: {msg}")
            >>> audio = await service.synthesize_long(
            ...     long_text,
            ...     speaker="alex",
            ...     progress_callback=on_progress,
            ... )
        """
        from src.delivery.audio_utils import concatenate_mp3_files
        from src.delivery.text_chunker import TextChunker

        # Get provider name for chunk limits
        provider_name = self._get_provider_name()
        chunker = TextChunker(provider=provider_name)

        chunks = chunker.chunk(text)
        if not chunks:
            logger.debug("Empty text provided to synthesize_long, returning empty bytes")
            return b""

        logger.info(
            f"Synthesizing long text: {len(text)} chars, {len(chunks)} chunks, "
            f"provider={provider_name}, speaker={speaker}"
        )

        # Single chunk - no concatenation needed
        if len(chunks) == 1:
            if progress_callback:
                progress_callback(1, 1, "Synthesizing single chunk")
            return await self.synthesize(chunks[0].text, speaker, **kwargs)

        # Multiple chunks - synthesize and concatenate
        audio_segments: list[bytes] = []
        for i, chunk in enumerate(chunks):
            chunk_num = i + 1
            if progress_callback:
                progress_callback(
                    chunk_num,
                    len(chunks),
                    f"Synthesizing chunk {chunk_num}/{len(chunks)}",
                )

            logger.debug(
                f"Synthesizing chunk {chunk_num}/{len(chunks)}: "
                f"{len(chunk.text)} chars, est. {chunk.estimated_duration:.1f}s"
            )

            audio_bytes = await self.synthesize(chunk.text, speaker, **kwargs)
            audio_segments.append(audio_bytes)

        # Concatenate using ffmpeg via audio_utils
        logger.debug(f"Concatenating {len(audio_segments)} audio segments")

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
        try:
            concatenate_mp3_files(audio_segments, tmp_path)
            result = tmp_path.read_bytes()
            logger.info(
                f"Long-form synthesis complete: {len(chunks)} chunks, "
                f"{len(result) / 1024:.1f} KB output"
            )
            return result
        finally:
            tmp_path.unlink(missing_ok=True)

    async def synthesize_long_stream(
        self,
        text: str,
        speaker: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Stream long-form text synthesis chunk by chunk.

        For progressive output, this method yields audio bytes as each
        chunk is synthesized. Useful for streaming responses where you
        want to start playback before the entire text is processed.

        Note: Each yielded chunk is a complete MP3 segment. The caller
        is responsible for concatenation if a single file is needed.

        Args:
            text: Text of any length to synthesize.
            speaker: Speaker name ("alex" or "sam").
            **kwargs: Provider-specific options (speed, model, etc.)

        Yields:
            Audio data bytes for each chunk (MP3 format).

        Example:
            >>> service = TTSService(provider=VoiceProvider.OPENAI_TTS)
            >>> async for chunk_audio in service.synthesize_long_stream(
            ...     long_text,
            ...     speaker="sam",
            ... ):
            ...     # Process or send each chunk immediately
            ...     await send_audio_chunk(chunk_audio)
        """
        from src.delivery.text_chunker import TextChunker

        # Get provider name for chunk limits
        provider_name = self._get_provider_name()
        chunker = TextChunker(provider=provider_name)

        chunks = chunker.chunk(text)
        if not chunks:
            logger.debug("Empty text provided to synthesize_long_stream")
            return

        logger.info(
            f"Streaming long text synthesis: {len(text)} chars, "
            f"{len(chunks)} chunks, provider={provider_name}, speaker={speaker}"
        )

        for i, chunk in enumerate(chunks):
            logger.debug(
                f"Streaming chunk {i + 1}/{len(chunks)}: "
                f"{len(chunk.text)} chars, est. {chunk.estimated_duration:.1f}s"
            )
            audio_bytes = await self.synthesize(chunk.text, speaker, **kwargs)
            yield audio_bytes

        logger.debug(f"Stream synthesis complete: {len(chunks)} chunks")
