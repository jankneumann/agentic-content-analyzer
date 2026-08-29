"""Executable GX-10 smoke orchestration and runbook acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.gx10.verify_observability import main

from tests.e2e.test_operation_observability import CANARY, _snapshot


def test_fixture_smoke_writes_machine_readable_ready_report(tmp_path: Path) -> None:
    fixture = tmp_path / "evidence.json"
    output = tmp_path / "report.json"
    fixture.write_text(json.dumps(_snapshot()), encoding="utf-8")

    exit_code = main(
        [
            "--fixture",
            str(fixture),
            "--canary",
            CANARY,
            "--output",
            str(output),
        ]
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["schema_version"] == 1
    assert report["ready"] is True
    assert report["mode"] == "fixture"
    assert report["operation_id"] == "42"


def test_fixture_smoke_fails_closed_without_exported_trace(tmp_path: Path) -> None:
    fixture = tmp_path / "evidence.json"
    output = tmp_path / "report.json"
    incomplete = _snapshot()
    incomplete["observations"] = []
    fixture.write_text(json.dumps(incomplete), encoding="utf-8")

    exit_code = main(
        [
            "--fixture",
            str(fixture),
            "--canary",
            CANARY,
            "--timeout-seconds",
            "0",
            "--output",
            str(output),
        ]
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["ready"] is False
    assert "trace_arrival_timeout" in report["failure_codes"]


def test_runbook_covers_required_operator_workflows() -> None:
    runbook = Path("docs/runbooks/gx10-observability.md").read_text(encoding="utf-8")

    for heading in (
        "Trace lookup workflow",
        "Stage and error catalog",
        "Exporter troubleshooting",
        "Disk and retention policy",
        "Backup and restore",
        "Environment fencing",
        "Rollback boundaries",
        "Langfuse edition capabilities",
    ):
        assert f"## {heading}" in runbook

    assert "six-hour" in runbook.lower()
    assert "not complete" in runbook.lower()
    assert "do not activate" in runbook.lower()
