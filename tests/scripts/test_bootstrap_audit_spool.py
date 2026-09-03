from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from src.clients import operational_observability
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


def test_bootstrap_directory_prefers_explicit_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ACA_BOOTSTRAP_AUDIT_DIR", str(tmp_path / "configured"))
    assert operational_observability._bootstrap_directory() == tmp_path / "configured"


def test_bootstrap_directory_keeps_the_durable_default_when_usable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ACA_BOOTSTRAP_AUDIT_DIR", raising=False)
    default = tmp_path / "srv" / "aca" / "bootstrap-audit"
    default.parent.mkdir(parents=True)
    monkeypatch.setattr(operational_observability, "_DEFAULT_BOOTSTRAP_DIRECTORY", default)
    assert operational_observability._bootstrap_directory() == default


@pytest.mark.skipif(os.geteuid() == 0, reason="root can enter any directory")
def test_bootstrap_directory_falls_back_to_user_state_when_default_is_root_owned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A developer hook on the production host must not crash on /srv/aca."""
    monkeypatch.delenv("ACA_BOOTSTRAP_AUDIT_DIR", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    sealed = tmp_path / "srv" / "aca"
    sealed.mkdir(parents=True)
    sealed.chmod(0o000)
    try:
        monkeypatch.setattr(
            operational_observability, "_DEFAULT_BOOTSTRAP_DIRECTORY", sealed / "bootstrap-audit"
        )
        chosen = operational_observability._bootstrap_directory()
        assert chosen == tmp_path / "state" / "aca" / "bootstrap-audit"
        BootstrapAuditSpool(chosen).append(entrypoint="bootstrap.hook", outcome="succeeded")
        assert chosen.is_dir()
    finally:
        sealed.chmod(0o700)
