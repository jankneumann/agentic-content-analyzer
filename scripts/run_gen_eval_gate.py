#!/usr/bin/env python3
"""Run the CLI gen-eval gate: contract validation, then the evaluation suite.

Ordering is deliberate. Contract validation (Phase 1) runs first and always, with no
runner required, so a failed runner acquisition reduces coverage *visibly* rather than
turning the gate green. Only then is a runner resolved and the suite executed.

Exit codes:
    0  contract valid, and either the suite passed or the runner is absent locally
    1  contract invalid, or the suite failed
    2  usage error (argparse)
    3  runner is broken, or absent while ACA_GEN_EVAL_REQUIRE is set
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.cli_gen_eval.contract import MUTATING_CATEGORIES, READ_ONLY_CATEGORIES  # noqa: E402
from src.cli_gen_eval.runner import (  # noqa: E402
    ENV_REQUIRE,
    RunnerState,
    exit_code_for,
    is_enforcing,
    load_pin,
    resolve,
)

DEFAULT_DESCRIPTOR = REPO_ROOT / "evaluation" / "descriptors" / "aca-cli.yaml"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "evaluation" / "reports"
CONTRACT_VALIDATOR = REPO_ROOT / "scripts" / "validate_gen_eval_contract.py"


def emit(message: str) -> None:
    """Gate diagnostics go to stderr, keeping stdout free for runner output."""
    print(f"gen-eval gate: {message}", file=sys.stderr)


def run_contract_validation(descriptor: Path) -> int:
    completed = subprocess.run(
        [sys.executable, str(CONTRACT_VALIDATOR), "--descriptor", str(descriptor)],
        cwd=REPO_ROOT,
        check=False,
    )
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--descriptor", type=Path, default=DEFAULT_DESCRIPTOR)
    parser.add_argument(
        "--categories",
        nargs="*",
        default=None,
        help=(
            "Scenario categories to run. Defaults to the read-only categories "
            f"({', '.join(sorted(READ_ONLY_CATEGORIES))}); mutating categories "
            f"({', '.join(sorted(MUTATING_CATEGORIES))}) must be named explicitly."
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--fail-threshold", type=float, default=0.95)
    parser.add_argument(
        "--resolve-only",
        action="store_true",
        help="Report the runner state and exit without executing the suite.",
    )
    parser.add_argument(
        "--skip-contract",
        action="store_true",
        help="Skip contract validation. For debugging the runner path only; never in CI.",
    )
    args = parser.parse_args()

    enforcing = is_enforcing()

    # 1. Contract layer — unconditional, runner-independent.
    if not args.skip_contract:
        contract_status = run_contract_validation(args.descriptor)
        if contract_status != 0:
            emit("contract validation FAILED — not running the suite")
            return 1
    elif enforcing:
        emit(f"--skip-contract is refused while {ENV_REQUIRE} is set")
        return 2

    # 2. Runner resolution.
    pin = load_pin()
    resolution = resolve(pin=pin)

    for attempt in resolution.attempted:
        emit(f"tried {attempt}")

    if resolution.state is RunnerState.BROKEN:
        emit(f"BROKEN — {resolution.detail}")
        emit("a present-but-unusable runner is fatal regardless of enforcement")
        return exit_code_for(resolution, enforcing)

    if resolution.state is RunnerState.ABSENT:
        if enforcing:
            emit(f"ABSENT — {resolution.detail}")
            emit(f"{ENV_REQUIRE} is set, so an absent runner is fatal")
            return exit_code_for(resolution, enforcing)
        emit(f"ABSENT — {resolution.detail}")
        emit("skipping the suite; contract validation already ran and passed")
        return 0

    assert resolution.candidate is not None
    emit(f"AVAILABLE via {resolution.candidate.origin} — {resolution.detail}")

    if args.resolve_only:
        return 0

    # 3. Execute the suite.
    categories = args.categories if args.categories is not None else sorted(READ_ONLY_CATEGORIES)
    selected_mutating = sorted(set(categories) & MUTATING_CATEGORIES)
    if selected_mutating:
        # Phase 5 installs the real target-policy guard here. Until then, refuse
        # rather than submit durable work with no production check in place.
        emit(
            f"mutating categories {selected_mutating} require the non-production target "
            "guard, which is not implemented yet (Phase 5)"
        )
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    argv = [
        *resolution.candidate.argv,
        "--descriptor",
        str(args.descriptor),
        "--mode",
        "template-only",
        "--no-services",
        "--report-format",
        "both",
        "--output-dir",
        str(args.output_dir),
        "--fail-threshold",
        str(args.fail_threshold),
        "--categories",
        *categories,
    ]
    emit(f"running categories {categories}")
    completed = subprocess.run(argv, cwd=REPO_ROOT, check=False, env=os.environ.copy())
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
