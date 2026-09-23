"""`aca telemetry prune-traces` is how the scheduled pruner gets exercised.

A daily tick is not something you can test in production without waiting a day,
so the same code is reachable by hand. Deletion is irreversible and clears
ClickHouse rows together with their object-storage blobs, so the command counts
by default and only deletes when asked.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import Any

import pytest
from typer.testing import CliRunner

from src.cli.telemetry_commands import app

runner = CliRunner()


class _Settings:
    langfuse_public_key = "pk-lf-test"
    langfuse_secret_key = "sk-lf-test"
    langfuse_base_url = "http://langfuse-web:3000"
    langfuse_trace_retention_days = 30
    langfuse_trace_retention_batch_size = 50
    langfuse_trace_retention_max_deletes_per_run = 1000


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Record the arguments the command hands the pruner."""
    seen: dict[str, Any] = {}

    # `src.config.__init__` binds a Settings INSTANCE named `settings`, which
    # shadows the submodule for attribute lookup, so the dotted-string form of
    # setattr resolves to the instance and fails. Reach the real module object.
    monkeypatch.setattr(sys.modules["src.config.settings"], "get_settings", lambda: _Settings())

    class _Client:
        def __init__(self, **kwargs: Any) -> None:
            seen["client_kwargs"] = kwargs

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

    async def _prune(client: Any, **kwargs: Any) -> Any:
        seen.update(kwargs)

        from src.services.langfuse_retention import LangfuseRetentionResult

        return LangfuseRetentionResult(
            deleted_count=7,
            batch_count=2,
            cutoff=datetime(2026, 8, 23, tzinfo=UTC),
            capped=False,
            dry_run=kwargs.get("dry_run", False),
        )

    monkeypatch.setattr("src.services.langfuse_retention.LangfuseRetentionClient", _Client)
    monkeypatch.setattr("src.services.langfuse_retention.prune_expired_traces", _prune)
    return seen


def test_it_counts_without_deleting_by_default(captured: dict[str, Any]) -> None:
    """The destructive direction is the one you have to ask for."""
    result = runner.invoke(app, [])

    assert result.exit_code == 0, result.output
    assert captured["dry_run"] is True
    assert "Would delete 7 traces" in result.output


def test_apply_actually_deletes(captured: dict[str, Any]) -> None:
    result = runner.invoke(app, ["--apply"])

    assert result.exit_code == 0, result.output
    assert captured["dry_run"] is False
    assert "Deleted 7 traces" in result.output


def test_the_window_defaults_to_the_configured_retention(captured: dict[str, Any]) -> None:
    runner.invoke(app, [])

    assert captured["retention_days"] == 30
    assert captured["batch_size"] == 50
    assert captured["max_deletes"] == 1000


def test_flags_override_the_configured_window(captured: dict[str, Any]) -> None:
    """A one-off aggressive prune must not need a profile edit."""
    runner.invoke(
        app,
        ["--older-than-days", "1", "--batch-size", "10", "--max-deletes", "5"],
    )

    assert captured["retention_days"] == 1
    assert captured["batch_size"] == 10
    assert captured["max_deletes"] == 5


def test_missing_credentials_fail_rather_than_report_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'0 traces' and 'I could not ask' must not look the same."""

    class _NoKeys(_Settings):
        langfuse_secret_key = None

    monkeypatch.setattr(sys.modules["src.config.settings"], "get_settings", lambda: _NoKeys())

    result = runner.invoke(app, [])

    assert result.exit_code == 1
    assert "credentials are not configured" in result.output


def test_json_mode_emits_one_document(captured: dict[str, Any]) -> None:
    """The CLI JSON contract: exactly one document on stdout."""
    from src.cli.output import _set_json_mode

    _set_json_mode(True)
    try:
        result = runner.invoke(app, [])
    finally:
        _set_json_mode(False)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["applied"] is False
    assert payload["trace_count"] == 7
    assert payload["retention_days"] == 30


def test_the_command_is_reachable_as_aca_telemetry_prune_traces() -> None:
    """A command nothing can invoke is the same as no command at all."""
    import typer

    from src.cli.app import app as root

    group = typer.main.get_command(root).commands["telemetry"]
    assert "prune-traces" in group.commands
