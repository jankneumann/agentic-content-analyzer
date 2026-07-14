"""Public podcast audio generation boundary used by durable workflows."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.delivery.audio_generator_v2 import PodcastAudioGeneratorV2
from src.models.podcast import PodcastScript, VoicePersona, VoiceProvider
from src.services.file_storage import FileStorageProvider, get_storage


@dataclass(frozen=True)
class PodcastAudioArtifact:
    """Stored podcast output ready for workflow-owned persistence."""

    storage_path: str
    audio_format: str
    duration_seconds: int
    file_size_bytes: int
    voice_config: dict[str, Any]


class PodcastAudioService:
    """Generate and store podcast bytes without creating ORM records."""

    def __init__(
        self,
        *,
        storage: FileStorageProvider | None = None,
        generator_factory: Callable[..., Any] = PodcastAudioGeneratorV2,
    ) -> None:
        self.storage = storage or get_storage(bucket="podcasts")
        self.generator_factory = generator_factory

    async def generate(
        self,
        script: PodcastScript,
        *,
        podcast_id: int,
        provider: VoiceProvider,
        alex_voice: VoicePersona,
        sam_voice: VoicePersona,
        speed: float,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> PodcastAudioArtifact:
        """Generate audio for a workflow-reserved podcast identifier."""

        generator = self.generator_factory(
            provider=provider,
            alex_voice=alex_voice,
            sam_voice=sam_voice,
            speed=speed,
        )
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as handle:
            output_path = Path(handle.name)
        try:
            metadata = await generator.generate_audio(
                script,
                output_path,
                progress_callback=progress_callback,
            )
            audio = output_path.read_bytes()
            filename = f"podcast_{podcast_id}.mp3"
            storage_path = await self.storage.save(
                data=audio,
                filename=filename,
                content_type="audio/mpeg",
            )
            return PodcastAudioArtifact(
                storage_path=storage_path,
                audio_format=metadata.format,
                duration_seconds=metadata.duration_seconds,
                file_size_bytes=len(audio),
                voice_config=generator.get_voice_config(),
            )
        finally:
            output_path.unlink(missing_ok=True)
