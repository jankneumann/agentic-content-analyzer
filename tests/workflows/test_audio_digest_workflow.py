from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.contracts.workflow_models import AudioDigestRequest
from src.models.audio_digest import AudioDigest, AudioDigestStatus
from src.models.jobs import ResourceReference
from src.services.audio_digest_service import AudioDigestArtifact
from src.workflows.audio_digest import AudioDigestWorkflow


@pytest.mark.asyncio
async def test_audio_digest_uses_public_service_persists_and_attaches(db_session, digest) -> None:
    service = SimpleNamespace(
        generate=AsyncMock(
            return_value=AudioDigestArtifact(
                storage_path="audio-digests/digest.mp3",
                duration_seconds=180.0,
                file_size_bytes=900,
                text_char_count=1200,
                chunk_count=2,
            )
        )
    )
    operations = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(resource=None)),
        update_progress=AsyncMock(),
        attach_resource=AsyncMock(),
        attach_completion=AsyncMock(),
    )

    @contextmanager
    def sessions():
        yield db_session

    workflow = AudioDigestWorkflow(
        operation_service=operations,
        audio_service_factory=lambda _provider: service,
        voice_resolver=lambda voice: f"voice:{voice}",
        session_factory=sessions,
    )

    record = await workflow.execute(
        "91", AudioDigestRequest(digest_id=digest.id, voice="nova", speed=1.25)
    )

    assert record.status == AudioDigestStatus.COMPLETED
    assert record.operation_id == 91
    assert record.audio_url == "audio-digests/digest.mp3"
    service.generate.assert_awaited_once()
    operations.attach_resource.assert_awaited_once_with(
        "91",
        ResourceReference(
            type="audio_digest", id=str(record.id), url=f"/api/v1/audio-digests/{record.id}"
        ),
    )
    assert db_session.get(AudioDigest, record.id) is not None

    operations.get.return_value = SimpleNamespace(
        resource=ResourceReference(
            type="audio_digest", id=str(record.id), url=f"/api/v1/audio-digests/{record.id}"
        )
    )
    repeated = await workflow.execute(
        "91", AudioDigestRequest(digest_id=digest.id, voice="nova", speed=1.25)
    )
    assert repeated.id == record.id
    assert service.generate.await_count == 1
    assert operations.attach_resource.await_count == 1
    assert operations.attach_completion.await_count == 2
