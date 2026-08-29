from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from src.clients.operational_observability import (
    BootstrapAuditCorruptionError,
    BootstrapAuditSpool,
)


def test_bootstrap_spool_is_masked_hash_chained_and_mode_0600(tmp_path: Path) -> None:
    spool = BootstrapAuditSpool(tmp_path / "bootstrap-audit")

    first = spool.append(
        entrypoint="bootstrap.seed",
        outcome="succeeded",
        metadata={"token": "top-secret", "component": "openbao"},
    )
    second = spool.append(
        entrypoint="bootstrap.profile",
        outcome="permanent_failure",
        diagnostic_code="profile.invalid",
        metadata={"detail": "password=hunter2"},
    )

    assert stat.S_IMODE(spool.path.stat().st_mode) == 0o600
    assert first["previous_hash"] is None
    assert second["previous_hash"] == first["record_hash"]
    assert spool.verify(required=True) == [first, second]
    serialized = spool.path.read_text()
    assert "top-secret" not in serialized
    assert "hunter2" not in serialized
    assert "[REDACTED]" in serialized


def test_first_healthy_maintenance_imports_once_and_marks_checkpoint(tmp_path: Path) -> None:
    spool = BootstrapAuditSpool(tmp_path / "bootstrap-audit")
    spool.append(entrypoint="bootstrap.setup", outcome="succeeded")
    imported: list[dict[str, object]] = []

    assert spool.import_records(imported.append) == 1
    restarted = BootstrapAuditSpool(spool.directory)
    assert restarted.import_records(imported.append) == 0
    assert len(imported) == 1
    assert stat.S_IMODE(spool.checkpoint_path.stat().st_mode) == 0o600


def test_missing_or_corrupt_required_spool_degrades_readiness(tmp_path: Path) -> None:
    missing = BootstrapAuditSpool(tmp_path / "missing")
    assert missing.readiness(required=True).ready is False
    assert missing.readiness(required=True).diagnostic_code == "bootstrap.spool_missing"

    corrupt = BootstrapAuditSpool(tmp_path / "corrupt")
    corrupt.append(entrypoint="bootstrap.setup", outcome="succeeded")
    payload = json.loads(corrupt.path.read_text().splitlines()[0])
    payload["entrypoint"] = "tampered"
    corrupt.path.write_text(json.dumps(payload) + "\n")
    corrupt.path.chmod(0o600)

    assert corrupt.readiness(required=True).ready is False
    assert corrupt.readiness(required=True).diagnostic_code == "bootstrap.spool_corrupt"
    with pytest.raises(BootstrapAuditCorruptionError):
        corrupt.verify(required=True)
