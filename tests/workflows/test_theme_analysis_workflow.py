from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.contracts.workflow_models import ContentQuery, ThemeAnalysisRequest
from src.models.jobs import ResourceReference
from src.models.query import ResolvedContentSet, SelectionPolicy, compute_selection_fingerprint
from src.models.theme import AnalysisStatus, ThemeAnalysis, ThemeAnalysisResult
from src.workflows.theme_analysis import ThemeAnalysisWorkflow


def _resolved() -> ResolvedContentSet:
    policy = SelectionPolicy(
        start_date=datetime(2026, 7, 1, tzinfo=UTC),
        end_date=datetime(2026, 7, 2, tzinfo=UTC),
    )
    return ResolvedContentSet(
        policy=policy,
        fingerprint=compute_selection_fingerprint(policy, [], []),
    )


@pytest.mark.asyncio
async def test_theme_workflow_resolves_once_persists_and_attaches(db_session) -> None:
    resolved = _resolved()
    resolver = Mock()
    resolver.resolve.return_value = resolved
    analyzer = SimpleNamespace(
        analyze_themes=AsyncMock(
            return_value=ThemeAnalysisResult(
                start_date=resolved.policy.start_date or resolved.policy.end_date,
                end_date=resolved.policy.end_date or resolved.policy.start_date,
                content_ids=list(resolved.content_ids),
                summary_ids=list(resolved.summary_ids),
                selection_fingerprint=resolved.fingerprint,
                selection_policy=resolved.policy.model_dump(mode="json"),
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

    workflow = ThemeAnalysisWorkflow(
        operation_service=operations,
        resolver=resolver,
        analyzer=analyzer,
        session_factory=sessions,
    )
    request = ThemeAnalysisRequest(query=ContentQuery(), max_themes=12)

    record = await workflow.execute("51", request)

    resolver.resolve.assert_called_once()
    analyzer.analyze_themes.assert_awaited_once()
    assert record.status == AnalysisStatus.COMPLETED
    assert record.operation_id == 51
    assert record.selection_fingerprint == resolved.fingerprint
    operations.attach_resource.assert_awaited_once_with(
        "51",
        ResourceReference(
            type="theme_analysis", id=str(record.id), url=f"/api/v1/themes/analysis/{record.id}"
        ),
    )
    assert db_session.get(ThemeAnalysis, record.id) is not None

    operations.get.return_value = SimpleNamespace(
        resource=ResourceReference(
            type="theme_analysis",
            id=str(record.id),
            url=f"/api/v1/themes/analysis/{record.id}",
        )
    )
    repeated = await workflow.execute("51", request)
    assert repeated.id == record.id
    assert analyzer.analyze_themes.await_count == 1
    assert operations.attach_resource.await_count == 1
    assert operations.attach_completion.await_count == 2

    result = await workflow.analyze_persisted(request, resolved_set=resolved)
    persisted = db_session.query(ThemeAnalysis).filter_by(operation_id=None).one()
    assert result.selection_fingerprint == resolved.fingerprint
    assert persisted.status == AnalysisStatus.COMPLETED
    assert persisted.selection_fingerprint == resolved.fingerprint

    analyzer.analyze_themes.return_value = analyzer.analyze_themes.return_value.model_copy(
        update={"selection_policy": SelectionPolicy().model_dump(mode="json")}
    )
    operations.get.return_value = SimpleNamespace(resource=None)
    with pytest.raises(ValueError, match="provenance"):
        await workflow.execute("52", request)
    failed = db_session.query(ThemeAnalysis).filter_by(operation_id=52).one()
    assert failed.status == AnalysisStatus.FAILED


@pytest.mark.asyncio
async def test_digest_owned_theme_analysis_reuses_persisted_selection(db_session) -> None:
    resolved = _resolved()
    analyzer = SimpleNamespace(
        analyze_themes=AsyncMock(
            return_value=ThemeAnalysisResult(
                start_date=resolved.policy.start_date or resolved.policy.end_date,
                end_date=resolved.policy.end_date or resolved.policy.start_date,
                content_ids=list(resolved.content_ids),
                summary_ids=list(resolved.summary_ids),
                selection_fingerprint=resolved.fingerprint,
                selection_policy=resolved.policy.model_dump(mode="json"),
            )
        )
    )

    @contextmanager
    def sessions():
        yield db_session

    workflow = ThemeAnalysisWorkflow(analyzer=analyzer, session_factory=sessions)
    request = ThemeAnalysisRequest(query=ContentQuery(), max_themes=12)

    first = await workflow.analyze_persisted(
        request,
        resolved_set=resolved,
        owner_operation_id=61,
    )
    repeated = await workflow.analyze_persisted(
        request,
        resolved_set=resolved,
        owner_operation_id=61,
    )

    records = db_session.query(ThemeAnalysis).filter_by(operation_id=61).all()
    assert len(records) == 1
    assert analyzer.analyze_themes.await_count == 1
    assert repeated.id == first.id == records[0].id
    assert repeated.content_ids == first.content_ids == list(resolved.content_ids)
    assert repeated.summary_ids == first.summary_ids == list(resolved.summary_ids)
    assert repeated.selection_fingerprint == first.selection_fingerprint == resolved.fingerprint


@pytest.mark.asyncio
async def test_completed_theme_reentry_atomically_repairs_operation_projection(db_session) -> None:
    resolved = _resolved()
    record = ThemeAnalysis(
        operation_id=53,
        status=AnalysisStatus.COMPLETED,
        start_date=resolved.policy.start_date,
        end_date=resolved.policy.end_date,
        content_count=0,
        content_ids=[],
        summary_ids=[],
        selection_fingerprint=resolved.fingerprint,
        selection_policy=resolved.policy.model_dump(mode="json"),
    )
    db_session.add(record)
    db_session.flush()
    resource = ResourceReference(
        type="theme_analysis",
        id=str(record.id),
        url=f"/api/v1/themes/analysis/{record.id}",
    )
    operations = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(resource=resource, result=None, progress=0)),
        attach_completion=AsyncMock(),
    )

    @contextmanager
    def sessions():
        yield db_session

    workflow = ThemeAnalysisWorkflow(operation_service=operations, session_factory=sessions)

    repeated = await workflow.execute("53", ThemeAnalysisRequest(query=ContentQuery()))

    assert repeated.id == record.id
    operations.attach_completion.assert_awaited_once_with(
        "53",
        result={"theme_analysis_id": record.id, "selection_fingerprint": resolved.fingerprint},
        resource=resource,
        message="Theme analysis complete",
    )
