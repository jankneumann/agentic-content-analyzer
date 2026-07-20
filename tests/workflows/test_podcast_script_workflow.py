from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.contracts.workflow_models import PodcastScriptRequest
from src.models.jobs import ResourceReference
from src.models.podcast import (
    PodcastGenerationMetadata,
    PodcastLength,
    PodcastScript,
    PodcastScriptRecord,
    PodcastStatus,
)
from src.workflows.podcast_script import PodcastScriptWorkflow


@pytest.mark.asyncio
async def test_podcast_script_workflow_persists_provenance_and_attaches(db_session, digest) -> None:
    script = PodcastScript(
        title="Episode",
        length=PodcastLength.BRIEF,
        estimated_duration_seconds=300,
        word_count=800,
    )
    generator = SimpleNamespace(
        generate_script=AsyncMock(
            return_value=(script, PodcastGenerationMetadata(content_ids_fetched=[3]))
        ),
        available_content_ids=(3, 5),
        cited_content_ids=(3,),
        selection_fingerprint="a" * 64,
        model_used="test",
        model_version="v1",
        input_tokens=10,
        output_tokens=20,
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

    workflow = PodcastScriptWorkflow(
        operation_service=operations, generator=generator, session_factory=sessions
    )

    record = await workflow.execute("71", PodcastScriptRequest(digest_id=digest.id, length="brief"))

    assert record.status == PodcastStatus.SCRIPT_PENDING_REVIEW
    assert record.operation_id == 71
    assert record.source_content_ids_available == [3, 5]
    assert record.source_content_ids_cited == [3]
    assert record.selection_fingerprint == "a" * 64
    operations.attach_resource.assert_awaited_once_with(
        "71",
        ResourceReference(
            type="podcast_script", id=str(record.id), url=f"/api/v1/scripts/{record.id}"
        ),
    )
    assert db_session.get(PodcastScriptRecord, record.id) is not None

    operations.get.return_value = SimpleNamespace(
        resource=ResourceReference(
            type="podcast_script", id=str(record.id), url=f"/api/v1/scripts/{record.id}"
        )
    )
    repeated = await workflow.execute(
        "71", PodcastScriptRequest(digest_id=digest.id, length="brief")
    )
    assert repeated.id == record.id
    assert generator.generate_script.await_count == 1
    assert operations.attach_resource.await_count == 1
    assert operations.attach_completion.await_count == 2
