from __future__ import annotations

import importlib
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter
from typer.testing import CliRunner

from src.cli.app import app
from src.clients.workflow_api_client import (
    IngestionHistoryTraversal,
    OperationTraversal,
    ProblemError,
)
from src.contracts.workflow_models import (
    COMMAND_FIELD_SCHEMAS,
    CapabilityDocument,
    ConfiguredSourcePage,
    IngestCommand,
    IngestionHistoryItem,
    IngestionHistoryPage,
    OperationHandle,
    OperationPage,
    OperationSummary,
    Problem,
    UploadReference,
)


def _handle(operation_type: str = "ingestion.execute", status: str = "queued") -> OperationHandle:
    return OperationHandle(
        operation_id="op-1",
        operation_type=operation_type,
        status=status,
        progress=0,
        message=status,
        cancellable=True,
        retry_count=0,
        status_url="/api/v1/operations/op-1",
        events_url="/api/v1/operations/op-1/events",
        created_at=datetime.now(UTC),
    )


def _pipeline_handle(outcome: str, *, status: str = "completed") -> OperationHandle:
    handle = _handle("pipeline.run", status)
    handle.result = {
        "schema_version": 2,
        "ingestion_summary": {
            "outcome": outcome,
            "sources": [],
            "sources_omitted": 0,
        },
    }
    return handle


def _summary() -> OperationSummary:
    return OperationSummary.model_validate(
        _handle().model_dump(mode="json", exclude={"resource", "result", "problem"})
    )


def _history_item() -> IngestionHistoryItem:
    return IngestionHistoryItem(
        operation_id="17",
        parent_operation_id="91",
        command_key="rss",
        operation_status="completed",
        outcome="partial",
        items_ingested=3,
        items_skipped=1,
        items_failed=2,
        source_outcomes=[],
        retry_count=0,
        problem_code="source_partial",
        status_url="/api/v1/operations/17",
        created_at=datetime(2026, 7, 13, 10, tzinfo=UTC),
        completed_at=datetime(2026, 7, 13, 10, 1, tzinfo=UTC),
    )


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, str | None]] = []
        self.uploads: list[Path] = []
        self.wait_result: OperationHandle | None = None
        self.operation_pages_requested: int | None = None
        self.operation_statuses: list[str | None] = []
        self.history_calls: list[dict[str, Any]] = []
        self.history_pages_requested: int | None = None

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def upload(self, path: Path) -> UploadReference:
        self.uploads.append(path)
        return UploadReference(
            id=f"upload-{len(self.uploads)}",
            filename=path.name,
            media_type="text/plain",
            size_bytes=1,
        )

    def submit_ingestion(
        self, payload: dict[str, Any], *, idempotency_key: str | None = None
    ) -> OperationHandle:
        self.calls.append(("ingestion.execute", payload.copy(), idempotency_key))
        return _handle()

    def __getattr__(self, name: str) -> Any:
        operation_types = {
            "submit_summarization": "summarization.run",
            "submit_theme_analysis": "theme_analysis.create",
            "submit_digest": "digest.create",
            "submit_pipeline": "pipeline.run",
            "submit_podcast_script": "podcast_script.create",
            "submit_podcast_audio": "podcast_audio.create",
            "submit_audio_digest": "audio_digest.create",
        }
        if name in operation_types:

            def submit(
                payload: dict[str, Any], *, idempotency_key: str | None = None
            ) -> OperationHandle:
                operation_type = operation_types[name]
                self.calls.append((operation_type, payload.copy(), idempotency_key))
                return _handle(operation_type)

            return submit
        raise AttributeError(name)

    def wait_operation(self, operation_id: str, *, timeout_seconds: float = 300) -> OperationHandle:
        if self.wait_result is not None:
            return self.wait_result
        operation_type = self.calls[-1][0] if self.calls else "ingestion.execute"
        return _handle(operation_type, "completed")

    def get_capabilities(self, **_: Any) -> CapabilityDocument:
        return CapabilityDocument(
            contract_version="v1",
            source_commands=[],
            operation_types=[],
            resource_types=[],
        )

    def list_configured_sources(self, **_: Any) -> ConfiguredSourcePage:
        return ConfiguredSourcePage(data=[], next_cursor="next")

    def list_operations(self, **kwargs: Any) -> OperationPage:
        self.operation_statuses.append(kwargs.get("status"))
        return OperationPage(data=[_summary()], next_cursor="next")

    def collect_operations(self, **kwargs: Any) -> OperationTraversal:
        self.operation_pages_requested = kwargs["max_pages"]
        self.operation_statuses.append(kwargs.get("status"))
        return OperationTraversal(data=[_summary()], next_cursor="continue-here", truncated=True)

    def list_ingestion_history(self, **kwargs: Any) -> IngestionHistoryPage:
        self.history_calls.append(kwargs)
        return IngestionHistoryPage(data=[_history_item()], next_cursor="history-next")

    def collect_ingestion_history(self, **kwargs: Any) -> IngestionHistoryTraversal:
        self.history_calls.append(kwargs)
        self.history_pages_requested = kwargs["max_pages"]
        return IngestionHistoryTraversal(
            data=[_history_item()],
            next_cursor="history-continue",
            truncated=True,
        )

    def get_operation(self, operation_id: str) -> OperationHandle:
        return _handle()

    def retry_operation(self, operation_id: str) -> OperationHandle:
        return _handle(status="queued")

    def cancel_operation(self, operation_id: str) -> OperationHandle:
        return _handle(status="cancelled")


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch) -> tuple[CliRunner, FakeClient]:
    client = FakeClient()
    app_module = importlib.import_module("src.cli.app")
    monkeypatch.setattr(app_module, "default_client_factory", lambda: client)
    return CliRunner(), client


def test_ingestion_command_names_are_registry_derived(cli: tuple[CliRunner, FakeClient]) -> None:
    runner, _ = cli
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0
    for key in COMMAND_FIELD_SCHEMAS:
        assert key.replace("_", "-") in result.output
    assert "youtube " not in result.output
    assert "xsearch" not in result.output


def test_capabilities_supports_documented_command_local_json(
    cli: tuple[CliRunner, FakeClient],
) -> None:
    runner, _ = cli
    result = runner.invoke(app, ["capabilities", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["contract_version"] == "v1"


def test_configured_sources_supports_documented_command_local_json(
    cli: tuple[CliRunner, FakeClient],
) -> None:
    runner, _ = cli
    result = runner.invoke(app, ["configured-sources", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"data": [], "next_cursor": "next"}
    assert result.stdout.count("\n") == 1
    assert result.stderr == ""


def test_empty_graph_json_stdout_is_exactly_one_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapters = importlib.import_module("src.cli.adapters")
    graph_commands = importlib.import_module("src.cli.graph_commands")
    monkeypatch.setattr(adapters, "search_graph_sync", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(graph_commands, "is_remote_backend", lambda: False)
    monkeypatch.setattr(graph_commands, "guard_remote_backend", lambda *_args, **_kwargs: None)

    result = CliRunner().invoke(app, ["--json", "graph", "query", "--query", "missing"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"results": [], "total": 0, "query": "missing"}
    assert result.stdout.count("\n") == 1
    assert result.stderr == ""


def test_failed_graph_json_stdout_is_exactly_one_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapters = importlib.import_module("src.cli.adapters")
    graph_commands = importlib.import_module("src.cli.graph_commands")
    monkeypatch.setattr(
        adapters,
        "search_graph_sync",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("offline")),
    )
    monkeypatch.setattr(graph_commands, "is_remote_backend", lambda: False)
    monkeypatch.setattr(graph_commands, "guard_remote_backend", lambda *_args, **_kwargs: None)

    result = CliRunner().invoke(app, ["--json", "graph", "query", "--query", "missing"])

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "error": "Graph database is unavailable: offline",
        "success": False,
    }
    assert result.stdout.count("\n") == 1
    assert "Graph database is unavailable: offline" in result.stderr


def test_cli_logging_handler_routes_diagnostics_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured: dict[str, Any] = {}
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: configured.update(kwargs))

    from src.utils.logging import setup_logging

    setup_logging()

    handler = configured["handlers"][0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stderr


def test_ingestion_uses_underscore_discriminator_and_idempotency(
    cli: tuple[CliRunner, FakeClient],
) -> None:
    runner, client = cli
    result = runner.invoke(
        app,
        [
            "--json",
            "ingest",
            "x-search",
            "--prompt",
            "agents",
            "--max-threads",
            "3",
            "--idempotency-key",
            "stable-key",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["operation_type"] == "ingestion.execute"
    assert client.calls == [
        (
            "ingestion.execute",
            {"kind": "x_search", "prompt": "agents", "max_threads": 3},
            "stable-key",
        )
    ]
    assert result.stderr == ""


def test_direct_flag_does_not_bypass_durable_submission(
    cli: tuple[CliRunner, FakeClient],
) -> None:
    runner, client = cli
    result = runner.invoke(app, ["--direct", "ingest", "rss"])
    assert result.exit_code == 0
    assert client.calls == [("ingestion.execute", {"kind": "rss"}, None)]


def test_files_upload_every_path_before_submission(
    cli: tuple[CliRunner, FakeClient], tmp_path: Path
) -> None:
    runner, client = cli
    first = tmp_path / "one.txt"
    second = tmp_path / "two.txt"
    first.write_text("1")
    second.write_text("2")
    result = runner.invoke(app, ["ingest", "files", str(first), str(second)])
    assert result.exit_code == 0, result.output
    assert client.uploads == [first, second]
    assert client.calls[0][1] == {"kind": "files", "upload_ids": ["upload-1", "upload-2"]}


@pytest.mark.parametrize(
    ("args", "operation_type"),
    [
        (["summarize", "run"], "summarization.run"),
        (["theme", "create"], "theme_analysis.create"),
        (
            [
                "digest",
                "create",
                "--type",
                "daily",
                "--period-start",
                "2026-07-15T00:00:00Z",
                "--period-end",
                "2026-07-16T00:00:00Z",
            ],
            "digest.create",
        ),
        (
            [
                "pipeline",
                "run",
                "--period",
                "daily",
                "--period-start",
                "2026-07-15T00:00:00Z",
                "--period-end",
                "2026-07-16T00:00:00Z",
            ],
            "pipeline.run",
        ),
        (["podcast-script", "create", "--digest-id", "1"], "podcast_script.create"),
        (["podcast-audio", "create", "--script-id", "1"], "podcast_audio.create"),
        (["audio-digest", "create", "--digest-id", "1"], "audio_digest.create"),
    ],
)
def test_every_workflow_submits_an_operation(
    cli: tuple[CliRunner, FakeClient], args: list[str], operation_type: str
) -> None:
    runner, client = cli
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert client.calls[-1][0] == operation_type


def test_wait_progress_is_stderr_and_json_stdout_is_exact(
    cli: tuple[CliRunner, FakeClient],
) -> None:
    runner, _ = cli
    result = runner.invoke(app, ["--json", "summarize", "run", "--wait", "--timeout", "0"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["status"] == "completed"
    assert result.stderr == ""


def test_tolerated_partial_pipeline_wait_warns_without_corrupting_json(
    cli: tuple[CliRunner, FakeClient],
) -> None:
    runner, client = cli
    client.wait_result = _pipeline_handle("partial")

    result = runner.invoke(
        app,
        [
            "--json",
            "pipeline",
            "run",
            "--period",
            "daily",
            "--period-start",
            "2026-07-15T00:00:00Z",
            "--period-end",
            "2026-07-16T00:00:00Z",
            "--wait",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["result"]["ingestion_summary"]["outcome"] == "partial"
    assert result.stdout.count("\n") == 1
    assert result.stderr == "Warning: pipeline ingestion completed with partial source results.\n"


def test_zero_item_pipeline_wait_prints_informational_human_summary(
    cli: tuple[CliRunner, FakeClient],
) -> None:
    runner, client = cli
    client.wait_result = _pipeline_handle("zero_items")

    result = runner.invoke(
        app,
        [
            "pipeline",
            "run",
            "--period",
            "daily",
            "--period-start",
            "2026-07-15T00:00:00Z",
            "--period-end",
            "2026-07-16T00:00:00Z",
            "--wait",
        ],
    )

    assert result.exit_code == 0
    assert "Pipeline ingestion completed with zero items." in result.stdout


def test_fail_on_source_error_pipeline_wait_keeps_nonzero_exit(
    cli: tuple[CliRunner, FakeClient],
) -> None:
    runner, client = cli
    client.wait_result = _pipeline_handle("failed", status="failed")

    result = runner.invoke(
        app,
        [
            "pipeline",
            "run",
            "--period",
            "daily",
            "--period-start",
            "2026-07-15T00:00:00Z",
            "--period-end",
            "2026-07-16T00:00:00Z",
            "--fail-on-source-error",
            "--wait",
        ],
    )

    assert result.exit_code == 1
    assert client.calls[-1][1]["continue_on_source_error"] is False


@pytest.mark.parametrize(
    "args",
    [
        ["operations", "list"],
        ["operations", "list", "--all"],
        ["operations", "get", "op-1"],
        ["operations", "wait", "op-1", "--timeout", "0"],
        ["operations", "retry", "op-1"],
        ["operations", "cancel", "op-1"],
    ],
)
def test_operation_controls_emit_structured_json(
    cli: tuple[CliRunner, FakeClient], args: list[str]
) -> None:
    runner, _ = cli
    result = runner.invoke(app, ["--json", *args])
    assert result.exit_code == 0
    assert json.loads(result.stdout)


def test_operations_all_is_bounded_and_json_signals_truncation(
    cli: tuple[CliRunner, FakeClient],
) -> None:
    runner, client = cli

    result = runner.invoke(app, ["--json", "operations", "list", "--all", "--max-pages", "3"])

    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert document["next_cursor"] == "continue-here"
    assert document["truncated"] is True
    assert [item["operation_id"] for item in document["data"]] == ["op-1"]
    assert {"result", "resource", "problem"}.isdisjoint(document["data"][0])
    assert client.operation_pages_requested == 3
    assert result.stderr == ""


def test_operations_all_human_output_warns_with_continuation_cursor(
    cli: tuple[CliRunner, FakeClient],
) -> None:
    runner, _ = cli

    result = runner.invoke(app, ["operations", "list", "--all", "--max-pages", "2"])

    assert result.exit_code == 0, result.output
    assert "continue-here" in result.stderr
    assert "truncated" in result.stderr.lower()


@pytest.mark.parametrize("all_args", [[], ["--all", "--max-pages", "2"]])
def test_operations_list_forwards_status_filter(
    cli: tuple[CliRunner, FakeClient], all_args: list[str]
) -> None:
    runner, client = cli

    result = runner.invoke(
        app, ["--json", "operations", "list", "--status", "in_progress", *all_args]
    )

    assert result.exit_code == 0, result.output
    assert client.operation_statuses == ["in_progress"]


def test_ingest_history_forwards_every_backend_filter(
    cli: tuple[CliRunner, FakeClient],
) -> None:
    runner, client = cli

    result = runner.invoke(
        app,
        [
            "--json",
            "ingest",
            "history",
            "--command-key",
            "rss",
            "--configured-source-key",
            "src_0123456789abcdefabcd",
            "--outcome",
            "partial",
            "--status",
            "completed",
            "--parent-operation-id",
            "91",
            "--created-after",
            "2026-07-13T04:00:00Z",
            "--created-before",
            "2026-07-14T04:00:00+00:00",
            "--limit",
            "25",
            "--cursor",
            "opaque-cursor",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["data"][0]["operation_id"] == "17"
    assert client.history_calls == [
        {
            "command_key": "rss",
            "configured_source_key": "src_0123456789abcdefabcd",
            "outcome": "partial",
            "status": "completed",
            "parent_operation_id": "91",
            "created_after": datetime(2026, 7, 13, 4, tzinfo=UTC),
            "created_before": datetime(2026, 7, 14, 4, tzinfo=UTC),
            "limit": 25,
            "cursor": "opaque-cursor",
        }
    ]


def test_ingest_history_all_uses_default_budget_and_emits_one_json_document(
    cli: tuple[CliRunner, FakeClient],
) -> None:
    runner, client = cli

    result = runner.invoke(
        app,
        [
            "--json",
            "ingest",
            "history",
            "--configured-source-key",
            "src_0123456789abcdefabcd",
            "--all",
        ],
    )

    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert set(document) == {"data", "next_cursor", "truncated"}
    assert document["data"][0]["operation_id"] == "17"
    assert document["next_cursor"] == "history-continue"
    assert document["truncated"] is True
    assert client.history_pages_requested == 20
    assert client.history_calls[0]["configured_source_key"] == "src_0123456789abcdefabcd"
    assert result.stderr == ""


def test_ingest_history_human_output_is_bounded_and_warns_with_continuation(
    cli: tuple[CliRunner, FakeClient],
) -> None:
    runner, client = cli

    result = runner.invoke(app, ["ingest", "history", "--all", "--max-pages", "2"])

    assert result.exit_code == 0, result.output
    assert "rss" in result.stdout
    assert "completed" in result.stdout
    assert "partial" in result.stdout
    assert len(result.stdout) < 2_000
    assert "history-continue" in result.stderr
    assert "truncated" in result.stderr.lower()
    assert client.history_pages_requested == 2


def test_cli_problem_translation_preserves_full_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = Problem(
        type="https://aca.test/problems/validation",
        title="Invalid command",
        status=422,
        detail="prompt is required",
        code="validation_error",
        errors=[{"field": "prompt"}],
    )

    class ErrorClient(FakeClient):
        def submit_ingestion(self, *_: Any, **__: Any) -> OperationHandle:
            raise ProblemError(problem)

    app_module = importlib.import_module("src.cli.app")
    monkeypatch.setattr(app_module, "default_client_factory", ErrorClient)
    result = CliRunner().invoke(app, ["--json", "ingest", "gmail"])
    assert result.exit_code == 1
    assert json.loads(result.stdout) == problem.model_dump(mode="json", exclude_none=True)
    assert result.stderr == ""


def test_local_validation_error_is_a_json_problem(monkeypatch: pytest.MonkeyPatch) -> None:
    class ValidatingClient(FakeClient):
        def submit_ingestion(
            self, payload: dict[str, Any], *, idempotency_key: str | None = None
        ) -> OperationHandle:
            command = TypeAdapter(IngestCommand).validate_python(payload)
            return super().submit_ingestion(
                command.model_dump(mode="json", exclude_none=True),
                idempotency_key=idempotency_key,
            )

    app_module = importlib.import_module("src.cli.app")
    monkeypatch.setattr(app_module, "default_client_factory", ValidatingClient)
    result = CliRunner().invoke(
        app,
        ["--json", "ingest", "x-search", "--prompt", "agents", "--max-threads", "0"],
    )

    assert result.exit_code == 2
    problem = json.loads(result.stdout)
    assert problem["code"] == "validation_error"
    assert problem["errors"] == [
        {
            "path": ["x_search", "max_threads"],
            "code": "greater_than_equal",
            "message": "Input should be greater than or equal to 1",
        }
    ]
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("alias", "replacement"),
    [
        (["create-digest"], "digest create"),
        (["podcast"], "podcast-script create"),
        (["jobs"], "operations"),
        (["analyze"], "theme create"),
    ],
)
def test_removed_legacy_aliases_are_unknown_with_replacement_guidance(
    cli: tuple[CliRunner, FakeClient], alias: list[str], replacement: str
) -> None:
    runner, _ = cli
    result = runner.invoke(app, alias)
    assert result.exit_code != 0
    assert "No such command" in result.output
    assert replacement in result.output
