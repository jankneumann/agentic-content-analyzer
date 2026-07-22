from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.models.audio_digest import AudioDigest, AudioDigestStatus
from src.models.digest import Digest
from src.models.jobs import ResourceReference
from src.models.podcast import Podcast, PodcastScriptRecord
from src.models.theme import AnalysisStatus, ThemeAnalysis
from src.workflows.audio_digest import AudioDigestWorkflow
from src.workflows.digest import DigestWorkflow
from src.workflows.podcast_audio import PodcastAudioWorkflow
from src.workflows.podcast_script import PodcastScriptWorkflow
from src.workflows.resource import recover_owned_resource
from src.workflows.theme_analysis import ThemeAnalysisWorkflow


@pytest.mark.asyncio
async def test_recover_owned_resource_repairs_missing_operation_projection(
    db_session, digest
) -> None:
    digest.operation_id = 17
    db_session.flush()
    operations = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(resource=None)),
        attach_resource=AsyncMock(),
    )

    @contextmanager
    def sessions():
        yield db_session

    recovered = await recover_owned_resource(
        operations=operations,
        session_factory=sessions,
        model=Digest,
        operation_id="17",
        resource_type="digest",
        resource_url=lambda record_id: f"/api/v1/digests/{record_id}",
    )

    assert recovered is digest
    operations.attach_resource.assert_awaited_once_with(
        "17",
        ResourceReference(type="digest", id=str(digest.id), url=f"/api/v1/digests/{digest.id}"),
    )


@pytest.mark.asyncio
async def test_recover_owned_resource_rejects_wrong_attached_type(db_session) -> None:
    operations = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(
                resource=ResourceReference(type="podcast", id="1", url="/api/v1/podcasts/1")
            )
        )
    )

    @contextmanager
    def sessions():
        yield db_session

    with pytest.raises(ValueError, match="another resource type"):
        await recover_owned_resource(
            operations=operations,
            session_factory=sessions,
            model=Digest,
            operation_id=17,
            resource_type="digest",
            resource_url=lambda record_id: f"/api/v1/digests/{record_id}",
        )


@pytest.mark.asyncio
async def test_recover_owned_resource_claims_legacy_owner_and_rejects_conflict(
    db_session, digest
) -> None:
    reference = ResourceReference(
        type="digest", id=str(digest.id), url=f"/api/v1/digests/{digest.id}"
    )
    operations = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(resource=reference)))

    @contextmanager
    def sessions():
        yield db_session

    recovered = await recover_owned_resource(
        operations=operations,
        session_factory=sessions,
        model=Digest,
        operation_id=17,
        resource_type="digest",
        resource_url=lambda record_id: f"/api/v1/digests/{record_id}",
    )
    assert recovered.operation_id == 17

    digest.operation_id = 18
    db_session.flush()
    with pytest.raises(ValueError, match="belongs to operation 18"):
        await recover_owned_resource(
            operations=operations,
            session_factory=sessions,
            model=Digest,
            operation_id=17,
            resource_type="digest",
            resource_url=lambda record_id: f"/api/v1/digests/{record_id}",
        )


@pytest.mark.asyncio
async def test_all_generated_workflows_repair_reservation_attachment_crash(
    db_session,
    digest,
    podcast_script_record,
    podcast,
) -> None:
    """Every resource workflow must recover DB ownership without creating a duplicate."""

    theme = ThemeAnalysis(
        operation_id=118,
        status=AnalysisStatus.RUNNING,
        start_date=digest.period_start,
        end_date=digest.period_end,
        content_count=0,
        content_ids=[],
        summary_ids=[],
    )
    audio = AudioDigest(
        operation_id=121,
        digest_id=digest.id,
        voice="nova",
        speed=1.0,
        provider="openai",
        status=AudioDigestStatus.PROCESSING,
    )
    digest.operation_id = 117
    podcast_script_record.operation_id = 119
    podcast.operation_id = 120
    db_session.add_all([theme, audio])
    db_session.flush()
    operations = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(resource=None)),
        attach_resource=AsyncMock(),
    )

    @contextmanager
    def sessions():
        yield db_session

    workflows_and_records = (
        (
            DigestWorkflow(
                operation_service=operations,
                resolver=SimpleNamespace(),
                theme_workflow=SimpleNamespace(),
                creator=SimpleNamespace(),
                session_factory=sessions,
            ),
            digest,
            117,
        ),
        (
            ThemeAnalysisWorkflow(
                operation_service=operations,
                resolver=SimpleNamespace(),
                analyzer=SimpleNamespace(),
                session_factory=sessions,
            ),
            theme,
            118,
        ),
        (
            PodcastScriptWorkflow(
                operation_service=operations,
                generator=SimpleNamespace(),
                session_factory=sessions,
            ),
            podcast_script_record,
            119,
        ),
        (
            PodcastAudioWorkflow(
                operation_service=operations,
                audio_service=SimpleNamespace(),
                session_factory=sessions,
            ),
            podcast,
            120,
        ),
        (
            AudioDigestWorkflow(
                operation_service=operations,
                audio_service_factory=lambda _provider: SimpleNamespace(),
                session_factory=sessions,
            ),
            audio,
            121,
        ),
    )

    for workflow, expected, operation_id in workflows_and_records:
        recovered = await workflow._existing(operation_id)
        assert recovered.id == expected.id

    assert operations.attach_resource.await_count == len(workflows_and_records)
    assert db_session.query(Digest).filter_by(operation_id=117).count() == 1
    assert db_session.query(ThemeAnalysis).filter_by(operation_id=118).count() == 1
    assert db_session.query(PodcastScriptRecord).filter_by(operation_id=119).count() == 1
    assert db_session.query(Podcast).filter_by(operation_id=120).count() == 1
    assert db_session.query(AudioDigest).filter_by(operation_id=121).count() == 1
