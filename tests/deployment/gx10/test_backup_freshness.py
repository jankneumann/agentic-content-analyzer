"""A backup that never runs must still alert: freshness is read, not inferred from failures."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts.gx10.backup.freshness import check

ROOT = Path(__file__).resolve().parents[3]
SYSTEMD = ROOT / "deploy/gx10/systemd"
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
LIMIT = timedelta(hours=36)


def _manifest(tmp_path: Path, *, outcome: str = "succeeded", age_hours: float = 1.0) -> Path:
    completed = (NOW - timedelta(hours=age_hours)).isoformat().replace("+00:00", "Z")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"outcome": outcome, "completed_at": completed}), encoding="utf-8")
    return path


def test_recent_successful_backup_is_fresh(tmp_path: Path) -> None:
    assert check(_manifest(tmp_path, age_hours=30), max_age=LIMIT, now=NOW) is None


def test_old_successful_backup_is_stale(tmp_path: Path) -> None:
    problem = check(_manifest(tmp_path, age_hours=8 * 24), max_age=LIMIT, now=NOW)
    assert problem is not None and "192.0 h old" in problem


@pytest.mark.parametrize("outcome", ["partial", "permanent_failure"])
def test_a_failed_newest_run_keeps_alerting(tmp_path: Path, outcome: str) -> None:
    problem = check(_manifest(tmp_path, outcome=outcome), max_age=LIMIT, now=NOW)
    assert problem is not None and outcome in problem


def test_missing_or_corrupt_manifest_is_stale_not_a_crash(tmp_path: Path) -> None:
    assert "no backup manifest" in (check(tmp_path / "absent.json", max_age=LIMIT, now=NOW) or "")
    corrupt = tmp_path / "manifest.json"
    corrupt.write_text("{not json", encoding="utf-8")
    assert "unreadable" in (check(corrupt, max_age=LIMIT, now=NOW) or "")
    naive = tmp_path / "naive.json"
    naive.write_text('{"outcome": "succeeded", "completed_at": "2026-10-21T00:00:00"}')
    assert "no timezone" in (check(naive, max_age=LIMIT, now=NOW) or "")


def test_cli_exit_code_is_what_systemd_alerts_on(tmp_path: Path) -> None:
    script = ROOT / "scripts/gx10/backup/freshness.py"
    stale = subprocess.run(
        ["/usr/bin/env", "python3", "-I", str(script), "--manifest", str(tmp_path / "none.json")],
        capture_output=True,
        text=True,
    )
    assert stale.returncode == 1
    assert "gx10 backup stale" in stale.stderr


def test_freshness_unit_runs_when_the_runtime_and_its_secrets_are_down() -> None:
    """The 8-day gap had the runtime, its secrets and every timer down at once."""
    unit = (SYSTEMD / "aca-gx10-backup-freshness.service").read_text(encoding="utf-8")
    directives = [line for line in unit.splitlines() if not line.startswith("#")]
    body = "\n".join(directives)
    assert "OnFailure=aca-gx10-maintenance-alert@%n.service" in body
    for forbidden in ("Requires=", "Requisite=", "BindsTo=", "ExecCondition=", "EnvironmentFile="):
        assert forbidden not in body, forbidden
    assert "aca-gx10.service" not in body
    assert "/opt/aca/.venv" not in body, "the venv is a symlink into /root"
    assert "--max-age-hours 36" in body


def test_freshness_timer_is_installed_for_boot_and_catches_up() -> None:
    timer = (SYSTEMD / "aca-gx10-backup-freshness.timer").read_text(encoding="utf-8")
    assert "WantedBy=timers.target" in timer
    assert "Persistent=true" in timer
    assert "OnBootSec=" in timer
