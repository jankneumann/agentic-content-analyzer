from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[3]
DEPLOY = ROOT / "deploy/gx10"


def test_backup_approle_policy_is_path_scoped_and_not_shared_with_app_roles() -> None:
    policy = (DEPLOY / "openbao/aca-gx10-backup.hcl").read_text()
    provision = (DEPLOY / "openbao/provision-first-install.sh").read_text()

    assert 'path "secret/data/newsletter/gx10/backup"' in policy
    assert 'capabilities = ["read"]' in policy
    assert "newsletter/gx10/runtime" not in policy
    assert "newsletter/gx10/operator" not in policy
    assert "aca-gx10-backup" in provision
    assert "backup_age_recipient" in provision
    assert "backup_age_retained_recipients" in provision
    assert "backup_age_identities" in provision


def test_backup_renderer_uses_dedicated_approle_and_only_protected_role_files() -> None:
    bootstrap = (DEPLOY / "openbao/bootstrap-backup-approle.sh").read_text()
    login = (DEPLOY / "openbao/login-backup-approle.sh").read_text()
    renderer = (DEPLOY / "openbao/render-backup-secrets.sh").read_text()

    assert "aca-gx10-backup/role-id" in bootstrap
    assert "backup-openbao-role-id" in bootstrap
    assert "backup-openbao-secret-id" in bootstrap
    assert "backup-openbao-token" in login
    assert "secret/newsletter/gx10/backup" in renderer
    assert "backup-age.json" in renderer
    assert "restore-age.json" in renderer
    assert "install -m 0600" in renderer
    assert "common.env" not in renderer
    assert "worker.env" not in renderer


def test_age_material_file_fails_closed_for_missing_invalid_or_unavailable_rotation(
    tmp_path: Path,
) -> None:
    from scripts.gx10.backup.runtime import age_adapter_from_material_file

    with pytest.raises((ValueError, OSError)):
        age_adapter_from_material_file(tmp_path / "missing.json", require_identities=False)

    material = tmp_path / "age.json"
    material.write_text(json.dumps({"active_recipient": "not-age"}))
    material.chmod(0o600)
    with pytest.raises(ValueError):
        age_adapter_from_material_file(material, require_identities=False)

    active = "age1" + "a" * 58
    retained = "age1" + "b" * 58
    material.write_text(
        json.dumps(
            {
                "active_recipient": active,
                "retained_recipients": [retained],
                "identities": {},
            }
        )
    )
    with pytest.raises(ValueError, match="identity"):
        age_adapter_from_material_file(material, require_identities=True)


def test_backup_and_restore_cli_require_explicit_material_files() -> None:
    from scripts.gx10.backup.runtime import _parser

    parser = _parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "backup",
                "--plan",
                "plan.json",
                "--output",
                "out",
                "--operation-id",
                "op",
                "--trace-id",
                "a" * 32,
                "--quota-bytes",
                "1",
            ]
        )
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "restore",
                "--plan",
                "plan.json",
                "--manifest",
                "manifest.json",
                "--artifacts",
                "artifacts",
                "--isolated-root",
                "restore",
                "--operation-id",
                "op",
                "--trace-id",
                "a" * 32,
            ]
        )


@pytest.mark.parametrize(
    "unit",
    [
        "aca-gx10-storage.service",
        "aca-gx10-backup.service",
        "aca-gx10-restore-drill.service",
    ],
)
def test_storage_services_fail_closed_and_are_hardened(unit: str) -> None:
    source = (DEPLOY / "systemd" / unit).read_text()

    assert "OnFailure=aca-gx10-maintenance-alert@%n.service" in source
    assert "TimeoutStartSec=" in source
    assert "NoNewPrivileges=yes" in source
    assert "ProtectSystem=strict" in source
    assert "PrivateTmp=yes" in source
    assert "UMask=0077" in source
    assert "SuccessExitStatus" not in source


def test_storage_backup_and_restore_timers_preserve_recovery_objectives() -> None:
    storage = (DEPLOY / "systemd/aca-gx10-storage.timer").read_text()
    backup = (DEPLOY / "systemd/aca-gx10-backup.timer").read_text()
    restore = (DEPLOY / "systemd/aca-gx10-restore-drill.timer").read_text()

    assert "OnUnitActiveSec=60s" in storage
    assert "OnCalendar=*-*-* 03:00:00 UTC" in backup
    assert "Persistent=true" in backup
    assert "RandomizedDelaySec=" in backup
    assert "OnCalendar=weekly" in restore
    assert "Persistent=true" in restore


def test_services_use_persistent_state_evidence_and_safe_dependency_order() -> None:
    storage = (DEPLOY / "systemd/aca-gx10-storage.service").read_text()
    backup = (DEPLOY / "systemd/aca-gx10-backup.service").read_text()
    restore = (DEPLOY / "systemd/aca-gx10-restore-drill.service").read_text()

    assert "--state-file /var/lib/aca/gx10/storage-controller.json" in storage
    assert "--max-cycles 1" in storage
    assert "aca-gx10.service" in storage
    assert "--age-material-file /run/aca/gx10/backup/backup-age.json" in backup
    assert "/var/lib/aca/gx10/backups" in backup
    assert "--age-material-file /run/aca/gx10/backup/restore-age.json" in restore
    assert "/var/lib/aca/gx10/restore-evidence" in restore
    assert "aca-gx10-backup-secrets.service" in backup
    assert "aca-gx10-backup-secrets.service" in restore


def test_new_openbao_scripts_are_bash_syntax_clean() -> None:
    scripts = [
        DEPLOY / "openbao/bootstrap-backup-approle.sh",
        DEPLOY / "openbao/login-backup-approle.sh",
        DEPLOY / "openbao/render-backup-secrets.sh",
    ]
    for script in scripts:
        completed = subprocess.run(["/usr/bin/bash", "-n", script], capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr


def test_backup_renderer_writes_separated_mode_0600_material(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    backup_runtime = runtime / "backup"
    backup_runtime.mkdir(parents=True)
    (backup_runtime / "backup-openbao-token").write_text("token")
    tools = tmp_path / "bin"
    tools.mkdir()
    active = "age1" + "a" * 58
    retained = "age1" + "b" * 58
    response = {
        "data": {
            "data": {
                "backup_age_recipient": active,
                "backup_age_retained_recipients": [retained],
                "backup_age_identities": {
                    active: "AGE-SECRET-KEY-ACTIVE",
                    retained: "AGE-SECRET-KEY-RETAINED",
                },
            }
        }
    }
    curl = tools / "curl"
    curl.write_text("#!/usr/bin/env bash\nprintf '%s\\n' '" + json.dumps(response) + "'\n")
    curl.chmod(0o700)

    result = subprocess.run(
        [DEPLOY / "openbao/render-backup-secrets.sh"],
        env=os.environ
        | {
            "PATH": f"{tools}:{os.environ['PATH']}",
            "GX10_RUNTIME_DIR": str(runtime),
            "GX10_BAO_ADDR": "http://openbao.test/v1",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    backup = backup_runtime / "backup-age.json"
    restore = backup_runtime / "restore-age.json"
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert stat.S_IMODE(restore.stat().st_mode) == 0o600
    assert json.loads(backup.read_text())["identities"] == {}
    assert set(json.loads(restore.read_text())["identities"]) == {active, retained}
    assert not (runtime / "common.env").exists()
    assert not (runtime / "worker.env").exists()


def test_scheduled_units_never_hardcode_operation_or_trace_identity() -> None:
    for unit in (
        "aca-gx10-storage.service",
        "aca-gx10-backup.service",
        "aca-gx10-restore-drill.service",
    ):
        source = (DEPLOY / "systemd" / unit).read_text()
        assert "--operation-id" not in source
        assert "--trace-id" not in source
        assert "00000000000000000000000000000000" not in source


def test_scheduled_entrypoints_derive_one_identity_from_durable_roots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.gx10.backup import runtime as backup_runtime
    from scripts.gx10.storage import runtime as storage_runtime

    context = SimpleNamespace(operation_id="701", trace_id="a" * 32)
    monkeypatch.setattr(storage_runtime, "get_current_operation_context", lambda: context)
    monkeypatch.setattr(backup_runtime, "get_current_operation_context", lambda: context)

    assert storage_runtime._runtime_identity(None, None) == ("701", "a" * 32)
    assert backup_runtime._maintenance_correlation(
        None, None
    ) == backup_runtime.MaintenanceCorrelation(
        operation_id="701",
        trace_id="a" * 32,
    )
    assert storage_runtime._scheduled_monitor.__aca_operational_entrypoint__ == (
        "gx10.storage.monitor",
        "cleanup",
        "aca-gx10-storage",
    )
    assert backup_runtime._scheduled_backup.__aca_operational_entrypoint__[1] == "backup"
    assert backup_runtime._scheduled_restore.__aca_operational_entrypoint__[1] == "restore"


def test_reviewed_maintenance_plans_are_complete_and_absolute() -> None:
    maintenance = DEPLOY / "maintenance"
    storage = json.loads((maintenance / "storage-actions.json").read_text())
    backup = json.loads((maintenance / "backup-plan.json").read_text())
    restore = json.loads((maintenance / "restore-plan.json").read_text())
    components = {
        "application_postgresql",
        "neo4j",
        "langfuse_postgresql",
        "clickhouse",
        "minio",
        "configuration_metadata",
    }

    assert set(storage) == {"throttle", "cleanup", "alert"}
    assert set(backup) == {"producers"}
    assert set(backup["producers"]) == components
    assert set(restore) == {"restore", "validate", "production_sources", "metadata_probe"}
    assert set(restore["restore"]) == components
    assert set(restore["validate"]) == components
    assert set(restore["production_sources"]) == components
    assert set(restore["metadata_probe"]) == {
        "application_operation_rows",
        "langfuse_trace_metadata",
    }
    for inventory in (storage, backup["producers"], restore["restore"], restore["validate"]):
        for argv in inventory.values():
            assert argv and Path(argv[0]).is_absolute()
    assert set(restore["production_sources"].values()) == {
        "/srv/aca/postgres",
        "/srv/aca/neo4j",
        "/srv/aca/langfuse-postgres",
        "/srv/aca/clickhouse",
        "/srv/aca/minio",
        "/opt/aca/deploy/gx10",
    }


def test_maintenance_plan_installer_is_idempotent_and_protects_files(tmp_path: Path) -> None:
    installer = DEPLOY / "install-maintenance-plans.sh"
    destination = tmp_path / "etc"
    environment = os.environ | {
        "GX10_MAINTENANCE_SOURCE_DIR": str(DEPLOY / "maintenance"),
        "GX10_MAINTENANCE_CONFIG_DIR": str(destination),
    }
    for _attempt in range(2):
        completed = subprocess.run(
            [installer],
            env=environment,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
    assert {path.name for path in destination.iterdir()} == {
        "storage-actions.json",
        "backup-plan.json",
        "restore-plan.json",
    }
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in destination.iterdir())


def test_maintenance_services_require_validated_installed_plans() -> None:
    plan_unit = (DEPLOY / "systemd/aca-gx10-maintenance-plans.service").read_text()
    assert "install-maintenance-plans.sh" in plan_unit
    assert "Before=aca-gx10-storage.service aca-gx10-backup.service" in plan_unit
    assert "aca-gx10-restore-drill.service" in plan_unit
    for unit in (
        "aca-gx10-storage.service",
        "aca-gx10-backup.service",
        "aca-gx10-restore-drill.service",
    ):
        source = (DEPLOY / "systemd" / unit).read_text()
        assert "Requires=aca-gx10-maintenance-plans.service" in source
        assert "After=aca-gx10-maintenance-plans.service" in source


def test_explicit_maintenance_identity_must_be_canonical_and_match_bound_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.gx10.backup import runtime as backup_runtime
    from scripts.gx10.storage import runtime as storage_runtime

    context = SimpleNamespace(operation_id="701", trace_id="a" * 32)
    monkeypatch.setattr(storage_runtime, "get_current_operation_context", lambda: context)
    monkeypatch.setattr(backup_runtime, "get_current_operation_context", lambda: context)
    with pytest.raises(ValueError, match="bound durable operation root"):
        storage_runtime._runtime_identity("702", "b" * 32)
    with pytest.raises(ValueError, match="bound durable operation root"):
        backup_runtime._maintenance_correlation("702", "b" * 32)
    assert storage_runtime._runtime_identity("701", "a" * 32) == ("701", "a" * 32)

    monkeypatch.setattr(storage_runtime, "get_current_operation_context", lambda: None)
    monkeypatch.setattr(backup_runtime, "get_current_operation_context", lambda: None)
    for operation_id, trace_id in (("not-canonical", "b" * 32), ("702", "0" * 32)):
        with pytest.raises(ValueError):
            storage_runtime._runtime_identity(operation_id, trace_id)
        with pytest.raises(ValueError):
            backup_runtime._maintenance_correlation(operation_id, trace_id)
