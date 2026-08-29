from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[3]


def test_gx10_profile_declares_exact_storage_budget_and_hysteresis_policy() -> None:
    profile = yaml.safe_load((ROOT / "profiles/gx10.yaml").read_text())
    policy = profile["settings"]["gx10"]

    assert policy["component_budgets_percent"] == {
        "application_postgresql": 22,
        "neo4j": 12,
        "clickhouse": 28,
        "minio": 8,
        "backups": 15,
        "redis_and_logs": 2,
    }
    assert sum(policy["component_budgets_percent"].values()) == 87
    assert policy["reserve_percent"] == 13
    assert (
        policy["high_clear_percent"],
        policy["high_watermark_percent"],
        policy["critical_clear_percent"],
        policy["critical_watermark_percent"],
    ) == (75, 80, 85, 90)
    assert policy["hysteresis_minutes"] == 15


def test_storage_governance_has_no_direct_database_file_deletion_primitive() -> None:
    source = (ROOT / "src/services/storage_governance.py").read_text()
    tree = ast.parse(source)
    forbidden_attributes = {"remove", "unlink", "rmtree", "rmdir"}

    assert not [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in forbidden_attributes
    ]
    assert "DELETE FROM" not in source.upper()
    assert "TRUNCATE " not in source.upper()


def test_backup_controller_has_no_plaintext_fallback_or_source_delete_primitive() -> None:
    source = (ROOT / "src/services/backup/gx10.py").read_text()
    tree = ast.parse(source)
    forbidden_attributes = {"remove", "unlink", "rmtree", "rmdir"}

    assert not [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in forbidden_attributes
    ]
    assert "plaintext_fallback" not in source
    assert "DELETE FROM" not in source.upper()


@pytest.mark.parametrize(
    "module",
    [
        "src/services/storage_governance.py",
        "src/services/backup/gx10.py",
    ],
)
def test_checkpoint_surfaces_parse_without_shell_or_direct_database_mutation(
    module: str,
) -> None:
    source = (ROOT / module).read_text()
    ast.parse(source)

    assert "shell=True" not in source
    assert "DELETE FROM" not in source.upper()
    assert "TRUNCATE " not in source.upper()
    assert "PGDATA" not in source


def test_production_storage_and_backup_entrypoints_are_runnable_and_wired() -> None:
    import subprocess
    import sys

    for module in ("scripts.gx10.storage", "scripts.gx10.backup"):
        completed = subprocess.run(
            [sys.executable, "-m", module, "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr

    storage_source = (ROOT / "scripts/gx10/storage/runtime.py").read_text()
    backup_source = (ROOT / "scripts/gx10/backup/runtime.py").read_text()
    assert "StorageController" in storage_source
    assert "plan_retention" in storage_source
    assert "GX10BackupController" in backup_source
    assert "GX10RestoreDrill" in backup_source
    assert "OpenBaoAgeMaterialProvider" in backup_source


def test_storage_runtime_executes_throttle_cleanup_and_correlated_alert() -> None:
    from datetime import UTC, datetime

    from scripts.gx10.storage.runtime import StorageRuntime

    invoked: list[tuple[str, dict[str, object]]] = []
    runtime = StorageRuntime(
        invoke=lambda action, payload: invoked.append((action, payload)) or (action != "cleanup")
    )

    high = runtime.run_cycle(
        usage_percent=80,
        scheduled_ingestion_concurrency=8,
        now=datetime(2026, 8, 29, tzinfo=UTC),
        operation_id="storage-op",
        trace_id="a" * 32,
        outcome_specific_retention=False,
    )
    critical = runtime.run_cycle(
        usage_percent=90,
        scheduled_ingestion_concurrency=8,
        now=datetime(2026, 8, 29, 1, tzinfo=UTC),
        operation_id="storage-op",
        trace_id="a" * 32,
        outcome_specific_retention=False,
    )

    assert high.state == "high"
    assert high.scheduled_ingestion_concurrency == 4
    assert critical.state == "critical"
    assert any(action == "throttle" for action, _payload in invoked)
    assert any(action == "cleanup" for action, _payload in invoked)
    assert any(action == "alert" and payload["trace_id"] == "a" * 32 for action, payload in invoked)


def test_synthetic_checkpoint_records_truthful_evidence_and_native_unavailability(
    tmp_path: Path,
) -> None:
    import json

    from scripts.gx10.backup.runtime import run_synthetic_checkpoint

    output = tmp_path / "checkpoint.json"
    evidence = run_synthetic_checkpoint(output)

    assert json.loads(output.read_text()) == evidence
    assert evidence["evidence_status"] == "partial"
    assert evidence["task_8_10"]["status"] == "incomplete"
    assert evidence["checkpoint_mode"] == "synthetic"
    assert evidence["native_age_drill"]["status"] == "unavailable"
    assert evidence["native_age_drill"]["reason"] == "age_cli_absent"
    assert evidence["storage"]["states"] == ["high", "critical", "high"]
    assert evidence["storage"]["cleanup_failure"]["trace_id"]
    assert evidence["backup"]["manifest"]["outcome"] == "succeeded"
    assert len(evidence["backup"]["checksums"]) == 6
    assert evidence["restore"]["source_untouched"] is True
    assert evidence["restore"]["measured_rpo_rto"]["accepted"] is True
