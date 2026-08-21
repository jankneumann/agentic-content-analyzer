"""Subprocess execution for the backup pipeline.

Two seams, and only two, so every network- and disk-touching call in this package
is mockable from a unit test (Hard Constraint 1):

* :func:`run_command` — one process, used for preflight, size read-back, listing.
* :func:`run_pipeline` — a chain of processes, used for every store artifact.

Why a chain rather than ``sh -c 'a | b | c'``:

A shell pipeline reports the exit status of its **last** stage. ``pg_dump`` failing
halfway still yields zero from ``rclone`` — so a truncated ciphertext uploads and
the manifest records it as succeeded. That is precisely the silent-success failure
this change exists to eliminate, so every stage's status is collected and checked
here (design A6.1). ``set -o pipefail`` would also work, but only under a shell,
and putting these argv through a shell is how credentials end up in a process
listing.

The bytes never pass through the interpreter. The digest and the byte count are
produced by ``sha256sum`` and ``wc -c`` reading FIFOs fed by ``tee`` inside the
same pipeline (design A7), so a multi-GB dump streams host-side from start to
finish.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from src.utils.logging import get_logger

logger = get_logger(__name__)

#: Bound on how long one stage may run before the pipeline is abandoned.
DEFAULT_STAGE_TIMEOUT_SECONDS = 3600


@dataclass(frozen=True)
class Stage:
    """One process in a pipeline.

    ``env`` carries anything secret. Nothing secret may appear in ``argv``: argv is
    world-readable in ``/proc`` on the host, so a credential there leaks to every
    local user for the lifetime of the process.
    """

    name: str
    argv: tuple[str, ...]
    env: Mapping[str, str] = field(default_factory=dict)

    @property
    def program(self) -> str:
        return self.argv[0]


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    #: Populated only by ``binary=True`` calls. Ciphertext is not text: decoding it
    #: as UTF-8 either raises or mangles it, and re-encoding the result does not
    #: reproduce the original bytes.
    stdout_bytes: bytes = b""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class PipelineResult:
    """Outcome of one pipeline, with EVERY stage's status retained."""

    stage_status: tuple[tuple[str, int], ...]
    bytes_streamed: int | None = None
    checksum_sha256: str | None = None

    @property
    def ok(self) -> bool:
        return all(code == 0 for _, code in self.stage_status)

    @property
    def failed_stages(self) -> tuple[str, ...]:
        return tuple(name for name, code in self.stage_status if code != 0)


def _merged_env(extra: Mapping[str, str] | None) -> dict[str, str]:
    env = dict(os.environ)
    if extra:
        env.update(extra)
    return env


def run_command(
    argv: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    timeout: int = DEFAULT_STAGE_TIMEOUT_SECONDS,
    stdin_text: str | None = None,
    stdin_bytes: bytes | None = None,
    binary: bool = False,
) -> CommandResult:
    """Run one process and capture its output.

    ``binary=True`` is not a convenience. ``age`` writes raw binary ciphertext
    unless asked for armour, and ``text=True`` decodes stdout as strict UTF-8 —
    so reading a canary back through the text path raises ``UnicodeDecodeError``
    on the happy path, and any ciphertext that did happen to decode would not
    survive being re-encoded on the way into the next process. Anything carrying
    an encrypted artifact must use this mode.
    """
    if binary or stdin_bytes is not None:
        completed_bytes = subprocess.run(
            list(argv),
            capture_output=True,
            env=_merged_env(env),
            timeout=timeout,
            input=stdin_bytes,
            check=False,
        )
        return CommandResult(
            argv=tuple(argv),
            returncode=completed_bytes.returncode,
            stdout="",
            stderr=(completed_bytes.stderr or b"").decode("utf-8", "replace"),
            stdout_bytes=completed_bytes.stdout or b"",
        )
    completed = subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        env=_merged_env(env),
        timeout=timeout,
        input=stdin_text,
        check=False,
    )
    return CommandResult(
        argv=tuple(argv),
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def run_pipeline(
    stages: Sequence[Stage],
    *,
    measure: bool = True,
    timeout: int = DEFAULT_STAGE_TIMEOUT_SECONDS,
) -> PipelineResult:
    """Run ``stages`` as a chain, returning every stage's exit status.

    When ``measure`` is true a ``tee`` stage is spliced in before the final stage,
    feeding two FIFOs consumed by ``sha256sum`` and ``wc -c``. The measurement
    processes are peers of the pipeline, not stages of it: if either fails, the
    result carries no digest and the caller treats the store as failed rather than
    recording an artifact it cannot verify.

    **The digest and byte count describe the CIPHERTEXT, not the source data.**
    ``tee`` sits immediately before the upload, so it measures exactly the bytes
    the uploader writes. That is deliberate and load-bearing: the size read-back
    compares this count against the stored object's size, and a digest of the
    plaintext could not be checked against anything the target can report. Do not
    "fix" this by moving ``tee`` earlier — it would make the read-back compare two
    different quantities and always fail.
    """
    if not stages:
        raise ValueError("a pipeline needs at least one stage")

    with tempfile.TemporaryDirectory(prefix="aca-backup-") as tmp:
        tmpdir = Path(tmp)
        digest_fifo = tmpdir / "digest.fifo"
        size_fifo = tmpdir / "size.fifo"
        effective: list[Stage] = list(stages)
        sidecars: list[tuple[str, subprocess.Popen[bytes]]] = []

        if measure:
            os.mkfifo(digest_fifo)
            os.mkfifo(size_fifo)
            effective.insert(
                len(effective) - 1,
                Stage(
                    name="tee",
                    argv=("tee", str(digest_fifo), str(size_fifo)),
                ),
            )

        procs: list[tuple[str, subprocess.Popen[bytes]]] = []
        try:
            if measure:
                # Started BEFORE the pipeline: opening a FIFO blocks until both
                # ends are open, so `tee` would deadlock with no reader waiting.
                for label, argv in (
                    ("sha256sum", ("sha256sum", str(digest_fifo))),
                    ("wc", ("wc", "-c", str(size_fifo))),
                ):
                    sidecars.append(
                        (
                            label,
                            subprocess.Popen(
                                list(argv),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                            ),
                        )
                    )

            upstream: subprocess.Popen[bytes] | None = None
            for index, stage in enumerate(effective):
                is_last = index == len(effective) - 1
                proc = subprocess.Popen(
                    list(stage.argv),
                    stdin=upstream.stdout if upstream is not None else None,
                    stdout=None if is_last else subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=_merged_env(stage.env),
                )
                if upstream is not None and upstream.stdout is not None:
                    # Drop the parent's copy of the read end once the child holds
                    # it, so the upstream stage sees EPIPE if this one dies rather
                    # than blocking forever on a pipe nobody is draining.
                    upstream.stdout.close()
                procs.append((stage.name, proc))
                upstream = proc

            statuses: list[tuple[str, int]] = []
            for name, proc in procs:
                try:
                    _, stderr = proc.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                    statuses.append((name, 124))
                    continue
                if proc.returncode != 0:
                    # stderr can echo a connection string, so it is logged at debug
                    # and never travels into the manifest or the CLI result.
                    logger.debug(
                        "backup pipeline stage %s exited %s: %s",
                        name,
                        proc.returncode,
                        (stderr or b"").decode("utf-8", "replace")[:400],
                    )
                statuses.append((name, proc.returncode))

            checksum: str | None = None
            size: int | None = None
            for label, proc in sidecars:
                stdout, _ = proc.communicate(timeout=timeout)
                if proc.returncode != 0:
                    statuses.append((label, proc.returncode))
                    continue
                text = (stdout or b"").decode("utf-8", "replace").strip()
                if label == "sha256sum":
                    checksum = text.split()[0] if text else None
                else:
                    size = int(text.split()[0]) if text else None

            return PipelineResult(
                stage_status=tuple(statuses),
                bytes_streamed=size,
                checksum_sha256=checksum,
            )
        finally:
            for _, proc in [*procs, *sidecars]:
                if proc.poll() is None:
                    proc.kill()
