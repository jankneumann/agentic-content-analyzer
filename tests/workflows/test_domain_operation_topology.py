"""Executable coverage for the frozen domain-operation inventory."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.contracts.operation_context import (
    OperationContext,
    OperationOutcome,
    OperationStage,
    bind_operation_context,
)
from src.contracts.workflow_models import IngestionResultV2, SummarizationRequest
from src.models.jobs import OperationStatus


class _StageRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, OperationStage, Mock]] = []

    @contextmanager
    def stage(self, name: str, stage: OperationStage, **_: object):
        evidence = Mock()
        self.calls.append((name, stage, evidence))
        yield evidence

    def stages(self) -> list[OperationStage]:
        return [stage for _, stage, _ in self.calls]


@pytest.mark.asyncio
async def test_parser_and_workflow_boundaries_emit_nested_success_and_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.parsers.router import ParserRouter
    from src.workflows.summarization import SummarizationWorkflow

    recorder = _StageRecorder()
    monkeypatch.setattr("src.parsers.router.operation_stage", recorder.stage)
    monkeypatch.setattr("src.workflows.summarization.operation_stage", recorder.stage)

    router = ParserRouter.__new__(ParserRouter)
    router.default_parser = "default"
    router.parsers = {"default": SimpleNamespace(parse=AsyncMock(return_value="parsed"))}
    router._has_kreuzberg = False
    router._has_anydoc = False
    router._kreuzberg_shadow = frozenset()
    router._anydoc_shadow = frozenset()
    assert await router.parse(b"document") == "parsed"

    operations = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(resource=None, result=None)),
        update_progress=AsyncMock(),
        attach_completion=AsyncMock(),
    )
    workflow = SummarizationWorkflow(
        operation_service=operations,
        child_dispatcher=AsyncMock(return_value={"completed_ids": [7], "failed_ids": [9]}),
    )
    result = await workflow.execute("41", SummarizationRequest(content_ids=[7, 9]))

    assert result["completed_ids"] == [7]
    assert result["failed_ids"] == [9]
    assert recorder.stages() == [OperationStage.PARSE, OperationStage.MODEL]


@pytest.mark.asyncio
async def test_model_provider_fallback_emits_failed_provider_and_successful_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.config.models import Provider
    from src.services.llm_router import LLMResponse, LLMRouter

    recorder = _StageRecorder()
    monkeypatch.setattr("src.services.llm_router.operation_stage", recorder.stage)
    router = LLMRouter.__new__(LLMRouter)
    router.model_config = Mock()
    router.complexity_router = None
    router.get_provider_candidates = Mock(return_value=[Provider.ANTHROPIC, Provider.GOOGLE_VERTEX])
    router._generate_for_provider = AsyncMock(
        side_effect=[
            RuntimeError("token=secret-canary"),
            LLMResponse(text="ok", input_tokens=1, output_tokens=1),
        ]
    )
    router._trace_llm_call = Mock()

    response = await router.generate("model", "system", "user")

    assert response.text == "ok"
    assert recorder.stages() == [
        OperationStage.MODEL,
        OperationStage.MODEL,
        OperationStage.FALLBACK,
    ]
    first_provider = recorder.calls[1][2]
    first_provider.fail.assert_called_once()
    fallback = recorder.calls[2][2]
    fallback.finish.assert_called_once_with(
        OperationOutcome.SUCCEEDED,
        attributes={"model.provider": Provider.GOOGLE_VERTEX.value},
    )


def test_postgresql_and_index_boundaries_classify_commit_and_caught_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import indexing
    from src.storage import database

    recorder = _StageRecorder()
    monkeypatch.setattr("src.storage.database.operation_stage", recorder.stage)
    monkeypatch.setattr("src.services.indexing.operation_stage", recorder.stage)
    session = MagicMock()
    monkeypatch.setattr(database, "_get_session_factory", lambda: lambda: session)

    with database.get_db() as yielded:
        assert yielded is session
    session.commit.assert_called_once()

    monkeypatch.setattr(
        indexing,
        "get_settings",
        lambda: SimpleNamespace(enable_search_indexing=True),
    )
    monkeypatch.setattr(
        indexing,
        "_index_content_impl",
        Mock(side_effect=RuntimeError("password=secret-canary")),
    )
    indexing.index_content(SimpleNamespace(id=1), session)

    assert recorder.stages() == [OperationStage.PERSIST, OperationStage.INDEX]
    recorder.calls[1][2].fail.assert_called_once()


@pytest.mark.asyncio
async def test_graph_storage_and_delivery_boundaries_emit_truthful_outcomes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.delivery.email import GmailDeliveryService
    from src.services.file_storage import LocalFileStorage
    from src.storage.graphiti_client import GraphitiClient

    recorder = _StageRecorder()
    monkeypatch.setattr("src.storage.graphiti_client.operation_stage", recorder.stage)
    monkeypatch.setattr("src.services.file_storage.operation_stage", recorder.stage)
    monkeypatch.setattr("src.delivery.email.operation_stage", recorder.stage)

    graph = GraphitiClient.__new__(GraphitiClient)
    graph._create_content_episode = Mock(return_value="episode")
    graph.graphiti = SimpleNamespace(
        add_episode=AsyncMock(
            return_value=SimpleNamespace(episode=SimpleNamespace(uuid="episode-1"))
        )
    )
    content = SimpleNamespace(
        title="Title",
        publication=None,
        author=None,
        source_type=None,
        published_date=None,
        id=1,
    )
    assert await graph.add_content_summary(content, SimpleNamespace()) == "episode-1"

    storage = LocalFileStorage(base_path=tmp_path, bucket="evidence")
    stored_path = await storage.save(b"safe", "item.txt", "text/plain")
    assert await storage.get(stored_path) == b"safe"

    delivery = GmailDeliveryService.__new__(GmailDeliveryService)
    delivery.gmail_client = SimpleNamespace(service=MagicMock())
    delivery.gmail_client.service.users.side_effect = RuntimeError("authorization=secret-canary")
    with patch("src.delivery.email.DigestFormatter.to_html", return_value="<p>safe</p>"):
        assert (
            delivery.send_digest(SimpleNamespace(id=1, title="Digest"), "safe@example.test")
            is False
        )

    assert recorder.stages() == [
        OperationStage.GRAPH,
        OperationStage.PERSIST,
        OperationStage.FETCH,
        OperationStage.DELIVER,
    ]
    recorder.calls[-1][2].fail.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_submission_and_child_aggregate_keep_parent_child_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.pipeline.runner import run_pipeline
    from src.workflows.pipeline import build_pipeline_ingestion_summary

    recorder = _StageRecorder()
    monkeypatch.setattr("src.pipeline.runner.operation_stage", recorder.stage)

    def child_result(outcome: str, ingested: int, failed: int) -> dict[str, object]:
        return IngestionResultV2(
            command_key="rss",
            resolved_route="rss",
            emitted_sources=["rss"],
            status="partial" if outcome == "partial" else "ok",
            outcome=outcome,
            items_ingested=ingested,
            items_skipped=0,
            items_failed=failed,
            content_ids=list(range(1, ingested + 1)),
            errors=[],
            warnings=[],
            errors_omitted=0,
            warnings_omitted=0,
            source_outcomes=[],
            source_outcomes_omitted=0,
            details={},
            details_omitted=0,
        ).model_dump(mode="json")

    child = SimpleNamespace(
        operation_id=52,
        root_operation_id=41,
        parent_operation_id=41,
        status=OperationStatus.COMPLETED,
        result=child_result("partial", 1, 1),
        problem=None,
    )
    success = SimpleNamespace(
        operation_id=51,
        root_operation_id=41,
        parent_operation_id=41,
        status=OperationStatus.COMPLETED,
        result=child_result("success", 2, 0),
        problem=None,
    )
    operations = SimpleNamespace(
        submit=AsyncMock(
            return_value=SimpleNamespace(
                operation_id=41,
                status=OperationStatus.QUEUED,
                parent_operation_id=None,
            )
        )
    )

    handle = await run_pipeline(operation_service=operations)
    summary = build_pipeline_ingestion_summary(
        [{"kind": "rss"}, {"kind": "rss"}],
        [success, child],
        pipeline_status="completed",
    )

    assert handle.operation_id == 41
    assert summary.outcome == "partial"
    assert [source.operation_id for source in summary.sources] == ["51", "52"]
    assert [(item.root_operation_id, item.parent_operation_id) for item in [success, child]] == [
        (41, 41),
        (41, 41),
    ]
    assert recorder.stages() == [OperationStage.SUBMIT]


class _MemorySpan:
    def __init__(self, name: str, span_id: str, parent_span_id: str, attributes: dict):
        self.name = name
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.attributes = attributes
        self.events: list[dict] = []

    def add_event(self, _name: str, attributes: dict) -> None:
        self.events.append(attributes)


class _MemoryProvider:
    def __init__(self, attempt_span_id: str) -> None:
        self.attempt_span_id = attempt_span_id
        self.stack: list[_MemorySpan] = []
        self.spans: list[_MemorySpan] = []

    @contextmanager
    def start_span(self, name: str, attributes: dict | None = None):
        parent = self.stack[-1].span_id if self.stack else self.attempt_span_id
        span = _MemorySpan(name, f"{len(self.spans) + 1:016x}", parent, attributes or {})
        self.spans.append(span)
        self.stack.append(span)
        try:
            yield span
        finally:
            self.stack.pop()


def _operation_context() -> OperationContext:
    return OperationContext(
        schema_version=1,
        operation_id="41",
        root_operation_id="41",
        parent_operation_id=None,
        traceparent="00-11111111111111111111111111111111-2222222222222222-01",
        tracestate=None,
        trace_id="11111111111111111111111111111111",
        span_id="2222222222222222",
        claim_generation="0",
        attempt_number="1",
        entrypoint="pipeline.run",
        service_name="worker",
        service_instance_id="worker-1",
        environment="test",
        release_revision="revision",
        authority_fingerprint=None,
        ownership_epoch=None,
        stage="model",
        resource_kind=None,
        resource_key=None,
    )


@pytest.mark.asyncio
async def test_concrete_provider_fallback_keeps_trace_and_parent_span_topology(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.config.models import Provider
    from src.services.llm_router import LLMResponse, LLMRouter
    from src.workflows import stage_observability

    memory = _MemoryProvider("2222222222222222")
    monkeypatch.setattr(stage_observability, "get_provider", lambda: memory)
    router = LLMRouter.__new__(LLMRouter)
    router.model_config = Mock()
    router.complexity_router = None
    router.get_provider_candidates = Mock(return_value=[Provider.ANTHROPIC, Provider.GOOGLE_VERTEX])
    router._generate_for_provider = AsyncMock(
        side_effect=[
            RuntimeError("token=secret-canary"),
            LLMResponse(text="ok", input_tokens=1, output_tokens=1),
        ]
    )
    router._trace_llm_call = Mock()

    with bind_operation_context(_operation_context()):
        response = await router.generate("model", "system", "user")

    assert response.text == "ok"
    assert [span.name for span in memory.spans] == [
        "llm.generate",
        "llm.provider.anthropic",
        "llm.provider.google_vertex",
    ]
    root, failed_provider, fallback_provider = memory.spans
    assert root.parent_span_id == "2222222222222222"
    assert failed_provider.parent_span_id == root.span_id
    assert fallback_provider.parent_span_id == root.span_id
    assert {span.attributes["operation.trace_id"] for span in memory.spans} == {
        "11111111111111111111111111111111"
    }
    exported = repr([(span.attributes, span.events) for span in memory.spans])
    assert "secret-canary" not in exported
    assert "[REDACTED]" in exported
