"""Public, persistence-free audio service contract tests."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.delivery.tts_service import TTSService
from src.models.podcast import (
    DialogueTurn,
    PodcastLength,
    PodcastScript,
    PodcastSection,
    VoicePersona,
    VoiceProvider,
)
from src.services.audio_digest_service import AudioDigestService
from src.services.podcast_audio_service import PodcastAudioService


def _script() -> PodcastScript:
    section = PodcastSection(
        section_type="intro",
        title="Intro",
        dialogue=[DialogueTurn(speaker="alex", text="Hello", pause_after=0)],
    )
    return PodcastScript(
        title="Episode",
        length=PodcastLength.BRIEF,
        estimated_duration_seconds=10,
        word_count=1,
        sections=[section],
        intro=section,
    )


@pytest.mark.asyncio
async def test_podcast_audio_service_generates_and_stores_without_database_reservation() -> None:
    generator = MagicMock()

    async def generate_audio(script, output_path: Path, progress_callback=None):
        output_path.write_bytes(b"podcast-bytes")
        return SimpleNamespace(
            duration_seconds=10,
            file_size_bytes=13,
            format="mp3",
            sample_rate=44100,
            word_count=1,
            turn_count=1,
            generation_time_seconds=0.1,
        )

    generator.generate_audio = AsyncMock(side_effect=generate_audio)
    generator.get_voice_config.return_value = {"provider": "openai_tts"}
    factory = MagicMock(return_value=generator)
    storage = MagicMock()
    storage.save = AsyncMock(return_value="podcasts/podcast_41.mp3")
    service = PodcastAudioService(storage=storage, generator_factory=factory)

    result = await service.generate(
        _script(),
        podcast_id=41,
        provider=VoiceProvider.OPENAI_TTS,
        alex_voice=VoicePersona.ALEX_MALE,
        sam_voice=VoicePersona.SAM_FEMALE,
        speed=1.0,
    )

    generator.generate_audio.assert_awaited_once()
    storage.save.assert_awaited_once_with(
        data=b"podcast-bytes",
        filename="podcast_41.mp3",
        content_type="audio/mpeg",
    )
    assert result.storage_path == "podcasts/podcast_41.mp3"
    assert result.duration_seconds == 10
    assert result.voice_config == {"provider": "openai_tts"}


@pytest.mark.asyncio
async def test_audio_digest_service_uses_only_public_tts_and_storage() -> None:
    tts = MagicMock()
    tts.supports_ssml = False
    tts.provider_name = "openai"
    tts.synthesize_voice = AsyncMock(return_value=b"digest-bytes")
    storage = MagicMock()
    storage.save = AsyncMock(return_value="audio-digests/audio_digest_9.mp3")
    preparer = MagicMock()
    preparer.prepare_digest.return_value = "Prepared digest"
    preparer.estimate_duration.return_value = 15.0
    service = AudioDigestService(tts=tts, storage=storage, text_preparer=preparer)
    digest = SimpleNamespace(id=3)

    result = await service.generate(
        digest,
        audio_digest_id=9,
        voice_id="nova",
        speed=1.1,
    )

    tts.synthesize_voice.assert_awaited_once_with(
        "Prepared digest",
        "nova",
        speed=1.1,
    )
    storage.save.assert_awaited_once_with(
        data=b"digest-bytes",
        filename="audio_digest_9.mp3",
        content_type="audio/mpeg",
    )
    assert result.storage_path == "audio-digests/audio_digest_9.mp3"
    assert result.chunk_count == 1
    assert result.text_char_count == len("Prepared digest")


def test_public_audio_services_do_not_reserve_orm_records() -> None:
    for filename in (
        "src/services/podcast_audio_service.py",
        "src/services/audio_digest_service.py",
    ):
        source = Path(filename).read_text()
        assert "get_db" not in source
        assert "session.add" not in source
        assert "._provider" not in source


def test_production_audio_callers_use_public_services() -> None:
    audio_route = Path("src/api/audio_digest_routes.py").read_text()
    podcast_route = Path("src/api/podcast_routes.py").read_text()
    podcast_creator = Path("src/processors/podcast_creator.py").read_text()

    assert "AudioDigestService" in audio_route
    assert "_synthesize_short" not in audio_route
    assert "_synthesize_long" not in audio_route
    assert "PodcastAudioService" in podcast_creator
    assert "PodcastAudioGenerator(" not in podcast_creator
    assert "PodcastAudioGeneratorV2(" not in podcast_creator
    assert "PodcastAudioService" in podcast_route
    assert "PodcastAudioGenerator" not in podcast_route
    assert 'Path("output/podcasts")' not in podcast_route


@pytest.mark.asyncio
async def test_tts_exposes_provider_capabilities_and_explicit_voice_synthesis() -> None:
    service = object.__new__(TTSService)
    service.provider_type = VoiceProvider.OPENAI_TTS
    service._provider = MagicMock()
    service._provider.supports_ssml.return_value = True
    service._provider.synthesize = AsyncMock(return_value=b"audio")

    result = await service.synthesize_voice("text", "nova", speed=1.2)

    assert service.supports_ssml is True
    assert service.provider_name == "openai"
    assert result == b"audio"
    service._provider.synthesize.assert_awaited_once_with("text", "nova", speed=1.2)
