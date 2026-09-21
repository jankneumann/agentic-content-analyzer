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


def test_the_controller_logs_the_reason_it_recorded_a_diagnostic_code_for() -> None:
    """`except Exception:` with no logging is what made the codes opaque."""
    source = (ROOT / "src/services/backup/gx10.py").read_text(encoding="utf-8")
    assert "except Exception:" not in source, "a bare swallow loses the only copy of the reason"
    assert "gx10 component backup failed" in source
    assert "gx10 component restore failed" in source


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
