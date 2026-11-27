"""The restore drill streams artifact -> age -> restore command.

The drill read every artifact into memory, then held each decrypted component
a second time and handed it to the restore command a third. A ~100GB
ClickHouse artifact on a 121GB host OOM-killed the drill on 2026-11-16 and
2026-11-23. These tests use the real `age` binary and a throwaway keypair.
"""

from __future__ import annotations

import json
import resource
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.gx10.backup import runtime
from src.services.backup import gx10 as backup

AGE_KEYGEN = shutil.which("age-keygen") or "age-keygen"
pytestmark = pytest.mark.skipif(
    shutil.which("age") is None or shutil.which("age-keygen") is None,
    reason="needs the age binaries",
)

# The restore command gets the target directory appended as its last argument.
WRITE_DATA = ("/bin/sh", "-c", 'cat > "$1/data"', "sh")
HAS_DATA = ("/bin/sh", "-c", 'test -s "$1/data"', "sh")


def _keypair(directory: Path) -> tuple[str, str]:
    """Return (secret identity, recipient) for a fresh age key."""
    directory.mkdir(parents=True, exist_ok=True)
    key_file = directory / "identity.txt"
    subprocess.run([AGE_KEYGEN, "-o", str(key_file)], check=True, capture_output=True)
    secret = next(
        line
        for line in key_file.read_text(encoding="utf-8").splitlines()
        if line.startswith("AGE-SECRET-KEY-")
    )
    recipient = subprocess.run(
        [AGE_KEYGEN, "-y", str(key_file)], check=True, capture_output=True, text=True
    ).stdout.strip()
    return secret, recipient


@pytest.fixture
def keypair(tmp_path: Path) -> tuple[str, str]:
    return _keypair(tmp_path / "key")


def _encrypt(producer: list[str], recipient: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    runtime.stream_component(
        producer, recipient=recipient, destination=destination, limit_bytes=1 << 34
    )
    return destination


def test_a_streamed_restore_writes_exactly_what_was_backed_up(
    tmp_path: Path, keypair: tuple[str, str]
) -> None:
    identity, recipient = keypair
    plaintext = tmp_path / "source.bin"
    plaintext.write_bytes(bytes(range(256)) * 40_000)  # ~10MB, spans chunks
    artifact = _encrypt(["/bin/cat", str(plaintext)], recipient, tmp_path / "out" / "pg.age")
    target = tmp_path / "isolated" / "pg"
    target.mkdir(parents=True)

    runtime.stream_restore(WRITE_DATA, artifact=artifact, identity=identity, target=target)

    assert (target / "data").read_bytes() == plaintext.read_bytes()


def test_memory_stays_flat_however_large_the_artifact(
    tmp_path: Path, keypair: tuple[str, str]
) -> None:
    """256MB through the drill must not raise this process's peak by 256MB."""
    identity, recipient = keypair
    artifact = _encrypt(
        ["/usr/bin/head", "-c", str(256 * 1024 * 1024), "/dev/zero"],
        recipient,
        tmp_path / "out" / "clickhouse.age",
    )
    target = tmp_path / "isolated" / "clickhouse"
    target.mkdir(parents=True)
    before_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    runtime.stream_restore(
        ("/bin/sh", "-c", 'wc -c > "$1/size"', "sh"),
        artifact=artifact,
        identity=identity,
        target=target,
    )

    grown_mib = (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - before_kib) / 1024
    assert int((target / "size").read_text().strip()) == 256 * 1024 * 1024
    assert grown_mib < 64, f"peak RSS grew {grown_mib:.0f}MiB restoring 256MiB"


def test_a_failing_restore_command_is_reported_without_hanging_age(
    tmp_path: Path, keypair: tuple[str, str]
) -> None:
    """The restore exits without reading; age must not block on a full pipe."""
    identity, recipient = keypair
    artifact = _encrypt(
        ["/usr/bin/head", "-c", str(32 * 1024 * 1024), "/dev/urandom"],
        recipient,
        tmp_path / "out" / "minio.age",
    )

    with pytest.raises(RuntimeError, match=r"exit=4.*restore refused"):
        runtime.stream_restore(
            ("/bin/sh", "-c", "echo 'restore refused' >&2; exit 4", "sh"),
            artifact=artifact,
            identity=identity,
            target=tmp_path / "isolated",
        )


def test_a_decryption_failure_fails_even_when_the_restore_command_exits_zero(
    tmp_path: Path, keypair: tuple[str, str]
) -> None:
    """`cat` happily writes an empty file from age's empty output; age's code tells."""
    _, recipient = keypair
    wrong_identity, _ = _keypair(tmp_path / "other-key")
    artifact = _encrypt(["/bin/echo", "rows"], recipient, tmp_path / "out" / "pg.age")
    target = tmp_path / "isolated" / "pg"
    target.mkdir(parents=True)

    with pytest.raises(backup.EncryptionMaterialError, match="age decryption failed"):
        runtime.stream_restore(
            WRITE_DATA, artifact=artifact, identity=wrong_identity, target=target
        )


def test_a_file_without_the_age_envelope_never_reaches_the_restore_command(
    tmp_path: Path, keypair: tuple[str, str]
) -> None:
    identity, _ = keypair
    plaintext = tmp_path / "pg.age"
    plaintext.write_bytes(b"not encrypted at all")
    target = tmp_path / "isolated" / "pg"
    target.mkdir(parents=True)

    with pytest.raises(backup.EncryptionMaterialError, match="age envelope"):
        runtime.stream_restore(WRITE_DATA, artifact=plaintext, identity=identity, target=target)

    assert not (target / "data").exists()


def test_the_identity_never_reaches_argv_or_the_environment(
    tmp_path: Path, keypair: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    identity, recipient = keypair
    artifact = _encrypt(["/bin/echo", "rows"], recipient, tmp_path / "out" / "pg.age")
    target = tmp_path / "isolated" / "pg"
    target.mkdir(parents=True)
    launched: list[tuple[list[str], dict[str, str], tuple[int, ...]]] = []
    real_popen = subprocess.Popen

    def recording_popen(argv, **kwargs):
        launched.append((list(argv), dict(kwargs.get("env") or {}), kwargs.get("pass_fds", ())))
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(runtime.subprocess, "Popen", recording_popen)

    runtime.stream_restore(WRITE_DATA, artifact=artifact, identity=identity, target=target)

    assert (target / "data").read_text() == "rows\n"
    for argv, env, _ in launched:
        assert identity not in repr(argv)
        assert identity not in repr(env)
    age_argv, age_env, age_fds = launched[0]
    assert age_argv[:2] == ["age", "--decrypt"]
    assert set(age_env) == {"PATH"}
    assert age_fds, "the identity travels on an inherited fd"


def _isolated_restore_fixture(tmp_path: Path, keypair: tuple[str, str]) -> dict[str, Path]:
    """Back up every component for real, then write the plan and age material."""
    identity, recipient = keypair
    artifacts = tmp_path / "backups"
    artifacts.mkdir()

    def streamer(component: backup.BackupComponent) -> backup.ComponentStreamer:
        def stream(recipient: str, name: str, remaining: int) -> tuple[int, str]:
            return runtime.stream_component(
                ["/bin/echo", f"{component} rows"],
                recipient=recipient,
                destination=artifacts / name,
                limit_bytes=remaining,
            )

        return stream

    manifest = backup.GX10BackupController(
        streamers={component: streamer(component) for component in backup.BackupComponent}
    ).run(
        recipient_catalog=backup.AgeRecipientCatalog(active=recipient, retained=()),
        correlation=backup.MaintenanceCorrelation(operation_id="1", trace_id="a" * 32),
        quota=backup.BackupQuota(limit_bytes=1 << 30, used_bytes=0),
        started_at=datetime.now(UTC),
    )
    assert manifest.outcome == "succeeded"
    manifest_path = artifacts / "manifest.json"
    manifest_path.write_text(manifest.to_json(), encoding="utf-8")

    production = {}
    for component in backup.BackupComponent:
        source = tmp_path / "production" / str(component)
        source.mkdir(parents=True)
        production[str(component)] = str(source)
    components = [str(component) for component in backup.BackupComponent]
    plan_path = tmp_path / "restore-plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "restore": {name: list(WRITE_DATA) for name in components},
                "validate": {name: list(HAS_DATA) for name in components},
                "production_sources": production,
                "metadata_probe": {
                    "application_operation_rows": ["/bin/true"],
                    "langfuse_trace_metadata": ["/bin/true"],
                },
            }
        ),
        encoding="utf-8",
    )
    material = tmp_path / "restore-age.json"
    material.write_text(
        json.dumps(
            {
                "active_recipient": recipient,
                "retained_recipients": [],
                "identities": {recipient: identity},
            }
        ),
        encoding="utf-8",
    )
    material.chmod(0o600)
    return {"plan": plan_path, "manifest": manifest_path, "artifacts": artifacts, "age": material}


def test_the_isolated_restore_streams_every_component_end_to_end(
    tmp_path: Path, keypair: tuple[str, str]
) -> None:
    paths = _isolated_restore_fixture(tmp_path, keypair)
    isolated = tmp_path / "isolated"

    result = runtime.run_isolated_restore(
        plan_path=paths["plan"],
        manifest_path=paths["manifest"],
        artifact_dir=paths["artifacts"],
        isolated_root=isolated,
        correlation=backup.MaintenanceCorrelation(operation_id="2", trace_id="b" * 32),
        age=runtime.age_adapter_from_material_file(paths["age"], require_identities=True),
    )

    assert result.outcome == "succeeded", result.diagnostic_codes
    for component in backup.BackupComponent:
        assert (isolated / str(component) / "data").read_text() == f"{component} rows\n"


def test_a_corrupted_artifact_fails_its_component_before_decryption(
    tmp_path: Path, keypair: tuple[str, str]
) -> None:
    paths = _isolated_restore_fixture(tmp_path, keypair)
    manifest = backup.BackupManifest.from_json(paths["manifest"].read_text(encoding="utf-8"))
    corrupted = next(
        result
        for result in manifest.components
        if result.component == backup.BackupComponent.CLICKHOUSE
    )
    with (paths["artifacts"] / str(corrupted.artifact_name)).open("ab") as handle:
        handle.write(b"tampered")
    isolated = tmp_path / "isolated"

    result = runtime.run_isolated_restore(
        plan_path=paths["plan"],
        manifest_path=paths["manifest"],
        artifact_dir=paths["artifacts"],
        isolated_root=isolated,
        correlation=backup.MaintenanceCorrelation(operation_id="2", trace_id="b" * 32),
        age=runtime.age_adapter_from_material_file(paths["age"], require_identities=True),
    )

    assert result.outcome == "permanent_failure"
    assert result.diagnostic_codes == ("artifact_checksum_mismatch",)
    assert not (isolated / str(backup.BackupComponent.CLICKHOUSE)).exists()


def test_a_missing_artifact_fails_before_any_component_restores(
    tmp_path: Path, keypair: tuple[str, str]
) -> None:
    paths = _isolated_restore_fixture(tmp_path, keypair)
    manifest = backup.BackupManifest.from_json(paths["manifest"].read_text(encoding="utf-8"))
    (paths["artifacts"] / str(manifest.components[-1].artifact_name)).unlink()
    isolated = tmp_path / "isolated"

    with pytest.raises(FileNotFoundError, match="manifest artifacts are missing"):
        runtime.run_isolated_restore(
            plan_path=paths["plan"],
            manifest_path=paths["manifest"],
            artifact_dir=paths["artifacts"],
            isolated_root=isolated,
            correlation=backup.MaintenanceCorrelation(operation_id="2", trace_id="b" * 32),
            age=runtime.age_adapter_from_material_file(paths["age"], require_identities=True),
        )

    assert not isolated.exists()


def test_the_isolated_restore_streams_rather_than_buffers() -> None:
    source = Path(runtime.__file__).read_text(encoding="utf-8")
    drill = source.split("def run_isolated_restore(", 1)[1].split("\ndef ", 1)[0]
    assert "restorers=" in drill
    assert "decrypt=" not in drill
    assert "read_bytes()" not in drill
