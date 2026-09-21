"""A failed component must say why, and the units must be able to run Podman.

The first real backup produced six components: one succeeded and five reported
`component_backup_failed` with no reason anywhere. The manifest carries a
diagnostic code by design, the controller caught the exception bare, and the
subprocess's stderr was captured and dropped, so five identical codes could
have meant five different causes.

The one that succeeded is the tell: `configuration_metadata` only tars a
directory. Every producer that touches a container failed, because the units
ran under `ProtectSystem=strict` while rootful Podman needs to write container
state under /var/lib/containers and /run.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PODMAN_UNITS = ("aca-gx10-backup", "aca-gx10-restore-drill", "aca-gx10-storage")


def _runtime_module():
    spec = importlib.util.spec_from_file_location(
        "gx10_backup_runtime_under_test", ROOT / "scripts/gx10/backup/runtime.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_a_failed_component_command_reports_its_exit_code_and_stderr() -> None:
    runtime = _runtime_module()

    with pytest.raises(RuntimeError) as failure:
        runtime._safe_command(["/bin/sh", "-c", "echo 'pg_dump: connection refused' >&2; exit 3"])

    message = str(failure.value)
    assert "exit=3" in message
    assert "connection refused" in message


def test_command_evidence_is_bounded_and_survives_empty_stderr() -> None:
    """Unbounded command output in a log line is its own incident."""
    runtime = _runtime_module()

    assert runtime._command_evidence(b"") == "no stderr"
    bounded = runtime._command_evidence(b"x" * 10_000)
    assert len(bounded) <= runtime._STDERR_EVIDENCE_LIMIT


def test_the_controller_logs_the_reason_it_recorded_a_diagnostic_code_for(caplog) -> None:
    """The reason must be in the message, not in `extra`.

    The first attempt put the component and the failure in structured fields.
    The host formatter drops those, so the journal received the bare sentence
    "gx10 component backup failed" five times and the operator was no better
    off than with five identical diagnostic codes. This reads the line that is
    actually emitted rather than the source that emits it.
    """
    import logging
    from datetime import UTC, datetime

    from src.services.backup import gx10 as backup

    source = (ROOT / "src/services/backup/gx10.py").read_text(encoding="utf-8")
    assert "except Exception:" not in source, "a bare swallow loses the only copy of the reason"

    component = backup.BackupComponent.FALKORDB
    producers = {
        item: (lambda: b"payload") if item is not component else _raise_unreachable
        for item in backup.BackupComponent
    }
    controller = backup.GX10BackupController(
        producers=producers,
        encrypt=lambda payload, _recipient: b"age-encryption.org/v1\n" + payload,
        store=lambda _name, _payload: None,
    )

    with caplog.at_level(logging.ERROR):
        controller.run(
            recipient_catalog=backup.AgeRecipientCatalog(active="age1" + "q" * 58, retained=()),
            correlation=backup.MaintenanceCorrelation(operation_id="41", trace_id="a" * 32),
            quota=backup.BackupQuota(limit_bytes=1_000_000, used_bytes=0),
            started_at=datetime(2026, 9, 21, tzinfo=UTC),
        )

    logged = [record.getMessage() for record in caplog.records]
    reason = next((line for line in logged if "component backup failed" in line), None)
    assert reason is not None, logged
    assert "falkordb" in reason
    assert "podman is unreachable" in reason


def _raise_unreachable() -> bytes:
    raise RuntimeError("component command failed: podman-compose exit=1 podman is unreachable")


@pytest.mark.parametrize("name", PODMAN_UNITS)
def test_units_that_drive_podman_can_write_container_state(name: str) -> None:
    unit = (ROOT / f"deploy/gx10/systemd/{name}.service").read_text(encoding="utf-8")
    directives = [
        line.strip() for line in unit.splitlines() if line.strip() and not line.startswith("#")
    ]
    assert "ProtectSystem=strict" not in directives, name
    assert "ProtectSystem=full" in directives, name
    # These scripts stop a store for a consistent copy and start it again. The
    # restarted container's conmon lands in this unit's cgroup, and a oneshot's
    # default kill would stop it again the moment the unit finished.
    assert "KillMode=process" in directives, name


@pytest.mark.parametrize("name", PODMAN_UNITS)
def test_units_that_drive_podman_can_parse_the_overlay(name: str) -> None:
    """podman-compose reads the overlay on every call, and the overlay makes
    the application image and the reviewed digests mandatory. A unit without
    them fails at parse time, before touching a container: exactly the shape
    of five producers failing in a second each while the one that only tars a
    directory succeeded."""
    compose = (ROOT / "docker-compose.gx10.yml").read_text(encoding="utf-8")
    required = set(re.findall(r"\$\{(GX10_[A-Z_]+):\?", compose))
    assert required, "the overlay should still make its image pins mandatory"

    unit = (ROOT / f"deploy/gx10/systemd/{name}.service").read_text(encoding="utf-8")
    assert "EnvironmentFile=/etc/aca/gx10-images.env" in unit, name


def test_the_helper_environment_carries_the_pins_and_leaves_secrets_behind(monkeypatch) -> None:
    """Scrubbing to PATH alone is what broke five producers.

    podman-compose parses the overlay on every call and the overlay makes the
    image pins mandatory, so a helper with PATH alone fails on "set a reviewed
    application tag@sha256 digest" before touching a store. The pins are
    public references; the credentials in the same process environment are
    not, and must not follow the helper into the container engine.
    """
    from scripts.gx10.maintenance_env import component_environment

    monkeypatch.setenv("GX10_APP_IMAGE", "ghcr.io/example/app:gx10-abc@sha256:" + "a" * 64)
    monkeypatch.setenv("GX10_SQUID_DIGEST", "b" * 64)
    monkeypatch.setenv("GX10_LANGFUSE_WORKER_DIGEST", "c" * 64)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@10.89.0.251:5432/newsletters")
    monkeypatch.setenv("GX10_ADMIN_API_KEY", "must-not-travel")

    environment = component_environment()

    compose = (ROOT / "docker-compose.gx10.yml").read_text(encoding="utf-8")
    for name in set(re.findall(r"\$\{(GX10_[A-Z0-9_]+):\?", compose)):
        assert name in environment, f"{name} is mandatory in the overlay"
    assert "DATABASE_URL" not in environment
    assert "GX10_ADMIN_API_KEY" not in environment
    assert environment["PATH"]


def test_both_maintenance_runtimes_use_that_one_rule() -> None:
    """The backup and the storage monitor scrubbed identically and broke
    identically; the rule lives in one module so it cannot drift."""
    for relative in ("scripts/gx10/backup/runtime.py", "scripts/gx10/storage/runtime.py"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "env=component_environment()" in source, relative
        assert 'env={"PATH"' not in source, relative
