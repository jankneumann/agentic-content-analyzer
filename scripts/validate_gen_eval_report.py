#!/usr/bin/env python3
"""Validate a gen-eval evaluation report, then apply the pass-rate threshold.

The gate already runs these checks in-process on every run, so this script is not the
enforcement path — it is how a *retained* report is re-checked away from the run that
produced it: a CI artifact downloaded into a later job, a report attached to a bug, a
run whose logs have rolled off. Keeping one implementation in
``src/cli_gen_eval/report.py`` and two callers is deliberate; a second copy of the rules
here would be free to disagree with the gate.

Credibility is decided before the threshold and reported separately, because the two
answers go to different people. A pass rate below the threshold means `aca` regressed. A
report that dropped scenarios, lost coverage, or contradicts itself means nobody can
tell whether `aca` regressed — and that verdict is not improved by the pass rate being
high.

Usage:
    validate_gen_eval_report.py REPORT --expectation EXPECTATION
    validate_gen_eval_report.py REPORT --no-expectation   # reduced, and says so

Exit codes:
    0  the report is credible and meets the threshold
    1  the report is credible but the pass rate is below the threshold
    2  usage error
    5  the report is not credible — the pass rate cannot be believed either way
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.cli_gen_eval.report import (  # noqa: E402
    Expectation,
    Severity,
    load_json,
    validate,
)

EXIT_THRESHOLD = 1
EXIT_USAGE = 2
EXIT_NOT_CREDIBLE = 5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="The gen-eval JSON report to validate.")
    parser.add_argument(
        "--expectation",
        type=Path,
        default=None,
        help=(
            "The expectation document the gate wrote next to the report. Without it, "
            "completeness cannot be checked at all."
        ),
    )
    parser.add_argument(
        "--no-expectation",
        action="store_true",
        help=(
            "Validate without an expectation, checking only schema, range sanity, "
            "internal consistency and the threshold. An explicit, reported reduction: "
            "a report whose completeness is unchecked cannot be shown to be complete."
        ),
    )
    parser.add_argument("--fail-threshold", type=float, default=0.95)
    parser.add_argument("--json", action="store_true", help="Emit a JSON summary on stdout.")
    args = parser.parse_args()

    if args.expectation is None and not args.no_expectation:
        parser.error(
            "pass --expectation PATH, or --no-expectation to accept that completeness "
            "will not be checked"
        )
    if args.expectation is not None and args.no_expectation:
        parser.error("--expectation and --no-expectation contradict each other")

    document, load_error = load_json(args.report)
    if load_error is not None:
        return _emit(args.json, ok=False, credible=False, findings=[load_error], summary={})

    expectation = None
    if args.expectation is not None:
        raw, expectation_error = load_json(args.expectation)
        if expectation_error is not None:
            return _emit(
                args.json, ok=False, credible=False, findings=[expectation_error], summary={}
            )
        try:
            expectation = Expectation.from_dict(raw)
        except ValueError as exc:
            return _emit(
                args.json,
                ok=False,
                credible=False,
                findings=[f"{args.expectation}: {exc}"],
                summary={},
            )

    verdict = validate(document, expectation, fail_threshold=args.fail_threshold)

    if args.json:
        print(
            json.dumps(
                {
                    "valid": verdict.ok,
                    "credible": verdict.credible,
                    "findings": {
                        Severity.CREDIBILITY: verdict.messages(Severity.CREDIBILITY),
                        Severity.THRESHOLD: verdict.messages(Severity.THRESHOLD),
                    },
                    "summary": verdict.summary,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return _status(verdict.ok, verdict.credible)

    if expectation is None:
        print(
            "gen-eval report: completeness NOT checked — no expectation supplied, so a "
            "run that silently dropped scenarios would still be accepted here",
            file=sys.stderr,
        )

    if not verdict.credible:
        print("gen-eval report: NOT CREDIBLE")
        for message in verdict.messages(Severity.CREDIBILITY):
            print(f"- {message}")
        return EXIT_NOT_CREDIBLE

    if not verdict.ok:
        print("gen-eval report: BELOW THRESHOLD")
        for message in verdict.messages(Severity.THRESHOLD):
            print(f"- {message}")
        return EXIT_THRESHOLD

    total = verdict.summary.get("total_scenarios")
    rate = verdict.summary.get("pass_rate")
    checked = "completeness checked" if expectation else "completeness unchecked"
    print(f"gen-eval report: VALID ({total} scenarios, pass_rate={rate}, {checked})")
    return 0


def _status(ok: bool, credible: bool) -> int:
    if not credible:
        return EXIT_NOT_CREDIBLE
    return 0 if ok else EXIT_THRESHOLD


def _emit(
    as_json: bool,
    ok: bool,
    credible: bool,
    findings: list[str],
    summary: dict[str, object],
) -> int:
    """Report a failure that happened before validation could start."""
    if as_json:
        print(
            json.dumps(
                {
                    "valid": ok,
                    "credible": credible,
                    "findings": {Severity.CREDIBILITY: findings, Severity.THRESHOLD: []},
                    "summary": summary,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print("gen-eval report: NOT CREDIBLE")
        for message in findings:
            print(f"- {message}")
    return _status(ok, credible)


if __name__ == "__main__":
    sys.exit(main())
