from contextlib import contextmanager
from unittest.mock import patch

import pytest

from src.api.script_routes import regenerate_script_task
from src.models.podcast import PodcastLength, PodcastRequest, PodcastScriptRecord, PodcastStatus


@pytest.mark.asyncio
async def test_script_generation_error_leakage(db_session, sample_digest):
    """
    Test that exceptions raised during script generation do not leak sensitive details
    into the database error_message field.
    """
    # 1. Setup - Create a script record using the sample_digest fixture
    script_record = PodcastScriptRecord(
        digest_id=sample_digest.id, length="standard", status=PodcastStatus.SCRIPT_GENERATING.value
    )
    db_session.add(script_record)
    db_session.commit()
    db_session.refresh(script_record)

    script_id = script_record.id
    request = PodcastRequest(digest_id=sample_digest.id, length=PodcastLength.STANDARD)

    # 2. Mock the generator to raise a sensitive exception
    sensitive_info = "Connection failed to postgres://user:pass@1.2.3.4:5432/db"

    @contextmanager
    def mock_get_db():
        yield db_session

    # Patch at the import site (where the class is used), not where it's defined
    with (
        patch("src.api.script_routes.PodcastScriptGenerator") as MockGenerator,
        patch("src.api.script_routes.get_db", side_effect=mock_get_db),
    ):
        instance = MockGenerator.return_value
        # Make generate_script raise an exception
        instance.generate_script.side_effect = Exception(sensitive_info)

        # 3. Execute the task
        await regenerate_script_task(script_id, request)

    # 4. Verify - Check the error message in DB
    db_session.refresh(script_record)
    assert script_record.status == PodcastStatus.FAILED.value

    # This assertion fails if the vulnerability exists
    print(f"Error message in DB: {script_record.error_message}")
    assert sensitive_info not in script_record.error_message
    assert script_record.error_message == "Script generation failed due to an internal error."


@pytest.mark.asyncio
async def test_audio_generation_error_leakage(db_session, sample_digest):
    """
    Test that exceptions raised during audio generation do not leak sensitive details
    into the database error_message field.
    """
    from src.api.podcast_routes import generate_audio_task
    from src.models.podcast import (
        Podcast,
        PodcastScriptRecord,
        PodcastStatus,
        VoicePersona,
        VoiceProvider,
    )

    # 1. Setup - Create a script and podcast record using the sample_digest fixture
    script_record = PodcastScriptRecord(
        digest_id=sample_digest.id,
        length="standard",
        status=PodcastStatus.SCRIPT_APPROVED.value,
        script_json={"title": "Test", "sections": []},
    )
    db_session.add(script_record)
    db_session.commit()

    podcast = Podcast(
        script_id=script_record.id,
        status="generating",
        voice_provider=VoiceProvider.OPENAI_TTS.value,
        audio_format="mp3",
    )
    db_session.add(podcast)
    db_session.commit()

    podcast_id = podcast.id
    script_id = script_record.id

    # 2. Mock the generator to raise a sensitive exception
    sensitive_info = "Connection failed to s3://secret-bucket/key"

    @contextmanager
    def mock_get_db():
        yield db_session

    # PodcastAudioGenerator is imported lazily inside generate_audio_task,
    # so patching the source module works here
    with (
        patch("src.delivery.audio_generator.PodcastAudioGenerator") as MockGenerator,
        patch("src.api.podcast_routes.get_db", side_effect=mock_get_db),
    ):
        instance = MockGenerator.return_value
        # Make generate_podcast raise an exception
        instance.generate_podcast.side_effect = Exception(sensitive_info)

        # 3. Execute the task
        await generate_audio_task(
            script_id=script_id,
            podcast_id=podcast_id,
            voice_provider=VoiceProvider.OPENAI_TTS,
            alex_voice=VoicePersona.ALEX_MALE,
            sam_voice=VoicePersona.SAM_FEMALE,
        )

    # 4. Verify - Check the error message in DB
    db_session.refresh(podcast)
    db_session.refresh(script_record)

    assert podcast.status == "failed"
    assert script_record.status == PodcastStatus.FAILED.value

    print(f"Podcast error: {podcast.error_message}")
    print(f"Script error: {script_record.error_message}")

    assert sensitive_info not in podcast.error_message
    assert podcast.error_message == "Audio generation failed due to an internal error."

    assert sensitive_info not in script_record.error_message
    assert script_record.error_message == "Audio generation failed due to an internal error."
