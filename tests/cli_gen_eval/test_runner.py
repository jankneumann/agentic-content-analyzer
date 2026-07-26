"""Runner resolution and state-classification tests (ri-06 Phase 2).

Hermetic: no network, no real gen-eval install. Candidates are stub scripts written
into tmp_path, which lets us exercise the states that matter — especially BROKEN,
which is the one the sibling repository's gate could not express and therefore
reported as success.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from src.cli_gen_eval.runner import (
    ENV_BIN,
    ENV_PROJECT,
    ENV_REQUIRE,
    Candidate,
    RunnerState,
    VersionCheck,
    candidates,
    check_contract_version,
    exit_code_for,
    is_enforcing,
    load_pin,
    probe,
    resolve,
    runner_requirement,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PIN_PATH = REPO_ROOT / "evaluation" / "contract" / "pin.json"
GATE = REPO_ROOT / "scripts" / "run_gen_eval_gate.py"
GATE_SH = REPO_ROOT / "evaluation" / "run-gate.sh"


def write_stub(path: Path, body: str) -> Path:
    """Write an executable stub standing in for a runner."""
    path.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


def working_stub(path: Path, contract_version: str | None = None) -> Path:
    """A stub that answers --help, and optionally --print-contract-version."""
    version_branch = (
        f'if [ "$1" = "--print-contract-version" ]; then echo "{contract_version}"; exit 0; fi\n'
        if contract_version is not None
        else 'if [ "$1" = "--print-contract-version" ]; then exit 2; fi\n'
    )
    return write_stub(path, f'{version_branch}if [ "$1" = "--help" ]; then echo usage; exit 0; fi')


def broken_stub(path: Path) -> Path:
    """A stub that exists and is executable but fails — the upstream console script."""
    return write_stub(
        path,
        "echo \"TypeError: main() missing 1 required positional argument: 'args'\" >&2\nexit 1",
    )


@pytest.fixture
def pin() -> dict[str, Any]:
    return load_pin()


# ── Pin and invocation form ────────────────────────────────────────────────────


def test_pin_declares_the_entry_point() -> None:
    """The entry point must live in exactly one place so UP-1 migration is one edit."""
    document = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    assert document["entry_point"] in ("module", "console-script")
    assert document["entry_module"]
    assert document["entry_console_script"]


def test_entry_point_is_the_published_console_script(pin: dict[str, Any]) -> None:
    """UP-1 landed at runner ref 600744a5, so the published entry point is usable.

    Reverting to 'module' would mean routing around a published interface again, which
    is the situation UP-1 removed. If a future ref regresses the console script, the
    probe reports BROKEN — that is the mechanism, not a silent fallback here.
    """
    assert pin["entry_point"] == "console-script"


def test_entry_argv_follows_the_pin() -> None:
    """The pin is the only thing that decides the invocation form."""
    from src.cli_gen_eval.runner import _entry_argv

    assert _entry_argv({"entry_point": "console-script", "entry_console_script": "gen-eval"}) == [
        "gen-eval"
    ]
    assert _entry_argv({"entry_point": "module", "entry_module": "gen_eval"}) == [
        "python",
        "-m",
        "gen_eval",
    ]


def test_runner_requirement_is_fully_pinned(pin: dict[str, Any]) -> None:
    requirement = runner_requirement(pin)
    assert pin["runner_ref"] in requirement
    assert requirement.startswith(f"{pin['runner_package']} @ ")
    assert "subdirectory=" in requirement


def test_candidates_never_install_an_unpinned_version(pin: dict[str, Any]) -> None:
    """Every uvx candidate must carry the exact ref — no floating installs."""
    env = {"PATH": os.environ["PATH"]}
    for candidate in candidates(pin, env):
        if "uvx" in candidate.argv[0]:
            requirement = candidate.argv[candidate.argv.index("--from") + 1]
            assert pin["runner_ref"] in requirement
            assert candidate.pinned is True


# ── Enforcement flag ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["1", "true", "yes", "on"])
def test_enforcement_is_detected(value: str) -> None:
    assert is_enforcing({ENV_REQUIRE: value})


@pytest.mark.parametrize("value", ["", "0", "false", "no"])
def test_enforcement_is_off(value: str) -> None:
    assert not is_enforcing({ENV_REQUIRE: value})


def test_enforcement_defaults_off() -> None:
    assert not is_enforcing({})


# ── Resolution precedence ──────────────────────────────────────────────────────


def test_override_takes_precedence(pin: dict[str, Any], tmp_path: Path) -> None:
    stub = working_stub(tmp_path / "stub-runner")
    env = {"PATH": os.environ["PATH"], ENV_BIN: str(stub)}
    order = candidates(pin, env)
    assert order[0].origin.startswith(ENV_BIN)
    assert order[0].argv[0] == str(stub)


def test_pinned_artifact_precedes_adjacent_checkout(pin: dict[str, Any], tmp_path: Path) -> None:
    project = tmp_path / "gen-eval"
    project.mkdir()
    env = {"PATH": os.environ["PATH"], ENV_PROJECT: str(project)}
    origins = [candidate.origin for candidate in candidates(pin, env)]
    pinned_index = next(i for i, o in enumerate(origins) if o.startswith("pinned artifact"))
    adjacent = [i for i, o in enumerate(origins) if o.startswith("adjacent checkout")]
    assert adjacent, "adjacent checkout should be offered when not enforcing"
    assert pinned_index < adjacent[0]


def test_adjacent_checkout_is_excluded_under_enforcement(
    pin: dict[str, Any], tmp_path: Path
) -> None:
    """The headline D2 guarantee: CI never evaluates an unpinned adjacent checkout."""
    project = tmp_path / "gen-eval"
    project.mkdir()
    env = {
        "PATH": os.environ["PATH"],
        ENV_PROJECT: str(project),
        ENV_REQUIRE: "1",
    }
    origins = [candidate.origin for candidate in candidates(pin, env)]
    assert not [o for o in origins if o.startswith("adjacent checkout")], origins


def test_no_candidates_when_nothing_is_available(pin: dict[str, Any], tmp_path: Path) -> None:
    empty_path = tmp_path / "empty-bin"
    empty_path.mkdir()
    env = {"PATH": str(empty_path)}
    assert candidates(pin, env) == []


# ── Three-state classification ─────────────────────────────────────────────────


def test_available_when_the_override_works(pin: dict[str, Any], tmp_path: Path) -> None:
    stub = working_stub(tmp_path / "runner", contract_version=pin["contract_version"])
    env = {"PATH": os.environ["PATH"], ENV_BIN: str(stub)}
    resolution = resolve(pin=pin, env=env)
    assert resolution.state is RunnerState.AVAILABLE
    assert resolution.version_check is VersionCheck.MATCH
    assert resolution.ok


def test_absent_when_no_candidate_exists(pin: dict[str, Any], tmp_path: Path) -> None:
    empty_path = tmp_path / "empty-bin"
    empty_path.mkdir()
    resolution = resolve(pin=pin, env={"PATH": str(empty_path)})
    assert resolution.state is RunnerState.ABSENT
    assert exit_code_for(resolution, enforcing=False) == 0
    assert exit_code_for(resolution, enforcing=True) == 3


def test_broken_runner_is_never_reported_as_absent(pin: dict[str, Any], tmp_path: Path) -> None:
    """The defect this whole design exists to prevent.

    A stub reproducing the real upstream failure — present, executable, exits 1 with a
    TypeError — must classify BROKEN, not ABSENT, and must be fatal even with no
    enforcement set.
    """
    stub = broken_stub(tmp_path / "runner")
    env = {"PATH": os.environ["PATH"], ENV_BIN: str(stub)}
    resolution = resolve(pin=pin, env=env)

    assert resolution.state is RunnerState.BROKEN
    assert resolution.state is not RunnerState.ABSENT
    assert exit_code_for(resolution, enforcing=False) == 3
    assert exit_code_for(resolution, enforcing=True) == 3
    assert "TypeError" in resolution.detail or "exited 1" in resolution.detail


def test_broken_candidate_does_not_fall_through_to_the_next(
    pin: dict[str, Any], tmp_path: Path
) -> None:
    """A broken high-precedence candidate must not be silently replaced by a working one.

    Falling through would make a misconfigured override invisible — the gate would pass
    while evaluating something other than what the operator asked for.
    """
    stub = broken_stub(tmp_path / "runner")
    env = {"PATH": os.environ["PATH"], ENV_BIN: str(stub)}
    resolution = resolve(pin=pin, env=env)
    assert resolution.state is RunnerState.BROKEN
    assert len(resolution.attempted) == 1, resolution.attempted


def test_nonexistent_override_is_broken_not_absent(pin: dict[str, Any], tmp_path: Path) -> None:
    """An override naming a missing file is a misconfiguration, not an absence."""
    env = {"PATH": os.environ["PATH"], ENV_BIN: str(tmp_path / "not-here")}
    resolution = resolve(pin=pin, env=env)
    assert resolution.state is RunnerState.BROKEN


def test_probe_reports_failure_detail(tmp_path: Path) -> None:
    candidate = Candidate(origin="test", argv=[str(broken_stub(tmp_path / "runner"))])
    usable, detail = probe(candidate)
    assert not usable
    assert "exited 1" in detail


def test_probe_accepts_a_working_runner(tmp_path: Path) -> None:
    candidate = Candidate(origin="test", argv=[str(working_stub(tmp_path / "runner"))])
    usable, detail = probe(candidate)
    assert usable, detail


# ── Contract-version handshake ─────────────────────────────────────────────────


def test_version_mismatch_is_broken(pin: dict[str, Any], tmp_path: Path) -> None:
    stub = working_stub(tmp_path / "runner", contract_version="999")
    env = {"PATH": os.environ["PATH"], ENV_BIN: str(stub)}
    resolution = resolve(pin=pin, env=env)
    assert resolution.state is RunnerState.BROKEN
    assert resolution.version_check is VersionCheck.MISMATCH
    assert "999" in resolution.detail
    assert str(pin["contract_version"]) in resolution.detail


def test_pinned_candidate_is_verified_by_construction(pin: dict[str, Any], tmp_path: Path) -> None:
    """Until UP-2 ships --print-contract-version, the pinned ref is the proof."""
    candidate = Candidate(
        origin="pinned artifact",
        argv=[str(working_stub(tmp_path / "runner"))],
        pinned=True,
    )
    check, detail = check_contract_version(candidate, pin)
    assert check is VersionCheck.MATCH
    assert "by construction" in detail


def test_unpinned_runner_without_version_support_is_unverifiable(
    pin: dict[str, Any], tmp_path: Path
) -> None:
    candidate = Candidate(origin="override", argv=[str(working_stub(tmp_path / "runner"))])
    check, _ = check_contract_version(candidate, pin)
    assert check is VersionCheck.UNVERIFIABLE


def test_unverifiable_runner_is_refused_under_enforcement(
    pin: dict[str, Any], tmp_path: Path
) -> None:
    """CI must not evaluate against a runner whose contract version is unknown."""
    stub = working_stub(tmp_path / "runner")
    env = {"PATH": os.environ["PATH"], ENV_BIN: str(stub), ENV_REQUIRE: "1"}
    resolution = resolve(pin=pin, env=env)
    assert resolution.state is RunnerState.BROKEN
    assert resolution.version_check is VersionCheck.UNVERIFIABLE


def test_unverifiable_runner_is_tolerated_locally(pin: dict[str, Any], tmp_path: Path) -> None:
    stub = working_stub(tmp_path / "runner")
    env = {"PATH": os.environ["PATH"], ENV_BIN: str(stub)}
    resolution = resolve(pin=pin, env=env)
    assert resolution.state is RunnerState.AVAILABLE
    assert resolution.version_check is VersionCheck.UNVERIFIABLE


# ── Gate integration ───────────────────────────────────────────────────────────


def run_gate(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT), **env},
        check=False,
    )


def test_gate_runs_contract_validation_before_resolving(tmp_path: Path) -> None:
    """Contract validation must run even when the runner turns out to be broken."""
    stub = broken_stub(tmp_path / "runner")
    completed = run_gate(
        ["--resolve-only"],
        {"PATH": os.environ["PATH"], ENV_BIN: str(stub)},
    )
    assert completed.returncode == 3
    assert "gen-eval contract: VALID" in completed.stdout
    assert "BROKEN" in completed.stderr


def test_gate_skips_advisorily_when_runner_absent_locally(tmp_path: Path) -> None:
    empty_path = tmp_path / "empty-bin"
    empty_path.mkdir()
    completed = run_gate(["--resolve-only"], {"PATH": str(empty_path)})
    assert completed.returncode == 0
    assert "ABSENT" in completed.stderr
    assert "gen-eval contract: VALID" in completed.stdout


def test_gate_fails_when_runner_absent_under_enforcement(tmp_path: Path) -> None:
    empty_path = tmp_path / "empty-bin"
    empty_path.mkdir()
    completed = run_gate(
        ["--resolve-only"],
        {"PATH": str(empty_path), ENV_REQUIRE: "1"},
    )
    assert completed.returncode == 3
    assert "ABSENT" in completed.stderr


def test_gate_refuses_skip_contract_under_enforcement(tmp_path: Path) -> None:
    stub = working_stub(tmp_path / "runner")
    completed = run_gate(
        ["--resolve-only", "--skip-contract"],
        {"PATH": os.environ["PATH"], ENV_BIN: str(stub), ENV_REQUIRE: "1"},
    )
    assert completed.returncode == 2


def test_gate_refuses_mutating_categories_before_phase_5(tmp_path: Path) -> None:
    """No durable work may be submitted before the target guard exists."""
    stub = working_stub(tmp_path / "runner", contract_version="1")
    completed = run_gate(
        ["--categories", "workflow-submission"],
        {"PATH": os.environ["PATH"], ENV_BIN: str(stub)},
    )
    assert completed.returncode == 2
    assert "workflow-submission" in completed.stderr


def test_gate_diagnostics_stay_on_stderr(tmp_path: Path) -> None:
    """stdout belongs to the runner and the contract validator, not the gate."""
    stub = working_stub(tmp_path / "runner", contract_version="1")
    completed = run_gate(
        ["--resolve-only"],
        {"PATH": os.environ["PATH"], ENV_BIN: str(stub)},
    )
    assert completed.returncode == 0
    assert "gen-eval gate:" not in completed.stdout


def test_wrapper_script_is_executable() -> None:
    assert GATE_SH.exists()
    assert GATE_SH.stat().st_mode & stat.S_IXUSR, "run-gate.sh must be executable"
