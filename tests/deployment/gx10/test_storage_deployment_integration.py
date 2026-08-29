from __future__ import annotations

import json
import subprocess
from pathlib import Path

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
        completed = subprocess.run(["bash", "-n", script], capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr
