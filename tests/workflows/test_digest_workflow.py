from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.contracts.workflow_models import DigestCreateRequest
from src.models.content import ContentSource
from src.models.digest import Digest, DigestData, DigestStatus, DigestType
from src.models.jobs import ResourceReference
from src.models.query import (
    ResolvedContentItem,
    ResolvedContentSet,
    SelectionPolicy,
    compute_selection_fingerprint,
)
from src.models.theme import ThemeAnalysisResult
from src.workflows.digest import DigestWorkflow, validate_digest_provenance


@pytest.mark.asyncio
async def test_digest_workflow_persists_exact_selection_and_attaches(db_session) -> None:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    end = datetime(2026, 7, 2, tzinfo=UTC)
    policy = SelectionPolicy(start_date=start, end_date=end)
    resolved = ResolvedContentSet(
        policy=policy,
        fingerprint=compute_selection_fingerprint(policy, [], []),
    )
    resolver = Mock()
    resolver.resolve.return_value = resolved
    theme_workflow = SimpleNamespace(
        analyze_persisted=AsyncMock(
            return_value=ThemeAnalysisResult(
                start_date=start,
                end_date=end,
                selection_fingerprint=resolved.fingerprint,
            )
        )
    )
    creator = SimpleNamespace(
        create_digest=AsyncMock(
            return_value=DigestData(
                digest_type=DigestType.DAILY,
                period_start=start,
                period_end=end,
                title="Daily",
                executive_overview="Overview",
                newsletter_count=0,
                agent_framework="test",
                model_used="test",
                source_content_ids=[],
                source_summary_ids=[],
                selection_fingerprint=resolved.fingerprint,
                selection_policy=policy.model_dump(mode="json"),
            )
        )
    )
    operations = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(resource=None)),
        update_progress=AsyncMock(),
        attach_resource=AsyncMock(),
        attach_result=AsyncMock(),
    )

    @contextmanager
    def sessions():
        yield db_session

    workflow = DigestWorkflow(
        operation_service=operations,
        resolver=resolver,
        theme_workflow=theme_workflow,
        creator=creator,
        session_factory=sessions,
    )
    request = DigestCreateRequest(digest_type="daily", period_start=start, period_end=end)

    record = await workflow.execute("61", request, resolved_set=resolved)

    assert record.status == DigestStatus.PENDING_REVIEW
    assert record.operation_id == 61
    assert record.selection_fingerprint == resolved.fingerprint
    resolver.resolve.assert_not_called()
    assert theme_workflow.analyze_persisted.await_args.kwargs["resolved_set"] is resolved
    assert creator.create_digest.await_args.args[1] is resolved
    creator.create_digest.assert_awaited_once()
    operations.attach_resource.assert_awaited_once_with(
        "61",
        ResourceReference(type="digest", id=str(record.id), url=f"/api/v1/digests/{record.id}"),
    )
    assert db_session.get(Digest, record.id) is not None

    operations.get.return_value = SimpleNamespace(
        resource=ResourceReference(
            type="digest", id=str(record.id), url=f"/api/v1/digests/{record.id}"
        )
    )
    repeated = await workflow.execute("61", request, resolved_set=resolved)
    assert repeated.id == record.id
    assert creator.create_digest.await_count == 1
    assert operations.attach_resource.await_count == 1
    assert operations.attach_result.await_count == 2

    creator.create_digest.return_value = creator.create_digest.return_value.model_copy(
        update={"selection_fingerprint": "b" * 64}
    )
    operations.get.return_value = SimpleNamespace(resource=None)
    with pytest.raises(ValueError, match="provenance"):
        await workflow.execute("63", request, resolved_set=resolved)
    mismatched = db_session.query(Digest).filter_by(operation_id=63).one()
    assert mismatched.status == DigestStatus.FAILED


@pytest.mark.asyncio
async def test_digest_failure_keeps_reserved_failed_resource(db_session) -> None:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    end = datetime(2026, 7, 2, tzinfo=UTC)
    policy = SelectionPolicy(start_date=start, end_date=end)
    resolved = ResolvedContentSet(
        policy=policy,
        fingerprint=compute_selection_fingerprint(policy, [], []),
    )
    resolver = Mock()
    resolver.resolve.return_value = resolved
    theme_workflow = SimpleNamespace(
        analyze_persisted=AsyncMock(
            return_value=ThemeAnalysisResult(
                start_date=start,
                end_date=end,
                selection_fingerprint=resolved.fingerprint,
            )
        )
    )
    creator = SimpleNamespace(
        create_digest=AsyncMock(side_effect=RuntimeError("generation failed"))
    )
    operations = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(resource=None)),
        update_progress=AsyncMock(),
        attach_resource=AsyncMock(),
        attach_result=AsyncMock(),
    )

    @contextmanager
    def sessions():
        yield db_session

    workflow = DigestWorkflow(
        operation_service=operations,
        resolver=resolver,
        theme_workflow=theme_workflow,
        creator=creator,
        session_factory=sessions,
    )

    with pytest.raises(RuntimeError, match="generation failed"):
        await workflow.execute(
            "62", DigestCreateRequest(digest_type="daily", period_start=start, period_end=end)
        )

    failed = db_session.query(Digest).order_by(Digest.id.desc()).first()
    assert failed is not None
    assert failed.status == DigestStatus.FAILED
    operations.attach_resource.assert_awaited_once()
    operations.attach_result.assert_not_awaited()

    changed_policy = SelectionPolicy(
        start_date=start,
        end_date=datetime(2026, 7, 3, tzinfo=UTC),
    )
    resolver.resolve.return_value = ResolvedContentSet(
        policy=changed_policy,
        fingerprint=compute_selection_fingerprint(changed_policy, [], []),
    )
    operations.get.return_value = SimpleNamespace(
        resource=ResourceReference(
            type="digest", id=str(failed.id), url=f"/api/v1/digests/{failed.id}"
        )
    )
    with pytest.raises(ValueError, match="selection changed"):
        await workflow.execute(
            "62", DigestCreateRequest(digest_type="daily", period_start=start, period_end=end)
        )
    assert creator.create_digest.await_count == 1


@pytest.mark.parametrize(
    "updates",
    [
        {"newsletter_count": 0},
        {"source_content_ids": None},
        {"source_summary_ids": None},
    ],
)
def test_digest_provenance_fails_closed_on_count_and_nullable_ids(updates: dict) -> None:
    now = datetime(2026, 7, 1, tzinfo=UTC)
    policy = SelectionPolicy(source_types=(ContentSource.RSS,))
    item = ResolvedContentItem(
        content_id=31,
        summary_id=41,
        source_type=ContentSource.RSS,
        title="Existing",
        selection_date=now,
    )
    resolved = ResolvedContentSet(
        policy=policy,
        items=(item,),
        fingerprint=compute_selection_fingerprint(policy, [31], [41]),
    )
    candidate = SimpleNamespace(
        source_content_ids=[31],
        source_summary_ids=[41],
        selection_fingerprint=resolved.fingerprint,
        selection_policy=policy.model_dump(mode="json"),
        newsletter_count=1,
    )
    for field, value in updates.items():
        setattr(candidate, field, value)

    with pytest.raises(ValueError, match="provenance"):
        validate_digest_provenance(candidate, resolved)
