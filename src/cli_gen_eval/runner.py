"""Resolution and state classification for the external gen-eval runner.

The runner is an *artifact*, not a dependency (``establish-cli-gen-eval-coverage``
D2). This module decides which runner to invoke, proves it is usable, and — crucially
— distinguishes "no runner here" from "a runner that does not work".

That distinction is the whole point. A gate with only two states, works and
unavailable, has no way to express *present but wrong*, so every novel failure lands
in the benign bucket and the gate reports green forever. That is exactly what happened
to the sibling repository's evaluation gate: its probe invoked the upstream-broken
console script, the crash was read as "stub checkout", and it exited 0 without ever
evaluating anything. Hence three states, with ``BROKEN`` fatal everywhere.

Nothing here imports gen_eval. The runner is only ever reached through a subprocess.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
PIN_PATH = REPO_ROOT / "evaluation" / "contract" / "pin.json"

#: Explicit operator override. Highest precedence. A full command line.
ENV_BIN = "ACA_GEN_EVAL_BIN"
#: When set to a truthy value, absence becomes fatal and unverifiable runners are
#: refused. CI always sets this.
ENV_REQUIRE = "ACA_GEN_EVAL_REQUIRE"
#: Developer-convenience adjacent checkout. Never consulted under enforcement.
ENV_PROJECT = "ACA_GEN_EVAL_PROJECT"

DEFAULT_SIBLING = REPO_ROOT.parent / "agentic-coding-tools" / "packages" / "gen-eval"

PROBE_TIMEOUT_SECONDS = 300


class RunnerState(StrEnum):
    """Outcome of resolving and probing a runner."""

    AVAILABLE = "available"
    ABSENT = "absent"
    BROKEN = "broken"


class VersionCheck(StrEnum):
    """Result of the contract-version handshake."""

    MATCH = "match"
    MISMATCH = "mismatch"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True)
class Candidate:
    """One possible way to invoke the runner."""

    origin: str
    argv: list[str]
    #: True when the contract version is guaranteed by construction — the pinned
    #: artifact is installed from the exact ref the schemas were generated from.
    pinned: bool = False

    def display(self) -> str:
        return shlex.join(self.argv)


@dataclass
class Resolution:
    """What resolution decided, and why."""

    state: RunnerState
    candidate: Candidate | None = None
    version_check: VersionCheck = VersionCheck.UNVERIFIABLE
    attempted: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.state is RunnerState.AVAILABLE


def is_enforcing(env: Mapping[str, str] | None = None) -> bool:
    """Whether absence is fatal. Any non-empty value other than 0/false enforces."""
    environ = os.environ if env is None else env
    raw = (environ.get(ENV_REQUIRE) or "").strip().lower()
    return raw not in ("", "0", "false", "no")


def load_pin(path: Path = PIN_PATH) -> dict[str, Any]:
    pin: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return pin


def runner_requirement(pin: dict[str, Any]) -> str:
    """PEP 508 requirement for the pinned runner artifact."""
    return (
        f"{pin['runner_package']} @ {pin['runner_source']}"
        f"@{pin['runner_ref']}#subdirectory={pin['runner_subdirectory']}"
    )


def _entry_argv(pin: dict[str, Any]) -> list[str]:
    """How the runner is invoked, from the single declared location in the pin.

    ``entry_point`` is ``module`` while the upstream console script is broken
    (UPSTREAM.md UP-1). Flipping it to ``console-script`` is the entire migration.
    """
    if pin.get("entry_point") == "console-script":
        return [str(pin["entry_console_script"])]
    return ["python", "-m", str(pin.get("entry_module", "gen_eval"))]


def candidates(
    pin: dict[str, Any],
    env: Mapping[str, str] | None = None,
) -> list[Candidate]:
    """Build the resolution precedence list.

    Order: explicit override, pinned artifact, adjacent checkout. The adjacent
    checkout is omitted entirely under enforcement — it is a developer convenience and
    must never be what CI silently evaluates against.
    """
    environ = os.environ if env is None else env
    enforcing = is_enforcing(environ)
    found: list[Candidate] = []

    # shutil.which() reads os.environ["PATH"] unless told otherwise. Honour the caller's
    # environment instead, or a caller passing a restricted env silently gets the
    # ambient PATH — which would make resolution untestable and, worse, make a
    # deliberately constrained CI environment resolve tools it was denied.
    search_path = environ.get("PATH")

    override = (environ.get(ENV_BIN) or "").strip()
    if override:
        found.append(Candidate(origin=f"{ENV_BIN} override", argv=shlex.split(override)))

    uvx = shutil.which("uvx", path=search_path)
    if uvx is not None:
        found.append(
            Candidate(
                origin=f"pinned artifact {pin['runner_ref'][:12]}",
                argv=[uvx, "--from", runner_requirement(pin), *_entry_argv(pin)],
                pinned=True,
            )
        )

    if not enforcing:
        raw_project = (environ.get(ENV_PROJECT) or "").strip()
        project = Path(raw_project) if raw_project else DEFAULT_SIBLING
        uv = shutil.which("uv", path=search_path)
        if uv is not None and project.is_dir():
            found.append(
                Candidate(
                    origin=f"adjacent checkout {project}",
                    argv=[uv, "run", "--project", str(project), *_entry_argv(pin)],
                )
            )

    return found


def probe(candidate: Candidate, timeout: int = PROBE_TIMEOUT_SECONDS) -> tuple[bool, str]:
    """Run ``<candidate> --help`` and report whether it is usable.

    A non-zero exit, a crash, or a timeout all mean BROKEN — never ABSENT. The only
    way to be absent is for no candidate to exist at all.
    """
    try:
        completed = subprocess.run(
            [*candidate.argv, "--help"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=REPO_ROOT,
            check=False,
        )
    except FileNotFoundError as exc:
        return False, f"executable not found: {exc}"
    except subprocess.TimeoutExpired:
        return False, f"probe timed out after {timeout}s"
    except OSError as exc:
        return False, f"probe failed: {exc}"

    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()
        excerpt = tail[-1] if tail else "<no output>"
        return False, f"probe exited {completed.returncode}: {excerpt}"
    return True, "probe ok"


def check_contract_version(
    candidate: Candidate,
    pin: dict[str, Any],
    timeout: int = PROBE_TIMEOUT_SECONDS,
) -> tuple[VersionCheck, str]:
    """Compare the runner's contract version against the pin.

    ``--print-contract-version`` does not exist upstream yet (UPSTREAM.md UP-2). Until
    it does, a pinned candidate is verified *by construction* — it is installed from
    the exact ref the vendored schemas were generated from. Anything else is
    unverifiable, which is tolerable locally and refused under enforcement.
    """
    try:
        completed = subprocess.run(
            [*candidate.argv, "--print-contract-version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=REPO_ROOT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        completed = None
        detail = f"version probe failed: {exc}"
    else:
        detail = ""

    if completed is not None and completed.returncode == 0:
        reported = (completed.stdout or "").strip()
        expected = str(pin["contract_version"])
        if reported == expected:
            return VersionCheck.MATCH, f"runner reports contract version {reported}"
        return (
            VersionCheck.MISMATCH,
            f"runner reports contract version {reported!r} but the pin is {expected!r}",
        )

    if candidate.pinned:
        return (
            VersionCheck.MATCH,
            (
                f"contract version {pin['contract_version']} verified by construction "
                f"(installed from pinned ref {pin['runner_ref'][:12]})"
            ),
        )

    return (
        VersionCheck.UNVERIFIABLE,
        detail
        or (
            "runner does not support --print-contract-version and is not the pinned "
            "artifact, so its contract version cannot be established"
        ),
    )


def resolve(
    pin: dict[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
    timeout: int = PROBE_TIMEOUT_SECONDS,
) -> Resolution:
    """Resolve a usable runner, or explain precisely why there is not one."""
    resolved_pin = load_pin() if pin is None else pin
    environ = os.environ if env is None else env
    enforcing = is_enforcing(environ)

    options = candidates(resolved_pin, environ)
    if not options:
        return Resolution(
            state=RunnerState.ABSENT,
            attempted=[],
            detail=(
                "no runner candidate exists: no "
                f"{ENV_BIN} override, uvx is not on PATH, and no adjacent checkout is "
                "usable"
                + (" (adjacent checkouts are ignored under enforcement)" if enforcing else "")
            ),
        )

    attempted: list[str] = []
    for candidate in options:
        attempted.append(f"{candidate.origin}: {candidate.display()}")
        usable, detail = probe(candidate, timeout=timeout)
        if not usable:
            # A candidate that exists but does not work is fatal. Falling through to
            # the next candidate here would be how a broken runner silently becomes a
            # skip — the precise failure this design exists to prevent.
            return Resolution(
                state=RunnerState.BROKEN,
                candidate=candidate,
                attempted=attempted,
                detail=f"{candidate.origin} is present but unusable — {detail}",
            )

        version_check, version_detail = check_contract_version(
            candidate, resolved_pin, timeout=timeout
        )
        if version_check is VersionCheck.MISMATCH:
            return Resolution(
                state=RunnerState.BROKEN,
                candidate=candidate,
                version_check=version_check,
                attempted=attempted,
                detail=version_detail,
            )
        if version_check is VersionCheck.UNVERIFIABLE and enforcing:
            return Resolution(
                state=RunnerState.BROKEN,
                candidate=candidate,
                version_check=version_check,
                attempted=attempted,
                detail=(
                    f"{version_detail}; refusing to run an unverified runner under {ENV_REQUIRE}"
                ),
            )

        return Resolution(
            state=RunnerState.AVAILABLE,
            candidate=candidate,
            version_check=version_check,
            attempted=attempted,
            detail=version_detail,
        )

    return Resolution(state=RunnerState.ABSENT, attempted=attempted, detail="no usable runner")


def exit_code_for(resolution: Resolution, enforcing: bool) -> int:
    """Map a resolution onto a process exit status.

    0 for available, and for absence only when not enforcing. BROKEN is always
    non-zero: there is no configuration in which a present-but-unusable runner is
    acceptable.
    """
    if resolution.state is RunnerState.AVAILABLE:
        return 0
    if resolution.state is RunnerState.ABSENT:
        return 3 if enforcing else 0
    return 3
