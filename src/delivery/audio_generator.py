"""Audio generator for podcast production.

Combines TTS-synthesized dialogue turns into a complete podcast audio file.
Handles:
- Per-turn audio synthesis with speaker-specific voices
- Pause/silence insertion between turns
- Audio concatenation and export
- Progress tracking for long podcasts
"""

import io
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from src.config import settings
from src.delivery.tts_service import TTSService
from src.models.podcast import (
    PodcastScript,
    PodcastSection,
    VoicePersona,
    VoiceProvider,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AudioMetadata:
    """Metadata about generated audio."""

    duration_seconds: int
    file_size_bytes: int
    format: str
    sample_rate: int
    word_count: int
    turn_count: int
    generation_time_seconds: float


class PodcastAudioGenerator:
    """Generate podcast audio from scripts.

    Synthesizes each dialogue turn separately, adds pauses between turns,
    and combines everything into a single audio file.
    """

    def __init__(
        self,
        provider: VoiceProvider = VoiceProvider.OPENAI_TTS,
        alex_voice: VoicePersona = VoicePersona.ALEX_MALE,
        sam_voice: VoicePersona = VoicePersona.SAM_FEMALE,
        output_format: str = "mp3",
        sample_rate: int = 44100,
    ):
        """Initialize audio generator.

        Args:
            provider: TTS provider to use
            alex_voice: Voice persona for Alex
            sam_voice: Voice persona for Sam
            output_format: Audio output format (mp3, wav)
            sample_rate: Audio sample rate in Hz
        """
        self.tts = TTSService(
            provider=provider,
            alex_voice=alex_voice,
            sam_voice=sam_voice,
        )
        self.provider = provider
        self.alex_voice = alex_voice
        self.sam_voice = sam_voice
        self.output_format = output_format
        self.sample_rate = sample_rate

        logger.info(
            f"Initialized PodcastAudioGenerator with {provider.value}, "
            f"format={output_format}"
        )

    async def generate_audio(
        self,
        script: PodcastScript,
        output_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> AudioMetadata:
        """Generate complete podcast audio from a script.

        Args:
            script: Podcast script with dialogue turns
            output_path: Path to save the output audio file
            progress_callback: Optional callback(current, total, message)

        Returns:
            AudioMetadata with information about the generated audio

        Raises:
            RuntimeError: If audio generation fails
        """
        start_time = time.time()
        logger.info(
            f"Generating audio for '{script.title}' ({script.word_count} words)"
        )

        # Count total turns for progress
        total_turns = sum(len(s.dialogue) for s in script.sections)
        current_turn = 0
        audio_segments = []
        turn_count = 0

        try:
            # Import pydub for audio manipulation
            from pydub import AudioSegment
        except ImportError:
            raise RuntimeError(
                "pydub is required for audio generation. "
                "Install with: pip install pydub"
            )

        try:
            # Process each section
            for section_idx, section in enumerate(script.sections):
                logger.debug(
                    f"Processing section {section_idx + 1}/{len(script.sections)}: "
                    f"{section.title}"
                )

                for turn in section.dialogue:
                    current_turn += 1
                    turn_count += 1

                    if progress_callback:
                        progress_callback(
                            current_turn,
                            total_turns,
                            f"Synthesizing: {turn.speaker.upper()} in {section.section_type}",
                        )

                    # Synthesize speech for this turn
                    try:
                        audio_bytes = await self.tts.synthesize(
                            text=turn.text,
                            speaker=turn.speaker,
                        )

                        # Convert to AudioSegment
                        segment = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
                        audio_segments.append(segment)

                        # Add pause after turn
                        pause_ms = int(turn.pause_after * 1000)
                        if pause_ms > 0:
                            audio_segments.append(
                                AudioSegment.silent(duration=pause_ms)
                            )

                    except Exception as e:
                        logger.error(
                            f"Failed to synthesize turn {current_turn}: {e}"
                        )
                        # Add a longer pause as fallback
                        audio_segments.append(
                            AudioSegment.silent(duration=2000)
                        )

                # Add section transition pause
                audio_segments.append(AudioSegment.silent(duration=1000))

            if progress_callback:
                progress_callback(total_turns, total_turns, "Combining audio segments...")

            # Combine all segments
            if not audio_segments:
                raise RuntimeError("No audio segments generated")

            final_audio = audio_segments[0]
            for segment in audio_segments[1:]:
                final_audio = final_audio + segment

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Export to file
            final_audio.export(
                output_path,
                format=self.output_format,
                parameters=["-ar", str(self.sample_rate)],
            )

            generation_time = time.time() - start_time

            metadata = AudioMetadata(
                duration_seconds=len(final_audio) // 1000,
                file_size_bytes=output_path.stat().st_size,
                format=self.output_format,
                sample_rate=self.sample_rate,
                word_count=script.word_count,
                turn_count=turn_count,
                generation_time_seconds=generation_time,
            )

            logger.info(
                f"Audio generated successfully: {metadata.duration_seconds}s, "
                f"{metadata.file_size_bytes / 1024:.1f} KB, "
                f"took {generation_time:.1f}s"
            )

            return metadata

        except Exception as e:
            logger.error(f"Audio generation failed: {e}")
            raise RuntimeError(f"Audio generation failed: {e}")

    async def generate_section_preview(
        self,
        section: PodcastSection,
        output_path: Path,
    ) -> AudioMetadata:
        """Generate audio preview for a single section.

        Useful for reviewing individual sections before full podcast generation.

        Args:
            section: Section to preview
            output_path: Path to save the preview audio

        Returns:
            AudioMetadata for the preview
        """
        logger.info(f"Generating preview for section: {section.title}")

        # Create a mini-script with just this section
        from src.models.podcast import PodcastLength

        mini_script = PodcastScript(
            title=f"Preview: {section.title}",
            length=PodcastLength.BRIEF,
            estimated_duration_seconds=60,
            word_count=sum(len(t.text.split()) for t in section.dialogue),
            sections=[section],
            intro=section if section.section_type == "intro" else None,
            outro=section if section.section_type == "outro" else None,
            sources_summary=[],
        )

        return await self.generate_audio(mini_script, output_path)

    async def estimate_generation_time(
        self,
        script: PodcastScript,
    ) -> dict:
        """Estimate audio generation time and cost.

        Args:
            script: Script to estimate for

        Returns:
            Dict with time and cost estimates
        """
        total_turns = sum(len(s.dialogue) for s in script.sections)
        total_chars = sum(
            len(t.text)
            for s in script.sections
            for t in s.dialogue
        )

        # Rough estimates based on provider
        if self.provider == VoiceProvider.OPENAI_TTS:
            time_per_turn = 2.0  # seconds
            cost_per_char = 0.000015  # $15 per 1M chars
        elif self.provider == VoiceProvider.ELEVENLABS:
            time_per_turn = 3.0  # seconds (includes latency)
            cost_per_char = 0.00030  # $0.30 per 1k chars
        else:
            time_per_turn = 2.5
            cost_per_char = 0.000004  # Google/AWS are cheaper

        estimated_time = total_turns * time_per_turn + 10  # + overhead
        estimated_cost = total_chars * cost_per_char

        return {
            "total_turns": total_turns,
            "total_characters": total_chars,
            "estimated_time_seconds": estimated_time,
            "estimated_time_minutes": estimated_time / 60,
            "estimated_cost_usd": estimated_cost,
            "provider": self.provider.value,
        }

    def get_voice_config(self) -> dict:
        """Get current voice configuration.

        Returns:
            Dict with voice configuration details
        """
        return {
            "provider": self.provider.value,
            "alex_voice": self.alex_voice.value,
            "sam_voice": self.sam_voice.value,
            "output_format": self.output_format,
            "sample_rate": self.sample_rate,
            **self.tts.get_voice_config(),
        }


def get_output_path(podcast_id: int, storage_path: Optional[str] = None) -> Path:
    """Get the output path for a podcast audio file.

    Args:
        podcast_id: Podcast ID
        storage_path: Optional custom storage path

    Returns:
        Path for the audio file
    """
    base_path = Path(storage_path or settings.podcast_storage_path)
    base_path.mkdir(parents=True, exist_ok=True)
    return base_path / f"podcast_{podcast_id}.mp3"


def get_preview_path(script_id: int, section_index: int) -> Path:
    """Get the output path for a section preview.

    Args:
        script_id: Script ID
        section_index: Section index

    Returns:
        Path for the preview audio file
    """
    base_path = Path(settings.podcast_storage_path) / "previews"
    base_path.mkdir(parents=True, exist_ok=True)
    return base_path / f"preview_{script_id}_section_{section_index}.mp3"
