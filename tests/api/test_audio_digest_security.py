from contextlib import contextmanager
from unittest.mock import patch

import pytest

from src.api.audio_digest_routes import _generate_audio_digest_task
from src.models.audio_digest import AudioDigest, AudioDigestStatus


@pytest.mark.asyncio
async def test_audio_digest_generation_error_leakage(db_session, sample_digest):
    """
    Test that exceptions raised during audio digest generation do not leak sensitive details
    into the database error_message field.
    """
    # 1. Setup - Create an audio digest record using the sample_digest fixture
    audio_digest = AudioDigest(
        digest_id=sample_digest.id,
        voice="nova",
        speed=1.0,
        provider="openai",
        status=AudioDigestStatus.PENDING,
    )
    db_session.add(audio_digest)
    db_session.commit()
    db_session.refresh(audio_digest)

    audio_digest_id = audio_digest.id
    digest_id = sample_digest.id

    # 2. Mock the generator to raise a sensitive exception
    sensitive_info = "Connection failed to s3://secret-bucket/audio-key"

    @contextmanager
    def mock_get_db():
        yield db_session

    with (
        patch("src.api.audio_digest_routes.AudioDigestGenerator") as MockGenerator,
        patch("src.api.audio_digest_routes.get_db", side_effect=mock_get_db),
    ):
        instance = MockGenerator.return_value
        # Make the first method called raise an exception
        # We also need to mock text_preparer and _synthesize_short/_long?
        # A simpler way is to just let AudioDigestGenerator.__init__ raise it
        MockGenerator.side_effect = Exception(sensitive_info)

        # 3. Execute the task
        await _generate_audio_digest_task(
            audio_digest_id=audio_digest_id,
            digest_id=digest_id,
            voice="nova",
            speed=1.0,
            provider="openai",
        )

    # 4. Verify - Check the error message in DB
    db_session.refresh(audio_digest)

    assert audio_digest.status == AudioDigestStatus.FAILED

    print(f"Audio digest error: {audio_digest.error_message}")

    assert sensitive_info not in str(audio_digest.error_message)
    assert audio_digest.error_message == "Audio generation failed due to an internal error."
