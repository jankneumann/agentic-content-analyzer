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
from src.clients.workflow_api_client import ProblemError
from src.contracts.workflow_models import (
    COMMAND_FIELD_SCHEMAS,
    CapabilityDocument,
    ConfiguredSourcePage,
    IngestCommand,
    OperationHandle,
    OperationPage,
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


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, str | None]] = []
        self.uploads: list[Path] = []

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

    def list_operations(self, **_: Any) -> OperationPage:
        return OperationPage(data=[_handle()], next_cursor="next")

    def iter_operations(self, **_: Any):
        yield _handle()

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
