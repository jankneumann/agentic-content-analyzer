"""The scheduled backup streams producer -> age -> disk.

A 39GB ClickHouse component was buffered twice in RAM and the OOM killer took
the whole run down. These tests use the real `age` binary and a throwaway
keypair, so every artifact is proven to decrypt, not merely to exist.
"""

from __future__ import annotations

import hashlib
import resource
import shutil
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.gx10.backup import runtime
from src.services.backup import gx10 as backup

AGE = shutil.which("age") or "age"
AGE_KEYGEN = shutil.which("age-keygen") or "age-keygen"
pytestmark = pytest.mark.skipif(
    shutil.which("age") is None or shutil.which("age-keygen") is None,
    reason="needs the age binaries",
)


@pytest.fixture
def keypair(tmp_path: Path) -> tuple[Path, str]:
    identity = tmp_path / "identity.txt"
    subprocess.run([AGE_KEYGEN, "-o", str(identity)], check=True, capture_output=True)
    recipient = subprocess.run(
        [AGE_KEYGEN, "-y", str(identity)], check=True, capture_output=True, text=True
    ).stdout.strip()
    return identity, recipient


def _decrypt(artifact: Path, identity: Path) -> bytes:
    return subprocess.run(
        [AGE, "--decrypt", "--identity", str(identity), str(artifact)],
        check=True,
        capture_output=True,
    ).stdout


def _leftovers(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


def test_a_streamed_artifact_decrypts_to_exactly_what_the_producer_wrote(
    tmp_path: Path, keypair: tuple[Path, str]
) -> None:
    identity, recipient = keypair
    plaintext = tmp_path / "source.bin"
    plaintext.write_bytes(bytes(range(256)) * 40_000)  # ~10MB, spans chunks
    output = tmp_path / "out"
    output.mkdir()
    destination = output / "clickhouse-20261011T030000Z.age"

    size, digest = runtime.stream_component(
        ["/bin/cat", str(plaintext)],
        recipient=recipient,
        destination=destination,
        limit_bytes=1 << 30,
    )

    stored = destination.read_bytes()
    assert (size, digest) == (len(stored), hashlib.sha256(stored).hexdigest())
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert _decrypt(destination, identity) == plaintext.read_bytes()
    assert _leftovers(output) == [destination.name], "no .partial survives success"


def test_a_producer_that_dies_halfway_leaves_nothing_behind(
    tmp_path: Path, keypair: tuple[Path, str]
) -> None:
    """age exits 0 on the truncated stream; only the producer's code tells."""
    _, recipient = keypair
    output = tmp_path / "out"
    output.mkdir()

    with pytest.raises(RuntimeError, match=r"exit=3.*disk vanished"):
        runtime.stream_component(
            ["/bin/sh", "-c", "head -c 100000 /dev/zero; echo 'disk vanished' >&2; exit 3"],
            recipient=recipient,
            destination=output / "minio-20261011T030000Z.age",
            limit_bytes=1 << 30,
        )

    assert _leftovers(output) == []


def test_exceeding_the_quota_stops_mid_stream_and_cleans_up(
    tmp_path: Path, keypair: tuple[Path, str]
) -> None:
    _, recipient = keypair
    output = tmp_path / "out"
    output.mkdir()

    with pytest.raises(backup.ComponentQuotaExceededError):
        runtime.stream_component(
            # Would run forever: proves the producer is killed, not awaited.
            ["/bin/cat", "/dev/zero"],
            recipient=recipient,
            destination=output / "clickhouse-20261011T030000Z.age",
            limit_bytes=20 * 1024 * 1024,
        )

    assert _leftovers(output) == []


def test_memory_stays_flat_however_large_the_component(
    tmp_path: Path, keypair: tuple[Path, str]
) -> None:
    """256MB through the pipe must not raise this process's peak by 256MB."""
    _, recipient = keypair
    output = tmp_path / "out"
    output.mkdir()
    before_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    size, _ = runtime.stream_component(
        ["/usr/bin/head", "-c", str(256 * 1024 * 1024), "/dev/zero"],
        recipient=recipient,
        destination=output / "clickhouse-20261011T030000Z.age",
        limit_bytes=1 << 34,
    )

    grown_mib = (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - before_kib) / 1024
    assert size > 256 * 1024 * 1024
    assert grown_mib < 64, f"peak RSS grew {grown_mib:.0f}MiB streaming 256MiB"


def test_the_controller_isolates_a_component_that_outgrows_the_quota(
    tmp_path: Path, keypair: tuple[Path, str]
) -> None:
    identity, recipient = keypair
    output = tmp_path / "out"
    output.mkdir()
    big = {backup.BackupComponent.CLICKHOUSE}

    def streamer(component: backup.BackupComponent) -> backup.ComponentStreamer:
        argv = ["/bin/cat", "/dev/zero"] if component in big else ["/bin/echo", str(component)]

        def stream(recipient: str, name: str, remaining: int) -> tuple[int, str]:
            return runtime.stream_component(
                argv, recipient=recipient, destination=output / name, limit_bytes=remaining
            )

        return stream

    controller = backup.GX10BackupController(
        streamers={component: streamer(component) for component in backup.BackupComponent}
    )
    manifest = controller.run(
        recipient_catalog=backup.AgeRecipientCatalog(active=recipient, retained=()),
        correlation=backup.MaintenanceCorrelation(operation_id="1", trace_id="a" * 32),
        quota=backup.BackupQuota(limit_bytes=8 * 1024 * 1024, used_bytes=0),
        started_at=datetime(2026, 10, 11, 3, tzinfo=UTC),
    )

    assert manifest.outcome == "partial"
    by_component = {result.component: result for result in manifest.components}
    assert by_component[backup.BackupComponent.CLICKHOUSE].diagnostic_code == (
        "backup_quota_exhausted"
    )
    for component, result in by_component.items():
        if component in big:
            continue
        assert result.outcome == "succeeded"
        artifact = output / str(result.artifact_name)
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == result.checksum_sha256
        assert _decrypt(artifact, identity) == f"{component}\n".encode()
    assert not any(name.endswith(".partial") for name in _leftovers(output))


def test_streamers_and_the_buffered_trio_are_mutually_exclusive() -> None:
    noop: backup.ComponentStreamer = lambda _r, _n, _q: (0, "")  # noqa: E731
    with pytest.raises(ValueError, match="not both"):
        backup.GX10BackupController(
            streamers=dict.fromkeys(backup.BackupComponent, noop),
            producers=dict.fromkeys(backup.BackupComponent, lambda: b""),
        )
    with pytest.raises(backup.ComponentInventoryError, match="complete"):
        backup.GX10BackupController(streamers={backup.BackupComponent.MINIO: noop})


def test_the_scheduled_backup_streams_rather_than_buffers() -> None:
    source = (Path(runtime.__file__)).read_text(encoding="utf-8")
    scheduled = source.split("def run_scheduled_backup(", 1)[1].split("\ndef ", 1)[0]
    assert "streamers=" in scheduled
    assert "producers=" not in scheduled
