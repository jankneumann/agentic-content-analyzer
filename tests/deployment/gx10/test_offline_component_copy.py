"""Stopping a store to copy it cold must leave the store running.

The first backup that reached the stores produced four artifacts and failed
ClickHouse and MinIO. Both failed on the restart, not the copy: `compose up -d`
finds the container already there, runs `podman run`, takes 125 for the name
in use, falls back to `podman start`, and reports failure anyway. The store
came back; the component was recorded as a permanent failure with no artifact,
which is the half that matters.
"""

from __future__ import annotations

import os
import subprocess
import tarfile
from io import BytesIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
COMPONENT = ROOT / "scripts/gx10/backup/component.sh"


def _fixture(tmp_path: Path, *, stop_exit: int = 0, start_exit: int = 0) -> dict[str, str]:
    log = tmp_path / "calls.log"
    compose = tmp_path / "podman-compose.sh"
    compose.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "compose $*" >> "{log}"\n'
        f"[[ \"$1\" == stop ]] && exit {stop_exit}\n"
        "exit 0\n"
    )
    podman = tmp_path / "podman"
    podman.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "podman $*" >> "{log}"\n'
        f"[[ \"$1\" == start ]] && exit {start_exit}\n"
        "exit 0\n"
    )
    compose.chmod(0o700)
    podman.chmod(0o700)

    persist = tmp_path / "srv"
    (persist / "clickhouse").mkdir(parents=True)
    (persist / "clickhouse" / "data.bin").write_bytes(b"cold copy")
    return {
        "PATH": os.environ["PATH"],
        "GX10_COMPOSE_BIN": str(compose),
        "GX10_PODMAN_BIN": str(podman),
        "GX10_PERSIST_ROOT": str(persist),
    }


def _calls(tmp_path: Path) -> list[str]:
    log = tmp_path / "calls.log"
    return log.read_text().splitlines() if log.exists() else []


def test_the_store_is_stopped_copied_and_started_again(tmp_path: Path) -> None:
    env = _fixture(tmp_path)

    result = subprocess.run(
        [COMPONENT, "produce", "clickhouse"], env=env, capture_output=True
    )

    assert result.returncode == 0, result.stderr.decode()
    calls = _calls(tmp_path)
    assert calls[0].startswith("compose stop")
    assert "podman start aca-gx10_clickhouse_1" in calls
    # The container exists; recreating it is what reported failure after a
    # restart that had in fact worked.
    assert not any(call.startswith("compose up") for call in calls), calls

    with tarfile.open(fileobj=BytesIO(result.stdout)) as archive:
        assert "./data.bin" in archive.getnames()


def test_a_failed_stop_aborts_before_the_copy(tmp_path: Path) -> None:
    """A tar of a running store restores torn while looking like a backup."""
    env = _fixture(tmp_path, stop_exit=2)

    result = subprocess.run(
        [COMPONENT, "produce", "clickhouse"], env=env, capture_output=True
    )

    assert result.returncode == 2
    assert result.stdout == b"", "no artifact may be produced from a live store"
    assert not any("start" in call for call in _calls(tmp_path))


def test_a_store_that_will_not_start_again_fails_the_component(tmp_path: Path) -> None:
    """The copy succeeded, but leaving a store down must not read as success."""
    env = _fixture(tmp_path, start_exit=1)

    result = subprocess.run(
        [COMPONENT, "produce", "clickhouse"], env=env, capture_output=True
    )

    assert result.returncode == 1
    assert "podman start aca-gx10_clickhouse_1" in _calls(tmp_path)


@pytest.mark.parametrize("service", ["falkordb", "clickhouse", "minio"])
def test_every_offline_store_uses_the_same_sequence(service: str) -> None:
    source = COMPONENT.read_text(encoding="utf-8")
    assert f"{service}) offline_tar {service}" in source
