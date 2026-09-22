"""Copying a store must freeze it, and must always thaw it again.

Stopping the container was the original design and it cannot work: these
services carry `restart: on-failure:5`, and Podman brought ClickHouse back up
0.45 seconds after the stop, so tar ran against a live store and exited with
"file changed as we read it". MinIO failed inside Podman's own namespace
teardown while the stop and the restart raced.

`podman pause` emits no "died" event, so no restart policy fires and nothing
races the copy. What it must never do is leave a store frozen.
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


def _fixture(tmp_path: Path, *, pause_exit: int = 0, unpause_exit: int = 0) -> dict[str, str]:
    log = tmp_path / "calls.log"
    compose = tmp_path / "podman-compose.sh"
    compose.write_text("#!/usr/bin/env bash\n" f'echo "compose $*" >> "{log}"\n' "exit 0\n")
    podman = tmp_path / "podman"
    podman.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "podman $*" >> "{log}"\n'
        f'[[ "$1" == pause ]] && exit {pause_exit}\n'
        f'[[ "$1" == unpause ]] && exit {unpause_exit}\n'
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


def test_the_store_is_frozen_copied_and_thawed(tmp_path: Path) -> None:
    env = _fixture(tmp_path)

    result = subprocess.run([COMPONENT, "produce", "clickhouse"], env=env, capture_output=True)

    assert result.returncode == 0, result.stderr.decode()
    calls = _calls(tmp_path)
    assert calls == [
        "podman pause aca-gx10_clickhouse_1",
        "podman unpause aca-gx10_clickhouse_1",
    ], calls
    # Stopping hands the restart policy a "died" event to react to, which is
    # what put a live store under the copy.
    assert not any("stop" in call for call in calls)

    with tarfile.open(fileobj=BytesIO(result.stdout)) as archive:
        assert "./data.bin" in archive.getnames()


def test_a_refused_freeze_aborts_before_the_copy(tmp_path: Path) -> None:
    """A tar of a running store restores torn while looking like a backup."""
    env = _fixture(tmp_path, pause_exit=2)

    result = subprocess.run([COMPONENT, "produce", "clickhouse"], env=env, capture_output=True)

    assert result.returncode == 2
    assert result.stdout == b"", "no artifact may be produced from a live store"
    assert not any("unpause" in call for call in _calls(tmp_path))


def test_a_store_that_will_not_thaw_fails_the_component(tmp_path: Path) -> None:
    """The copy succeeded, but a store left frozen is an outage, not a backup."""
    env = _fixture(tmp_path, unpause_exit=1)

    result = subprocess.run([COMPONENT, "produce", "clickhouse"], env=env, capture_output=True)

    assert result.returncode == 1
    assert "podman unpause aca-gx10_clickhouse_1" in _calls(tmp_path)


@pytest.mark.parametrize("service", ["falkordb", "clickhouse", "minio"])
def test_every_offline_store_uses_the_same_sequence(service: str) -> None:
    source = COMPONENT.read_text(encoding="utf-8")
    assert f"{service}) paused_tar {service}" in source
