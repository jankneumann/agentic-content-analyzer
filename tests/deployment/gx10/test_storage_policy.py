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


def test_storage_state_persists_hysteresis_across_runtime_instances(tmp_path: Path) -> None:
    import stat
    from datetime import UTC, datetime, timedelta

    from scripts.gx10.storage.runtime import StorageRuntime

    state_file = tmp_path / "state" / "storage.json"
    kwargs = {
        "scheduled_ingestion_concurrency": 8,
        "operation_id": "persisted-storage",
        "trace_id": "d" * 32,
        "outcome_specific_retention": False,
    }
    start = datetime(2026, 8, 29, tzinfo=UTC)

    StorageRuntime(invoke=lambda _action, _payload: True, state_file=state_file).run_cycle(
        usage_percent=80, now=start, **kwargs
    )
    before = StorageRuntime(invoke=lambda _action, _payload: True, state_file=state_file).run_cycle(
        usage_percent=75, now=start + timedelta(minutes=1), **kwargs
    )
    cleared = StorageRuntime(
        invoke=lambda _action, _payload: True, state_file=state_file
    ).run_cycle(usage_percent=75, now=start + timedelta(minutes=16), **kwargs)

    assert before.state == "high"
    assert cleared.state == "normal"
    assert stat.S_IMODE(state_file.stat().st_mode) == 0o600
    assert state_file.stat().st_size <= 4096


def test_storage_state_rejects_oversized_or_unsafe_files(tmp_path: Path) -> None:
    from scripts.gx10.storage.runtime import StorageRuntime

    state_file = tmp_path / "state.json"
    state_file.write_bytes(b"x" * 4097)
    state_file.chmod(0o600)
    with pytest.raises(ValueError, match="bounded size"):
        StorageRuntime(invoke=lambda _action, _payload: True, state_file=state_file)

    state_file.write_text('{"schema_version":1,"state":"normal","clear_since":null}')
    state_file.chmod(0o644)
    with pytest.raises(ValueError, match="permissions"):
        StorageRuntime(invoke=lambda _action, _payload: True, state_file=state_file)


def test_critical_pause_failure_emits_correlated_alert_and_cli_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import json
    import sys
    from collections import namedtuple

    from scripts.gx10.storage import runtime as storage_runtime

    invoked: list[tuple[str, dict[str, object]]] = []
    runtime = storage_runtime.StorageRuntime(
        invoke=lambda action, payload: invoked.append((action, payload)) or action != "throttle"
    )
    runtime.run_cycle(
        usage_percent=90,
        scheduled_ingestion_concurrency=8,
        now=storage_runtime.datetime(2026, 8, 29, tzinfo=storage_runtime.UTC),
        operation_id="critical-pause",
        trace_id="e" * 32,
        outcome_specific_retention=False,
    )
    assert runtime.action_failures == ("critical_pause_action_failed",)
    assert any(
        action == "alert"
        and payload["trace_id"] == "e" * 32
        and payload["diagnostic_code"] == "critical_pause_action_failed"
        for action, payload in invoked
    )

    actions = tmp_path / "actions.json"
    actions.write_text(
        json.dumps(
            {
                "throttle": [sys.executable, "-c", "raise SystemExit(7)"],
                "cleanup": [sys.executable, "-c", "raise SystemExit(0)"],
                "alert": [sys.executable, "-c", "raise SystemExit(0)"],
            }
        )
    )
    Disk = namedtuple("Disk", "total used free")
    monkeypatch.setattr(storage_runtime.shutil, "disk_usage", lambda _path: Disk(100, 90, 10))

    result = storage_runtime.main(
        [
            "--filesystem",
            str(tmp_path),
            "--concurrency",
            "8",
            "--operation-id",
            "critical-pause",
            "--trace-id",
            "e" * 32,
            "--actions",
            str(actions),
            "--state-file",
            str(tmp_path / "state.json"),
        ]
    )

    assert result != 0
    evidence = json.loads(capsys.readouterr().out)
    assert evidence["trace_id"] == "e" * 32
    assert evidence["action_failures"] == ["critical_pause_action_failed"]


def test_allowed_entrypoints_expose_bounded_monitor_and_daily_backup_schedules() -> None:
    from scripts.gx10.backup.runtime import _parser as backup_parser, run_daily_backup_schedule
    from scripts.gx10.storage.runtime import _parser as storage_parser, run_monitor_schedule

    monitor_calls: list[int] = []
    monitor_sleeps: list[float] = []
    assert (
        run_monitor_schedule(
            lambda: monitor_calls.append(1) or 0,
            interval_seconds=60,
            max_cycles=2,
            sleep=monitor_sleeps.append,
        )
        == 0
    )
    backup_calls: list[int] = []
    backup_sleeps: list[float] = []
    assert (
        run_daily_backup_schedule(
            lambda: backup_calls.append(1) or 0,
            max_runs=2,
            sleep=backup_sleeps.append,
        )
        == 0
    )

    assert monitor_calls == [1, 1]
    assert monitor_sleeps == [60]
    assert backup_calls == [1, 1]
    assert backup_sleeps == [24 * 60 * 60]
    assert "--interval-seconds" in storage_parser().format_help()
    assert "schedule" in backup_parser().format_help()


def test_storage_entrypoint_uses_only_frozen_operation_stages() -> None:
    source = (ROOT / "scripts/gx10/storage/runtime.py").read_text()

    assert 'stage="storage_governance"' not in source
    assert '"stage": "storage_governance"' not in source
    assert 'stage="cleanup"' in source


@pytest.mark.parametrize("name", ["../outside.age", "/outside.age", "nested/file.age"])
def test_restore_rejects_manifest_artifact_path_escape(tmp_path: Path, name: str) -> None:
    from scripts.gx10.backup.runtime import resolve_manifest_artifact_path

    with pytest.raises(ValueError, match="artifact name"):
        resolve_manifest_artifact_path(tmp_path, name)


def test_restore_rejects_manifest_artifact_symlink_escape(tmp_path: Path) -> None:
    from scripts.gx10.backup.runtime import resolve_manifest_artifact_path

    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    outside = tmp_path / "outside.age"
    outside.write_bytes(b"ciphertext")
    (artifacts / "linked.age").symlink_to(outside)

    with pytest.raises(ValueError, match="escapes"):
        resolve_manifest_artifact_path(artifacts, "linked.age")
