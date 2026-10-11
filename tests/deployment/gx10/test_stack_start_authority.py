"""Only an operator starts the runtime; a timer never does.

A minutely storage monitor declared `Requires=aca-gx10.service`, so every tick
restarted a stack that `make stop` had just stopped. A Langfuse wipe ran into
live ClickHouse and MinIO writers and failed with "Directory not empty".
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SYSTEMD = ROOT / "deploy/gx10/systemd"
GATE = "/usr/bin/systemctl is-active --quiet aca-gx10.service"


def _timer_driven_services() -> list[Path]:
    services = []
    for timer in SYSTEMD.glob("*.timer"):
        match = re.search(r"^Unit=(\S+)$", timer.read_text(encoding="utf-8"), re.MULTILINE)
        services.append(SYSTEMD / (match.group(1) if match else timer.stem + ".service"))
    return services


def test_no_timer_driven_unit_can_start_the_runtime() -> None:
    services = _timer_driven_services()
    assert services, "expected timer-driven maintenance units"
    for service in services:
        source = service.read_text(encoding="utf-8")
        for directive in ("Requires", "Wants", "BindsTo", "Requisite"):
            pulls = re.findall(rf"^{directive}=(.*)$", source, re.MULTILINE)
            assert not any("aca-gx10.service" in line.split() for line in pulls), (
                f"{service.name} {directive}= would start or couple to the runtime"
            )


def test_a_skipped_backup_alerts_but_a_skipped_monitor_tick_does_not() -> None:
    for unit in ("aca-gx10-backup.service", "aca-gx10-restore-drill.service"):
        source = (SYSTEMD / unit).read_text(encoding="utf-8")
        # A failing ExecStartPre puts the unit in `failed`, which fires OnFailure=.
        assert f"ExecStartPre={GATE}" in source
        assert "OnFailure=aca-gx10-maintenance-alert@%n.service" in source

    storage = (SYSTEMD / "aca-gx10-storage.service").read_text(encoding="utf-8")
    assert f"ExecCondition={GATE}" in storage


def test_wipe_langfuse_names_exact_paths_and_demands_confirmation() -> None:
    makefile = (ROOT / "deploy/gx10/Makefile").read_text(encoding="utf-8")
    paths = re.search(r"^LANGFUSE_DATA := (.*)$", makefile, re.MULTILINE)
    assert paths is not None
    listed = paths.group(1).split()
    assert listed == [
        "/srv/aca/clickhouse",
        "/srv/aca/clickhouse-logs",
        "/srv/aca/minio",
        "/srv/aca/langfuse-postgres",
    ]
    assert "/srv/aca/postgres" not in listed, "that is the application database"
    assert not any("*" in path for path in listed)

    target = makefile.split("\nwipe-langfuse:", 1)[1].split("\n\n", 1)[0]
    assert 'CONFIRM)" == wipe-langfuse' in target
    assert target.index("systemctl stop aca-gx10.service") < target.index("refusing to delete")
    assert target.index("refusing to delete") < target.index("\trm -rf --one-file-system")


def test_every_host_python_entrypoint_can_reach_the_database() -> None:
    """The operational wrapper reserves an operation row first; a unit without
    the host env file connects to 127.0.0.1:5432 and fails before any work."""
    for unit in SYSTEMD.glob("*.service"):
        source = unit.read_text(encoding="utf-8")
        if re.search(r"^ExecStart=/opt/aca/\.venv/bin/python -m scripts\.", source, re.MULTILINE):
            assert "EnvironmentFile=/run/aca/gx10/host-maintenance.env" in source, unit.name
            assert "ProtectSystem=strict" not in source, unit.name
