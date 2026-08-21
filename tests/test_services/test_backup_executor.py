"""The pipeline executor, against REAL subprocesses.

Everything else in this package mocks the execution seam, which is right for
testing decisions. But the executor IS the seam, and the properties that matter
about it — that a mid-pipe failure is visible, that the digest measures the right
bytes — are properties of how processes are actually wired together. Mocking here
would test the mock.

Only coreutils are required (`printf`, `cat`, `sh`, `tee`, `sha256sum`, `wc`), so
this runs anywhere. The `age` case skips when the binary is absent.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from src.services.backup.executor import Stage, run_pipeline


def _bin(name: str) -> str:
    """Resolve a tool to its absolute path.

    ruff S607 flags bare executable names: a partial path resolves through
    PATH at exec time, so what actually runs depends on the caller's
    environment. These tests shell out to real binaries, so resolve once
    and fail loudly if the tool is absent rather than silently running
    something else.
    """
    resolved = shutil.which(name)
    if resolved is None:  # pragma: no cover - guarded by skipif
        raise RuntimeError(f"required test binary not found: {name}")
    return resolved


class TestEveryStageStatusIsVisible:
    def test_a_clean_pipeline_reports_every_stage(self) -> None:
        result = run_pipeline(
            [
                Stage(name="src", argv=("printf", "%s", "hello")),
                Stage(name="mid", argv=("cat",)),
                Stage(name="sink", argv=("cat",)),
            ]
        )
        assert result.ok
        assert [name for name, _ in result.stage_status] == ["src", "mid", "tee", "sink"]

    def test_a_failure_in_the_first_stage_is_not_masked_by_the_last(self) -> None:
        """This is the whole reason the executor chains Popen instead of running
        `sh -c 'a | b | c'`. A shell pipeline reports the LAST stage's status, so
        `pg_dump` dying halfway yields zero from `rclone` and a truncated
        ciphertext uploads under a green light."""
        result = run_pipeline(
            [
                Stage(name="dump", argv=("sh", "-c", "printf partial; exit 3")),
                Stage(name="upload", argv=("cat",)),
            ]
        )
        assert not result.ok
        assert "dump" in result.failed_stages
        assert dict(result.stage_status)["dump"] == 3
        assert dict(result.stage_status)["upload"] == 0  # the masking exit code

    def test_a_failure_in_a_middle_stage_is_visible(self) -> None:
        result = run_pipeline(
            [
                Stage(name="src", argv=("printf", "%s", "x")),
                Stage(name="middle", argv=("sh", "-c", "cat >/dev/null; exit 4")),
                Stage(name="sink", argv=("cat",)),
            ]
        )
        assert not result.ok
        assert "middle" in result.failed_stages

    def test_a_single_stage_pipeline_works(self) -> None:
        assert run_pipeline([Stage(name="only", argv=("true",))]).ok

    def test_an_empty_pipeline_is_refused(self) -> None:
        with pytest.raises(ValueError, match="at least one stage"):
            run_pipeline([])


class TestMeasurement:
    def test_the_digest_and_size_describe_the_bytes_the_last_stage_receives(
        self, tmp_path: Path
    ) -> None:
        payload = "measure-me" * 40
        sink = tmp_path / "out.bin"
        result = run_pipeline(
            [
                Stage(name="src", argv=("printf", "%s", payload)),
                Stage(name="sink", argv=("tee", str(sink))),
            ]
        )
        assert result.bytes_streamed == len(payload)
        assert result.checksum_sha256 == hashlib.sha256(payload.encode()).hexdigest()
        assert sink.read_bytes() == payload.encode()

    @pytest.mark.skipif(shutil.which("age") is None, reason="needs the age binary")
    def test_with_encryption_it_measures_the_ciphertext(self, tmp_path: Path) -> None:
        """Load-bearing and easy to get backwards.

        `tee` sits immediately before the upload, so it measures exactly the bytes
        the uploader writes — which is what the stored object's size can be
        compared against. A digest of the PLAINTEXT could not be checked against
        anything the backup target is able to report, and moving `tee` earlier
        would make the size read-back compare two different quantities and fail
        every time.
        """
        from src.services.backup.target import encrypt_stage

        identity = tmp_path / "id.txt"
        subprocess.run([_bin("age-keygen"), "-o", str(identity)], check=True, capture_output=True)
        recipient = subprocess.run(
            [_bin("age-keygen"), "-y", str(identity)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        payload = "secret-payload" * 50
        artifact = tmp_path / "artifact.age"
        result = run_pipeline(
            [
                Stage(name="src", argv=("printf", "%s", payload)),
                encrypt_stage(recipient),
                Stage(name="sink", argv=("tee", str(artifact))),
            ]
        )

        assert result.ok
        ciphertext = artifact.read_bytes()
        assert result.bytes_streamed == len(ciphertext)
        assert result.checksum_sha256 == hashlib.sha256(ciphertext).hexdigest()
        assert result.bytes_streamed != len(payload)  # would mean nothing encrypted

    @pytest.mark.skipif(shutil.which("age") is None, reason="needs the age binary")
    def test_the_artifact_is_real_ciphertext_and_decrypts_back(self, tmp_path: Path) -> None:
        """The property the whole encryption design rests on: a bucket-credential
        leak is not a PII leak."""
        from src.services.backup.target import encrypt_stage

        identity = tmp_path / "id.txt"
        subprocess.run([_bin("age-keygen"), "-o", str(identity)], check=True, capture_output=True)
        recipient = subprocess.run(
            [_bin("age-keygen"), "-y", str(identity)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        payload = "row-with-pii: alice@example.com"
        artifact = tmp_path / "artifact.age"
        run_pipeline(
            [
                Stage(name="src", argv=("printf", "%s", payload)),
                encrypt_stage(recipient),
                Stage(name="sink", argv=("tee", str(artifact))),
            ]
        )

        raw = artifact.read_bytes()
        assert raw.startswith(b"age-encryption.org/v1")
        assert b"alice@example.com" not in raw

        recovered = subprocess.run(
            [_bin("age"), "--decrypt", "--identity", str(identity), str(artifact)],
            check=True,
            capture_output=True,
        )
        assert recovered.stdout.decode() == payload

    def test_measurement_can_be_disabled(self) -> None:
        result = run_pipeline(
            [Stage(name="src", argv=("printf", "%s", "x")), Stage(name="sink", argv=("cat",))],
            measure=False,
        )
        assert result.ok
        assert result.checksum_sha256 is None
        assert [name for name, _ in result.stage_status] == ["src", "sink"]


class TestEnvironmentIsolation:
    def test_stage_env_reaches_the_process(self, tmp_path: Path) -> None:
        """How every credential travels. If this broke, the credential would be
        silently absent rather than loudly wrong."""
        sink = tmp_path / "env.txt"
        result = run_pipeline(
            [
                Stage(
                    name="src",
                    argv=("sh", "-c", 'printf "%s" "$BACKUP_TEST_SECRET"'),
                    env={"BACKUP_TEST_SECRET": "from-the-environment"},
                ),
                Stage(name="sink", argv=("tee", str(sink))),
            ]
        )
        assert result.ok
        assert sink.read_text() == "from-the-environment"

    def test_a_stage_env_does_not_leak_into_the_next_stage(self, tmp_path: Path) -> None:
        """PGPASSWORD belongs to pg_dump, not to the uploader."""
        sink = tmp_path / "leak.txt"
        run_pipeline(
            [
                Stage(name="src", argv=("printf", "%s", "x"), env={"BACKUP_TEST_SECRET": "s3cr3t"}),
                Stage(
                    name="sink",
                    argv=("sh", "-c", f'cat >/dev/null; printf "%s" "${{BACKUP_TEST_SECRET:-absent}}" > {sink}'),
                ),
            ]
        )
        assert sink.read_text() == "absent"
