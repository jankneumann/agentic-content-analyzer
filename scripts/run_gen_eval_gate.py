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
    4  the backend target the selected categories need is unreachable
    5  the run finished but its report is not credible

Codes 1 and 5 are kept apart on purpose. Exit 1 means `aca` failed a scenario, which is
a defect in the product. Exit 5 means the report cannot be used to decide either way —
scenarios silently dropped, coverage missing, a self-inconsistent artifact. Collapsing
them would hide the second behind the first, and the second is the failure mode this
whole change exists to remove.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.cli_gen_eval.contract import MUTATING_CATEGORIES, READ_ONLY_CATEGORIES  # noqa: E402
from src.cli_gen_eval.report import (  # noqa: E402
    Severity,
    expectation_from,
    load_json,
    validate as validate_report,
)
from src.cli_gen_eval.runner import (  # noqa: E402
    ENV_REQUIRE,
    RunnerState,
    exit_code_for,
    is_enforcing,
    load_pin,
    resolve,
)
from src.cli_gen_eval.selection import materialize, select  # noqa: E402
from src.cli_gen_eval.target import (  # noqa: E402
    NO_TARGET_TAG,
    TargetState,
    resolve as resolve_target,
)

EXIT_TARGET_UNREACHABLE = 4
EXIT_REPORT_NOT_CREDIBLE = 5
SCENARIO_ROOT = REPO_ROOT / "evaluation" / "scenarios"

DEFAULT_DESCRIPTOR = REPO_ROOT / "evaluation" / "descriptors" / "aca-cli.yaml"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "evaluation" / "reports"
CONTRACT_VALIDATOR = REPO_ROOT / "scripts" / "validate_gen_eval_contract.py"
REPORT_NAME = "gen-eval-report.json"
EXPECTATION_NAME = "gen-eval-expectation.json"


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
    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Run only the scenarios that need no backend, naming the coverage that is "
            "being given up. An explicit, reported reduction — not a skip. Refused "
            f"while {ENV_REQUIRE} is set."
        ),
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

    # 4. Selection. The runner's own --categories flag is inert (see
    #    src/cli_gen_eval/selection.py), so the gate resolves the selection itself and
    #    hands the runner a descriptor that points at exactly those scenarios. Without
    #    this, every run evaluates everything on disk regardless of what was asked for.
    require_tags: set[str] | None = None
    if args.offline:
        if enforcing:
            emit(f"--offline is refused while {ENV_REQUIRE} is set")
            return 2
        require_tags = {NO_TARGET_TAG}

    selected = select(SCENARIO_ROOT, categories=set(categories), require_tags=require_tags)
    if not selected:
        emit(f"selection {categories} with tags {require_tags or 'none'} matched no scenarios")
        emit("refusing to report a pass rate over an empty suite")
        return 1

    if args.offline:
        dropped = sorted(
            {
                s.category
                for s in select(SCENARIO_ROOT, categories=set(categories))
                if NO_TARGET_TAG not in s.tags
            }
        )
        emit(
            f"--offline: selected {len(selected)} scenarios tagged {NO_TARGET_TAG!r}, "
            f"giving up the backend-dependent coverage in {dropped}"
        )
    else:
        # 5. Target resolution — the same three states as the runner, and the same refusal
        #    to treat a missing prerequisite as success.
        target = resolve_target()
        if target.state is TargetState.REACHABLE:
            emit(f"target REACHABLE — {target.detail}")
        else:
            emit(f"target {target.state.value.upper()} — {target.detail}")
            emit(
                "the selection includes scenarios against the canonical workflow "
                "surface, which is HTTP-only: there is no --direct path for "
                "capabilities, configured-sources, or operations list"
            )
            emit(
                "start a backend (make dev-bg), or pass --offline to run the hermetic "
                "subset with the dropped coverage named"
            )
            return EXIT_TARGET_UNREACHABLE

    args.output_dir.mkdir(parents=True, exist_ok=True)
    descriptor_document = yaml.safe_load(args.descriptor.read_text(encoding="utf-8"))
    run_descriptor = materialize(selected, descriptor_document, args.output_dir)

    # 6. Record what this run was asked to do, before it is asked to do it. A report
    #    cannot say whether it is complete — completeness is a fact about the request —
    #    so the expectation is written alongside it and published as evidence with it.
    expectation = expectation_from(
        [item.template for item in selected],
        descriptor_document,
        categories=list(categories),
        offline=args.offline,
    )
    expectation_path = args.output_dir / EXPECTATION_NAME
    expectation_path.write_text(
        json.dumps(expectation.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    argv = [
        *resolution.candidate.argv,
        "--descriptor",
        str(run_descriptor),
        "--mode",
        "template-only",
        "--no-services",
        "--report-format",
        "both",
        "--output-dir",
        str(args.output_dir),
        "--fail-threshold",
        str(args.fail_threshold),
    ]
    by_category: dict[str, int] = {}
    for item in selected:
        by_category[item.category] = by_category.get(item.category, 0) + 1
    emit(f"running {len(selected)} scenarios: {by_category}")
    completed = subprocess.run(argv, cwd=REPO_ROOT, check=False, env=os.environ.copy())

    # 7. Validate the report the run produced. This runs whether or not the runner
    #    reported success, because the interesting case is precisely the one where it
    #    reported success over work it silently dropped — the runner's own exit code
    #    cannot detect that, having been computed from the reduced set.
    report_path = args.output_dir / REPORT_NAME
    document, load_error = load_json(report_path)
    if load_error is not None:
        emit(f"report is unusable — {load_error}")
        if completed.returncode != 0:
            emit("the runner also exited non-zero; reporting that failure")
            return completed.returncode
        return EXIT_REPORT_NOT_CREDIBLE

    verdict = validate_report(document, expectation, fail_threshold=args.fail_threshold)
    for message in verdict.messages(Severity.CREDIBILITY):
        emit(f"report: {message}")
    for message in verdict.messages(Severity.THRESHOLD):
        emit(f"threshold: {message}")

    if not verdict.credible:
        emit(
            f"report REJECTED — {len(verdict.messages(Severity.CREDIBILITY))} credibility findings"
        )
        emit("the pass rate above describes a run that did not do what it was asked to do")
        return EXIT_REPORT_NOT_CREDIBLE

    if completed.returncode != 0 or not verdict.ok:
        return completed.returncode or 1

    emit(
        f"report VALID — {expectation.total_scenarios} scenarios selected and evaluated, "
        f"{len(expectation.interfaces)} interfaces covered"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
