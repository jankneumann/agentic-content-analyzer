from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.contracts.workflow_models import PodcastAudioRequest
from src.models.jobs import ResourceReference
from src.models.podcast import Podcast, PodcastLength, PodcastScript, PodcastStatus
from src.services.podcast_audio_service import PodcastAudioArtifact
from src.workflows.podcast_audio import PodcastAudioWorkflow


@pytest.mark.asyncio
async def test_podcast_audio_requires_approved_script(db_session, podcast_script_record) -> None:
    podcast_script_record.status = PodcastStatus.SCRIPT_PENDING_REVIEW
    db_session.flush()

    @contextmanager
    def sessions():
        yield db_session

    workflow = PodcastAudioWorkflow(
        operation_service=SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(resource=None))
        ),
        audio_service=SimpleNamespace(generate=AsyncMock()),
        session_factory=sessions,
    )

    with pytest.raises(ValueError, match="approved"):
        await workflow.execute("81", PodcastAudioRequest(script_id=podcast_script_record.id))


@pytest.mark.asyncio
async def test_podcast_audio_reserves_generates_and_attaches(
    db_session, podcast_script_record
) -> None:
    podcast_script_record.status = PodcastStatus.SCRIPT_APPROVED
    podcast_script_record.script_json = PodcastScript(
        title="Approved",
        length=PodcastLength.BRIEF,
        estimated_duration_seconds=300,
        word_count=800,
    ).model_dump(mode="json")
    db_session.flush()
    service = SimpleNamespace(
        generate=AsyncMock(
            return_value=PodcastAudioArtifact(
                storage_path="podcasts/episode.mp3",
                audio_format="mp3",
                duration_seconds=300,
                file_size_bytes=1234,
                voice_config={"provider": "test"},
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

    workflow = PodcastAudioWorkflow(
        operation_service=operations, audio_service=service, session_factory=sessions
    )

    record = await workflow.execute("82", PodcastAudioRequest(script_id=podcast_script_record.id))

    assert record.status == "completed"
    assert record.operation_id == 82
    assert record.audio_url == "podcasts/episode.mp3"
    operations.attach_resource.assert_awaited_once_with(
        "82",
        ResourceReference(type="podcast", id=str(record.id), url=f"/api/v1/podcasts/{record.id}"),
    )
    assert db_session.get(Podcast, record.id) is not None

    operations.get.return_value = SimpleNamespace(
        resource=ResourceReference(
            type="podcast", id=str(record.id), url=f"/api/v1/podcasts/{record.id}"
        )
    )
    repeated = await workflow.execute("82", PodcastAudioRequest(script_id=podcast_script_record.id))
    assert repeated.id == record.id
    assert service.generate.await_count == 1
    assert operations.attach_resource.await_count == 1
    assert operations.attach_completion.await_count == 2
