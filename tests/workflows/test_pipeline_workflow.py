from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.config.sources import RSSSource, SourcesConfig, WebSearchSource
from src.contracts.workflow_models import IngestionResultV1, IngestionResultV2, PipelineRequest
from src.ingestion.registry import SOURCE_REGISTRY
from src.models.content import ContentSource
from src.models.jobs import (
    JobRecord,
    JobStatus,
    OperationPayloadV2,
    OperationStatus,
    OperationType,
    ResourceReference,
)
from src.models.query import (
    ResolvedContentItem,
    ResolvedContentSet,
    SelectionPolicy,
    compute_selection_fingerprint,
)
from src.services.operation_service import OperationService
from src.workflows.pipeline import (
    PipelineWorkflow,
    aggregate_pipeline_ingestion_outcome,
    build_pipeline_ingestion_summary,
)

START = datetime(2026, 7, 13, tzinfo=UTC)
END = datetime(2026, 7, 14, tzinfo=UTC)


def _ingestion_result(*content_ids: int) -> dict:
    return IngestionResultV1(
        command_key="rss",
        resolved_route="rss",
        emitted_sources=["rss"],
        items_ingested=len(content_ids),
        content_ids=list(content_ids),
    ).model_dump(mode="json")


def _typed_ingestion_result(
    outcome: str,
    *,
    items_ingested: int = 0,
    items_skipped: int = 0,
    items_failed: int = 0,
) -> dict:
    status = "error" if outcome == "failed" else "partial" if outcome == "partial" else "ok"
    return IngestionResultV2(
        command_key="rss",
        resolved_route="rss",
        emitted_sources=["rss"],
        status=status,
        outcome=outcome,
        items_ingested=items_ingested,
        items_skipped=items_skipped,
        items_failed=items_failed,
        content_ids=list(range(1, items_ingested + 1)),
        errors=[],
        warnings=[],
        errors_omitted=0,
        warnings_omitted=0,
        source_outcomes=[],
        source_outcomes_omitted=0,
        details={},
        details_omitted=0,
    ).model_dump(mode="json")


@pytest.mark.parametrize(
    ("pipeline_status", "child_outcomes", "expected"),
    [
        ("cancelled", ["success"], "cancelled"),
        ("failed", ["success"], "failed"),
        ("completed", ["partial"], "partial"),
        ("completed", ["failed"], "partial"),
        ("completed", ["cancelled"], "partial"),
        ("completed", ["success", "unknown"], "unknown"),
        ("completed", [], "zero_items"),
        ("completed", ["zero_items", "zero_items"], "zero_items"),
        ("completed", ["success", "zero_items"], "success"),
    ],
)
def test_pipeline_aggregate_outcome_follows_d2_precedence(
    pipeline_status: str,
    child_outcomes: list[str],
    expected: str,
) -> None:
    assert aggregate_pipeline_ingestion_outcome(pipeline_status, child_outcomes) == expected


@pytest.mark.parametrize(
    ("status", "result", "expected_outcome", "expected_counts"),
    [
        (
            OperationStatus.COMPLETED,
            _typed_ingestion_result("success", items_ingested=2),
            "success",
            (2, 0, 0),
        ),
        (
            OperationStatus.COMPLETED,
            _typed_ingestion_result("zero_items"),
            "zero_items",
            (0, 0, 0),
        ),
        (
            OperationStatus.COMPLETED,
            _typed_ingestion_result("partial", items_ingested=1, items_failed=1),
            "partial",
            (1, 0, 1),
        ),
        (
            OperationStatus.FAILED,
            _typed_ingestion_result("failed", items_failed=1),
            "failed",
            (0, 0, 1),
        ),
        (OperationStatus.CANCELLED, None, "cancelled", (None, None, None)),
        (OperationStatus.COMPLETED, _ingestion_result(1), "unknown", (None, None, None)),
    ],
)
def test_pipeline_source_summary_uses_lifecycle_and_typed_result(
    status: OperationStatus,
    result: dict | None,
    expected_outcome: str,
    expected_counts: tuple[int | None, int | None, int | None],
) -> None:
    summary = build_pipeline_ingestion_summary(
        [{"kind": "rss"}],
        [_handle(20, OperationType.INGESTION_EXECUTE, status, result=result)],
        pipeline_status="completed",
    )

    assert summary.sources[0].outcome == expected_outcome
    assert (
        summary.sources[0].items_ingested,
        summary.sources[0].items_skipped,
        summary.sources[0].items_failed,
    ) == expected_counts


def test_pipeline_aggregate_includes_outcomes_omitted_from_bounded_source_details() -> None:
    commands = [{"kind": "rss"} for _ in range(101)]
    handles = [
        _handle(
            operation_id,
            OperationType.INGESTION_EXECUTE,
            OperationStatus.COMPLETED,
            result=_typed_ingestion_result("success", items_ingested=1),
        )
        for operation_id in range(1, 101)
    ]
    handles.append(
        _handle(
            101,
            OperationType.INGESTION_EXECUTE,
            OperationStatus.COMPLETED,
            result=_typed_ingestion_result("partial", items_ingested=1, items_failed=1),
        )
    )

    summary = build_pipeline_ingestion_summary(
        commands,
        handles,
        pipeline_status="completed",
    )

    assert summary.outcome == "partial"
    assert len(summary.sources) == 100
    assert summary.sources_omitted == 1


def _handle(
    operation_id: int,
    operation_type: OperationType,
    status: OperationStatus,
    *,
    result: dict | None = None,
    resource: ResourceReference | None = None,
    problem: object | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        operation_id=str(operation_id),
        operation_type=operation_type,
        status=status,
        result=result,
        resource=resource,
        problem=problem,
        is_terminal=status
        in {OperationStatus.COMPLETED, OperationStatus.FAILED, OperationStatus.CANCELLED},
    )


class FakeOperations:
    def __init__(self) -> None:
        self.handles = {10: _handle(10, OperationType.PIPELINE_RUN, OperationStatus.IN_PROGRESS)}
        self.next_id = 20
        self.submissions: list[tuple[OperationType, dict, str]] = []
        self.defer_calls: list[dict] = []
        self.attach_resource = AsyncMock()
        self.attach_result = AsyncMock()
        self.attach_completion = AsyncMock()
        self.update_progress = AsyncMock()

    async def get(self, operation_id: str | int) -> SimpleNamespace:
        return self.handles[int(operation_id)]

    async def submit_child(
        self,
        parent_operation_id: str | int,
        operation_type: OperationType,
        normalized_input: dict,
        *,
        idempotency_key: str,
    ) -> SimpleNamespace:
        assert int(parent_operation_id) == 10
        self.submissions.append((operation_type, normalized_input, idempotency_key))
        child = _handle(self.next_id, operation_type, OperationStatus.QUEUED)
        self.handles[self.next_id] = child
        self.next_id += 1
        return child

    async def defer(
        self,
        operation_id: str | int,
        *,
        checkpoint: dict,
        progress: int,
        message: str,
    ) -> SimpleNamespace:
        self.defer_calls.append(
            {"checkpoint": checkpoint, "progress": progress, "message": message}
        )
        parent = _handle(
            int(operation_id),
            OperationType.PIPELINE_RUN,
            OperationStatus.QUEUED,
            result=checkpoint,
        )
        self.handles[int(operation_id)] = parent
        return parent


def _request(*, sources: list[str] | None = None, continue_on_error: bool = True):
    return PipelineRequest(
        period="daily",
        period_start=START,
        period_end=END,
        sources=sources,
        continue_on_source_error=continue_on_error,
    )


@pytest.mark.asyncio
async def test_pipeline_defers_and_resumes_without_duplicate_children_or_stages() -> None:
    operations = FakeOperations()
    config = SourcesConfig(
        sources=[
            RSSSource(url="https://example.com/feed"),
            WebSearchSource(provider="grok", prompt="agent systems"),
        ]
    )
    policy = SelectionPolicy(
        source_types=(ContentSource.RSS, ContentSource.XSEARCH),
        start_date=START,
        end_date=END,
    )
    item = ResolvedContentItem(
        content_id=31,
        summary_id=41,
        source_type=ContentSource.RSS,
        title="One",
        selection_date=START,
    )
    resolved = ResolvedContentSet(
        policy=policy,
        items=(item,),
        fingerprint=compute_selection_fingerprint(policy, [31], [41]),
    )
    resolver = Mock()
    resolver.resolve.return_value = resolved
    digest = SimpleNamespace(
        id=91,
        source_content_ids=[31],
        source_summary_ids=[41],
        selection_fingerprint=resolved.fingerprint,
        selection_policy=policy.model_dump(mode="json"),
        newsletter_count=1,
    )
    digest_loader = Mock(return_value=digest)
    workflow = PipelineWorkflow(
        operation_service=operations,
        registry=SOURCE_REGISTRY,
        source_config_loader=lambda: config,
        resolver=resolver,
        digest_loader=digest_loader,
    )

    first = await workflow.execute("10", _request())
    assert first["deferred"] is True
    assert first["stage"] == "ingestion"
    assert operations.handles[10].status is OperationStatus.QUEUED
    assert [submission[0] for submission in operations.submissions] == [
        OperationType.INGESTION_EXECUTE,
        OperationType.INGESTION_EXECUTE,
    ]
    source_commands = [submission[1] for submission in operations.submissions]
    assert [command["kind"] for command in source_commands] == ["rss", "x_search"]
    assert source_commands[0]["configured_sources"][0]["url"] == "https://example.com/feed"
    assert source_commands[1]["configured_sources"][0]["prompt"] == "agent systems"
    assert source_commands[1]["prompt"] == "agent systems"

    source_ids = first["source_operation_ids"]
    operations.handles[source_ids[0]] = _handle(
        source_ids[0],
        OperationType.INGESTION_EXECUTE,
        OperationStatus.COMPLETED,
        result=_ingestion_result(31),
    )
    operations.handles[source_ids[1]] = _handle(
        source_ids[1],
        OperationType.INGESTION_EXECUTE,
        OperationStatus.FAILED,
        problem=SimpleNamespace(model_dump=lambda **_: {"detail": "rate limited"}),
    )
    second = await workflow.execute("10", _request())
    assert second["stage"] == "summarization"
    assert len(operations.submissions) == 3
    assert operations.submissions[-1][0] is OperationType.SUMMARIZATION_RUN
    assert operations.submissions[-1][1] == {
        "content_ids": [31],
        "query": None,
        "force_reprocess": False,
    }
    assert {result["status"] for result in second["source_results"]} == {"completed", "failed"}
    assert second["ingestion_summary"]["outcome"] == "partial"
    assert [source["outcome"] for source in second["ingestion_summary"]["sources"]] == [
        "unknown",
        "failed",
    ]

    summary_id = second["summary_operation_id"]
    operations.handles[summary_id] = _handle(
        summary_id,
        OperationType.SUMMARIZATION_RUN,
        OperationStatus.COMPLETED,
        result={"completed_ids": [31], "failed_ids": []},
    )
    third = await workflow.execute("10", _request())
    assert third["stage"] == "digest"
    assert resolver.resolve.call_count == 1
    resolved_query = resolver.resolve.call_args.args[0]
    assert resolved_query.source_types is None
    assert resolved_query.start_date == START
    assert resolved_query.end_date == END
    digest_submission = operations.submissions[-1]
    assert digest_submission[0] is OperationType.DIGEST_CREATE
    assert digest_submission[1]["resolved_set"] == resolved.model_dump(mode="json")

    digest_id = third["digest_operation_id"]
    digest_resource = ResourceReference(type="digest", id="91", url="/api/v1/digests/91")
    operations.handles[digest_id] = _handle(
        digest_id,
        OperationType.DIGEST_CREATE,
        OperationStatus.COMPLETED,
        result={"digest_id": 91, "selection_fingerprint": resolved.fingerprint},
        resource=digest_resource,
    )
    fourth = await workflow.execute("10", _request())
    assert fourth["deferred"] is False
    assert fourth["stage"] == "completed"
    assert fourth["digest_id"] == 91
    assert len(operations.submissions) == 4
    assert resolver.resolve.call_count == 1
    operations.attach_completion.assert_awaited_once_with(
        "10",
        result=fourth,
        resource=digest_resource,
        message="Pipeline complete",
    )

    operations.handles[10] = _handle(
        10,
        OperationType.PIPELINE_RUN,
        OperationStatus.IN_PROGRESS,
        result=fourth,
    )
    repaired = await workflow.execute("10", _request())
    assert repaired == fourth
    assert operations.attach_completion.await_count == 2

    operations.handles[10] = _handle(
        10,
        OperationType.PIPELINE_RUN,
        OperationStatus.IN_PROGRESS,
        result=fourth,
        resource=digest_resource,
    )
    repeated = await workflow.execute("10", _request())
    assert repeated == fourth
    assert len(operations.submissions) == 4
    assert resolver.resolve.call_count == 1
    assert digest_loader.call_count == 3
    digest_loader.assert_called_with(91)
    assert operations.attach_completion.await_count == 3


def test_pipeline_uses_canonical_status_from_projected_operation_handle() -> None:
    payload = OperationPayloadV2(
        operation_type=OperationType.INGESTION_EXECUTE,
        input={"kind": "rss"},
        result=_ingestion_result(31),
    ).model_dump(mode="json")
    projected = OperationService.project(
        JobRecord(
            id=20,
            entrypoint=OperationType.INGESTION_EXECUTE.value,
            status=JobStatus.COMPLETED,
            payload=payload,
            created_at=START,
            completed_at=END,
        )
    )

    assert projected.status is OperationStatus.COMPLETED
    assert projected.is_terminal is True
    assert PipelineWorkflow._has_active([projected]) is False


@pytest.mark.asyncio
async def test_pipeline_rejects_corrupt_completed_projection() -> None:
    operations = FakeOperations()
    operations.handles[10] = _handle(
        10,
        OperationType.PIPELINE_RUN,
        OperationStatus.IN_PROGRESS,
        result={"stage": "completed", "digest_id": 91},
        resource=ResourceReference(
            type="theme_analysis",
            id="91",
            url="/api/v1/theme-analyses/91",
        ),
    )
    workflow = PipelineWorkflow(operation_service=operations)

    with pytest.raises(RuntimeError, match="completion projection"):
        await workflow.execute("10", _request())

    assert operations.submissions == []


@pytest.mark.asyncio
async def test_pipeline_rejects_completed_parent_when_digest_child_is_not_completed() -> None:
    operations = FakeOperations()
    policy = SelectionPolicy()
    resolved = ResolvedContentSet(
        policy=policy,
        fingerprint=compute_selection_fingerprint(policy, [], []),
    )
    digest_resource = ResourceReference(type="digest", id="91", url="/api/v1/digests/91")
    operations.handles[10] = _handle(
        10,
        OperationType.PIPELINE_RUN,
        OperationStatus.IN_PROGRESS,
        result={
            "stage": "completed",
            "digest_id": 91,
            "digest_operation_id": 20,
            "resolved_set": resolved.model_dump(mode="json"),
        },
        resource=digest_resource,
    )
    operations.handles[20] = _handle(
        20,
        OperationType.DIGEST_CREATE,
        OperationStatus.FAILED,
        resource=digest_resource,
    )
    workflow = PipelineWorkflow(operation_service=operations, digest_loader=Mock())

    with pytest.raises(RuntimeError, match="completion projection"):
        await workflow.execute("10", _request())

    workflow.digest_loader.assert_not_called()


def test_pipeline_rejects_digest_that_broadens_resolved_selection() -> None:
    policy = SelectionPolicy(source_types=(ContentSource.RSS,))
    resolved = ResolvedContentSet(
        policy=policy,
        fingerprint=compute_selection_fingerprint(policy, [], []),
    )
    broadened = SimpleNamespace(
        source_content_ids=[999],
        source_summary_ids=[1000],
        selection_fingerprint="b" * 64,
        selection_policy=policy.model_dump(mode="json"),
        newsletter_count=1,
    )

    with pytest.raises(ValueError, match="provenance"):
        PipelineWorkflow._validate_digest(broadened, resolved)


def test_pipeline_rejects_digest_owned_by_another_operation() -> None:
    digest = SimpleNamespace(operation_id=999)

    with pytest.raises(RuntimeError, match="completion projection"):
        PipelineWorkflow._validate_digest_operation(digest, 20)

    PipelineWorkflow._validate_digest_operation(SimpleNamespace(operation_id=20), "20")


def test_pipeline_restricts_resolution_to_ingestion_receipt_content_ids() -> None:
    policy = SelectionPolicy(source_types=(ContentSource.YOUTUBE,))
    items = (
        ResolvedContentItem(
            content_id=31,
            summary_id=41,
            source_type=ContentSource.YOUTUBE,
            title="Requested playlist",
            selection_date=START,
        ),
        ResolvedContentItem(
            content_id=32,
            summary_id=42,
            source_type=ContentSource.YOUTUBE,
            title="Unrequested RSS feed",
            selection_date=START,
        ),
    )
    broad = ResolvedContentSet(
        policy=policy,
        items=items,
        fingerprint=compute_selection_fingerprint(policy, [31, 32], [41, 42]),
    )

    restricted = PipelineWorkflow._restrict_resolved(broad, [31])

    assert restricted.content_ids == (31,)
    assert restricted.summary_ids == (41,)
    assert restricted.fingerprint == compute_selection_fingerprint(policy, [31], [41])


def test_pipeline_receipt_keeps_cross_source_canonical_content() -> None:
    policy = SelectionPolicy()
    canonical_item = ResolvedContentItem(
        content_id=31,
        summary_id=41,
        source_type=ContentSource.SUBSTACK,
        title="Canonical Substack item reached through RSS",
        selection_date=START,
    )
    unrelated_item = ResolvedContentItem(
        content_id=32,
        summary_id=42,
        source_type=ContentSource.RSS,
        title="Unrelated RSS item",
        selection_date=START,
    )
    broad = ResolvedContentSet(
        policy=policy,
        items=(canonical_item, unrelated_item),
        fingerprint=compute_selection_fingerprint(policy, [31, 32], [41, 42]),
    )

    restricted = PipelineWorkflow._restrict_resolved(broad, [31])

    assert restricted.content_ids == (31,)
    assert restricted.items[0].source_type is ContentSource.SUBSTACK


@pytest.mark.asyncio
async def test_pipeline_stops_after_preserving_partial_failure_when_policy_disallows_continue() -> (
    None
):
    operations = FakeOperations()
    workflow = PipelineWorkflow(
        operation_service=operations,
        registry=SOURCE_REGISTRY,
        source_config_loader=lambda: SourcesConfig(
            sources=[RSSSource(url="https://example.com/feed")]
        ),
        resolver=Mock(),
        digest_loader=Mock(),
    )
    request = _request(sources=["rss"], continue_on_error=False)
    first = await workflow.execute("10", request)
    child_id = first["source_operation_ids"][0]
    operations.handles[child_id] = _handle(
        child_id,
        OperationType.INGESTION_EXECUTE,
        OperationStatus.FAILED,
        problem=SimpleNamespace(model_dump=lambda **_: {"detail": "feed unavailable"}),
    )
    with pytest.raises(RuntimeError, match="source ingestion failed"):
        await workflow.execute("10", request)

    assert operations.attach_result.await_args.args[1]["source_results"][0]["source"] == "rss"
    assert operations.attach_result.await_args.args[1]["retry_child_operation_ids"] == [child_id]
    assert all(s[0] is not OperationType.SUMMARIZATION_RUN for s in operations.submissions)


@pytest.mark.asyncio
async def test_pipeline_fails_completed_partial_source_when_continuation_is_disabled() -> None:
    operations = FakeOperations()
    workflow = PipelineWorkflow(
        operation_service=operations,
        registry=SOURCE_REGISTRY,
        source_config_loader=lambda: SourcesConfig(
            sources=[RSSSource(url="https://example.com/feed")]
        ),
        resolver=Mock(),
        digest_loader=Mock(),
    )
    request = _request(sources=["rss"], continue_on_error=False)
    first = await workflow.execute("10", request)
    child_id = first["source_operation_ids"][0]
    operations.handles[child_id] = _handle(
        child_id,
        OperationType.INGESTION_EXECUTE,
        OperationStatus.COMPLETED,
        result=_typed_ingestion_result("partial", items_ingested=1, items_failed=1),
    )

    with pytest.raises(RuntimeError, match="continuation is disabled"):
        await workflow.execute("10", request)

    failed_checkpoint = operations.attach_result.await_args.args[1]
    assert failed_checkpoint["ingestion_summary"]["outcome"] == "failed"
    assert failed_checkpoint["ingestion_summary"]["sources"][0]["outcome"] == "partial"
    assert failed_checkpoint["retry_child_operation_ids"] == []
    assert all(s[0] is not OperationType.SUMMARIZATION_RUN for s in operations.submissions)


@pytest.mark.asyncio
async def test_pipeline_stops_when_all_sources_fail_even_if_continuation_is_enabled() -> None:
    operations = FakeOperations()
    workflow = PipelineWorkflow(
        operation_service=operations,
        registry=SOURCE_REGISTRY,
        source_config_loader=lambda: SourcesConfig(
            sources=[RSSSource(url="https://example.com/feed")]
        ),
        resolver=Mock(),
        digest_loader=Mock(),
    )
    request = _request(sources=["rss"], continue_on_error=True)
    first = await workflow.execute("10", request)
    child_id = first["source_operation_ids"][0]
    operations.handles[child_id] = _handle(
        child_id,
        OperationType.INGESTION_EXECUTE,
        OperationStatus.FAILED,
        problem=SimpleNamespace(model_dump=lambda **_: {"detail": "feed unavailable"}),
    )

    with pytest.raises(RuntimeError, match="all source ingestion operations failed"):
        await workflow.execute("10", request)

    assert operations.attach_result.await_args.args[1]["retry_child_operation_ids"] == [child_id]
    assert all(s[0] is not OperationType.SUMMARIZATION_RUN for s in operations.submissions)


@pytest.mark.asyncio
async def test_pipeline_refreshes_source_results_after_failed_child_retry() -> None:
    operations = FakeOperations()
    workflow = PipelineWorkflow(
        operation_service=operations,
        registry=SOURCE_REGISTRY,
        source_config_loader=lambda: SourcesConfig(
            sources=[RSSSource(url="https://example.com/feed")]
        ),
        resolver=Mock(),
        digest_loader=Mock(),
    )
    request = _request(sources=["rss"], continue_on_error=False)
    first = await workflow.execute("10", request)
    child_id = first["source_operation_ids"][0]
    operations.handles[child_id] = _handle(
        child_id,
        OperationType.INGESTION_EXECUTE,
        OperationStatus.FAILED,
        problem=SimpleNamespace(model_dump=lambda **_: {"detail": "temporary failure"}),
    )
    with pytest.raises(RuntimeError, match="source ingestion failed"):
        await workflow.execute("10", request)

    failed_checkpoint = operations.attach_result.await_args.args[1]
    assert failed_checkpoint["ingestion_summary"]["outcome"] == "failed"
    operations.handles[10] = _handle(
        10,
        OperationType.PIPELINE_RUN,
        OperationStatus.IN_PROGRESS,
        result=failed_checkpoint,
    )
    operations.handles[child_id] = _handle(
        child_id,
        OperationType.INGESTION_EXECUTE,
        OperationStatus.QUEUED,
    )
    deferred = await workflow.execute("10", request)
    assert deferred["stage"] == "failed"

    operations.handles[10] = _handle(
        10,
        OperationType.PIPELINE_RUN,
        OperationStatus.IN_PROGRESS,
        result=deferred,
    )
    operations.handles[child_id] = _handle(
        child_id,
        OperationType.INGESTION_EXECUTE,
        OperationStatus.COMPLETED,
        result=_ingestion_result(31),
    )
    resumed = await workflow.execute("10", request)

    assert resumed["stage"] == "summarization"
    assert resumed["source_results"][0]["status"] == "completed"
    assert resumed["ingestion_summary"]["outcome"] == "unknown"
    assert operations.submissions[-1][0] is OperationType.SUMMARIZATION_RUN
    assert operations.submissions[-1][1]["content_ids"] == [31]


@pytest.mark.asyncio
async def test_summary_retry_does_not_rerun_tolerated_failed_source() -> None:
    operations = FakeOperations()
    workflow = PipelineWorkflow(
        operation_service=operations,
        registry=SOURCE_REGISTRY,
        source_config_loader=lambda: SourcesConfig(
            sources=[
                RSSSource(url="https://example.com/feed"),
                WebSearchSource(provider="grok", prompt="agents"),
            ]
        ),
        resolver=Mock(),
        digest_loader=Mock(),
    )
    request = _request(continue_on_error=True)
    first = await workflow.execute("10", request)
    rss_id, search_id = first["source_operation_ids"]
    operations.handles[rss_id] = _handle(
        rss_id,
        OperationType.INGESTION_EXECUTE,
        OperationStatus.COMPLETED,
        result=_ingestion_result(31),
    )
    operations.handles[search_id] = _handle(
        search_id,
        OperationType.INGESTION_EXECUTE,
        OperationStatus.FAILED,
    )
    summary_checkpoint = await workflow.execute("10", request)
    summary_id = summary_checkpoint["summary_operation_id"]
    operations.handles[summary_id] = _handle(
        summary_id,
        OperationType.SUMMARIZATION_RUN,
        OperationStatus.FAILED,
    )

    with pytest.raises(RuntimeError, match="summarization failed"):
        await workflow.execute("10", request)

    failed_checkpoint = operations.attach_result.await_args.args[1]
    assert failed_checkpoint["retry_child_operation_ids"] == [summary_id]
    operations.handles[10] = _handle(
        10,
        OperationType.PIPELINE_RUN,
        OperationStatus.IN_PROGRESS,
        result=failed_checkpoint,
    )
    operations.handles[summary_id] = _handle(
        summary_id,
        OperationType.SUMMARIZATION_RUN,
        OperationStatus.QUEUED,
    )
    resumed = await workflow.execute("10", request)

    assert resumed["stage"] == "summarization"
    assert (
        len(
            [
                submission
                for submission in operations.submissions
                if submission[0] is OperationType.INGESTION_EXECUTE
            ]
        )
        == 2
    )
    assert operations.handles[search_id].status is OperationStatus.FAILED


@pytest.mark.asyncio
async def test_pipeline_recovers_partially_dispatched_immutable_source_plan() -> None:
    operations = FakeOperations()
    checkpoint = {
        "deferred": True,
        "stage": "ingestion",
        "source_commands": [
            {
                "kind": "rss",
                "configured_sources": [{"type": "rss", "url": "https://queued.example/feed"}],
                "max_items": 10,
                "days_back": 1,
                "force_reprocess": False,
            },
            {
                "kind": "x_search",
                "configured_sources": [
                    {"type": "websearch", "provider": "grok", "prompt": "agents"}
                ],
                "prompt": "agents",
                "max_threads": None,
                "force_reprocess": False,
            },
        ],
        "source_operation_ids": [20],
        "source_results": [],
    }
    operations.handles[10] = _handle(
        10,
        OperationType.PIPELINE_RUN,
        OperationStatus.IN_PROGRESS,
        result=checkpoint,
    )
    operations.handles[20] = _handle(20, OperationType.INGESTION_EXECUTE, OperationStatus.QUEUED)
    operations.next_id = 21
    workflow = PipelineWorkflow(
        operation_service=operations,
        registry=SOURCE_REGISTRY,
        source_config_loader=Mock(side_effect=AssertionError("plan must be reused")),
        resolver=Mock(),
        digest_loader=Mock(),
    )

    result = await workflow.execute("10", _request())

    assert result["source_operation_ids"] == [20, 21]
    assert len(operations.submissions) == 1
    assert operations.submissions[0][1]["kind"] == "x_search"
    assert operations.submissions[0][1]["configured_sources"][0]["prompt"] == "agents"


@pytest.mark.asyncio
async def test_pipeline_rejects_unknown_or_unscheduled_source_before_submission() -> None:
    operations = FakeOperations()
    workflow = PipelineWorkflow(
        operation_service=operations,
        registry=SOURCE_REGISTRY,
        source_config_loader=lambda: SourcesConfig(
            sources=[RSSSource(url="https://example.com/feed")]
        ),
        resolver=Mock(),
        digest_loader=Mock(),
    )
    with pytest.raises(ValueError, match="Unknown ingestion source"):
        await workflow.execute("10", _request(sources=["does_not_exist"]))
    with pytest.raises(ValueError, match="not scheduled"):
        await workflow.execute("10", _request(sources=["url"]))
    assert operations.submissions == []
