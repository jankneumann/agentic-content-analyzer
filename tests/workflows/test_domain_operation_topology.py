"""Executable coverage for the frozen domain-operation inventory."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.contracts.operation_context import OperationOutcome, OperationStage
from src.contracts.workflow_models import SummarizationRequest
from src.models.jobs import JobStatus


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
    assert await router.parse(b"document") == "parsed"

    operations = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(resource=None, result=None)),
        update_progress=AsyncMock(),
        attach_completion=AsyncMock(),
    )
    workflow = SummarizationWorkflow(
        operation_service=operations,
        child_dispatcher=AsyncMock(
            return_value={"completed_ids": [7], "failed_ids": [9]}
        ),
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
    router.get_provider_candidates = Mock(
        return_value=[Provider.ANTHROPIC, Provider.GOOGLE_VERTEX]
    )
    router._generate_for_provider = AsyncMock(
        side_effect=[
            RuntimeError("token=secret-canary"),
            LLMResponse(content="ok", model="model", input_tokens=1, output_tokens=1),
        ]
    )
    router._trace_llm_call = Mock()

    response = await router.generate("model", "system", "user")

    assert response.content == "ok"
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
    assert "secret-canary" not in repr(first_provider.fail.call_args.kwargs)


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
    assert "secret-canary" not in repr(recorder.calls[1][2].fail.call_args.kwargs)


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
    delivery.gmail_client.service.users.side_effect = RuntimeError(
        "authorization=secret-canary"
    )
    with patch("src.delivery.email.DigestFormatter.to_html", return_value="<p>safe</p>"):
        assert delivery.send_digest(SimpleNamespace(id=1, title="Digest"), "safe@example.test") is False

    assert recorder.stages() == [
        OperationStage.GRAPH,
        OperationStage.PERSIST,
        OperationStage.FETCH,
        OperationStage.DELIVER,
    ]
    recorder.calls[-1][2].fail.assert_called_once()
    assert "secret-canary" not in repr(recorder.calls[-1][2].fail.call_args.kwargs)


@pytest.mark.asyncio
async def test_pipeline_submission_and_child_aggregate_keep_parent_child_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.pipeline.runner import run_pipeline
    from src.workflows.pipeline import build_pipeline_ingestion_summary

    recorder = _StageRecorder()
    monkeypatch.setattr("src.pipeline.runner.operation_stage", recorder.stage)
    child = SimpleNamespace(
        operation_id=52,
        status=JobStatus.FAILED,
        result={"items_ingested": 1, "items_failed": 1},
        problem=None,
    )
    success = SimpleNamespace(
        operation_id=51,
        status=JobStatus.COMPLETED,
        result={"items_ingested": 2, "items_failed": 0},
        problem=None,
    )
    operations = SimpleNamespace(
        submit=AsyncMock(
            return_value=SimpleNamespace(
                operation_id=41,
                status=JobStatus.QUEUED,
                parent_operation_id=None,
            )
        )
    )

    handle = await run_pipeline(operation_service=operations)
    summary = build_pipeline_ingestion_summary([success, child])

    assert handle.operation_id == 41
    assert summary["items_ingested"] == 3
    assert summary["items_failed"] == 1
    assert summary["status"] == "partial"
    assert summary["child_operation_ids"] == [51, 52]
    assert recorder.stages() == [OperationStage.SUBMIT]
