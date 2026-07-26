"""The report validator must reject a run that looks like it worked but did not.

Every negative case here is a mutation of a *real* recorded report rather than a
hand-authored one, so each test says "this is what the runner emits, and this one change
is what makes it unbelievable". The mutations are not hypothetical: dropping verdicts
reproduces the Phase 3 truncation exactly (39 selected, 21 evaluated, `pass_rate: 1.0`,
exit 0), and the out-of-range values reproduce what the published schema permits because
it bounds nothing (UPSTREAM.md UP-5).

The distinction the tests are most careful about is credibility versus threshold. A
report can be perfectly credible and fail (`aca` regressed); it can also report 100% and
be worthless (the run evaluated a third of what it was handed). Only the second is a
problem with the harness, and collapsing them would hide it.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.cli_gen_eval.contract import (
    INTENTIONALLY_UNDECLARED_COMMANDS,
    validate_report as validate_schema,
)
from src.cli_gen_eval.report import (
    Expectation,
    Severity,
    declared_interfaces,
    expectation_from,
    validate,
)
from src.cli_gen_eval.suite import derive_interfaces, iter_templates

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "gen_eval"
SCENARIO_ROOT = REPO_ROOT / "evaluation" / "scenarios"
DESCRIPTOR = REPO_ROOT / "evaluation" / "descriptors" / "aca-cli.yaml"
VALIDATOR = REPO_ROOT / "scripts" / "validate_gen_eval_report.py"

RECORDED_RUNS = ("full-pass", "offline-pass")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def report() -> dict[str, Any]:
    """The full 16-scenario passing run. Mutate freely — each test gets a fresh copy."""
    return _load("report-full-pass.json")


@pytest.fixture
def expectation() -> Expectation:
    return Expectation.from_dict(_load("expectation-full-pass.json"))


@pytest.fixture(scope="module")
def descriptor() -> dict[str, Any]:
    return yaml.safe_load(DESCRIPTOR.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def templates() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for path in sorted(SCENARIO_ROOT.rglob("*.yaml")):
        for template in iter_templates(yaml.safe_load(path.read_text(encoding="utf-8"))):
            if isinstance(template, dict):
                found.append(template)
    return found


def credibility(document: Any, expectation: Expectation | None = None) -> list[str]:
    return validate(document, expectation).messages(Severity.CREDIBILITY)


# ---------------------------------------------------------------------------
# The recorded runs are real, and are accepted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("run", RECORDED_RUNS)
def test_the_recorded_reports_are_schema_valid(run: str) -> None:
    """Also proves the fixture truncation did not corrupt the documents."""
    assert validate_schema(_load(f"report-{run}.json")) == []


@pytest.mark.parametrize("run", RECORDED_RUNS)
def test_a_real_passing_run_is_accepted(run: str) -> None:
    verdict = validate(
        _load(f"report-{run}.json"),
        Expectation.from_dict(_load(f"expectation-{run}.json")),
    )
    assert verdict.ok, verdict.messages()
    assert verdict.summary["completeness_checked"] is True


def test_the_offline_run_covers_less_and_is_still_complete() -> None:
    """`--offline` is a smaller *request*, not a smaller answer to the same request.

    This is the property that makes a scoped expectation the right denominator: the
    offline run evaluates 11 of 16 scenarios and is entirely credible, because 11 is
    what it was asked for.
    """
    offline = Expectation.from_dict(_load("expectation-offline-pass.json"))
    full = Expectation.from_dict(_load("expectation-full-pass.json"))
    assert offline.total_scenarios < full.total_scenarios
    assert offline.offline is True
    assert validate(_load("report-offline-pass.json"), offline).ok


# ---------------------------------------------------------------------------
# Interface derivation reproduces the runner's own
# ---------------------------------------------------------------------------


def test_derivation_reproduces_the_runners_per_interface_keys(
    templates: list[dict[str, Any]],
) -> None:
    """`derive_interfaces` duplicates gen-eval's rule, so it has to be pinned to it.

    If the runner ever changes how a step credits an interface, the expectation would
    silently start predicting the wrong coverage. Comparing against a recorded report
    catches that at the pin bump rather than in whatever run first went quiet.
    """
    report = _load("report-full-pass.json")
    predicted = {interface for template in templates for interface in derive_interfaces(template)}
    assert predicted == set(report["per_interface"])


def test_a_flag_first_command_credits_nothing() -> None:
    """The rule that made `absent-optional-values-omitted` need an extra step."""
    assert derive_interfaces({"steps": [{"transport": "cli", "command": "--json"}]}) == []


def test_declared_interfaces_match_the_steps(templates: list[dict[str, Any]]) -> None:
    """The runner ignores a scenario's `interfaces` field entirely.

    It derives coverage from steps alone, so the declaration is inert documentation
    unless something holds it to the steps — and inert documentation is exactly what
    drifts. Both drifts this test was written to catch were real: one scenario claimed
    `cli:operations` while crediting nothing, another declared nothing while crediting
    three.
    """
    for template in templates:
        assert sorted(template.get("interfaces") or []) == sorted(derive_interfaces(template)), (
            f"{template['id']}: the declared interfaces disagree with what the steps will credit"
        )


def test_the_declared_denominator_matches_the_descriptor(descriptor: dict[str, Any]) -> None:
    names = {f"cli:{command['name']}" for command in descriptor["services"][0]["commands"]}
    assert set(declared_interfaces(descriptor)) == names


# ---------------------------------------------------------------------------
# A vacuous run is rejected
# ---------------------------------------------------------------------------


def test_a_zero_scenario_report_is_rejected(report: dict[str, Any]) -> None:
    report.update(total_scenarios=0, passed=0, failed=0, errors=0, skipped=0, verdicts=[])
    report["pass_rate"] = 0.0
    findings = credibility(report)
    assert any("has no pass rate to report" in f for f in findings), findings


def test_a_zero_scenario_report_is_rejected_without_an_expectation(
    report: dict[str, Any],
) -> None:
    """Non-vacuity does not depend on knowing what was requested."""
    report.update(total_scenarios=0, passed=0, failed=0, errors=0, skipped=0, verdicts=[])
    report["pass_rate"] = 0.0
    assert credibility(report, None)


def test_dropped_scenarios_are_rejected_even_at_a_perfect_pass_rate(
    report: dict[str, Any], expectation: Expectation
) -> None:
    """The Phase 3 failure, reproduced.

    Truncating the verdicts and re-deriving every count gives a report that is
    internally consistent, schema-valid, and reports 100%. The runner exits 0 on it. The
    only thing wrong is that it evaluated half of what it was handed.
    """
    kept = report["verdicts"][:8]
    report["verdicts"] = kept
    report.update(total_scenarios=len(kept), passed=len(kept), failed=0, errors=0, skipped=0)
    report["pass_rate"] = 1.0

    verdict = validate(report, expectation)
    assert not verdict.credible
    assert verdict.messages(Severity.THRESHOLD) == []  # 100% — the threshold sees nothing
    findings = verdict.messages(Severity.CREDIBILITY)
    assert any("but the report evaluated 8" in f for f in findings), findings
    # And it must name what went missing, not just the shortfall.
    assert any("was selected but not run" in f for f in findings), findings


def test_a_scenario_outside_the_selection_is_rejected(
    report: dict[str, Any], expectation: Expectation
) -> None:
    """The safety direction: something ran that was not asked for.

    Under Phase 5 this is a mutating scenario escaping its category, which is why it is
    a credibility failure rather than a curiosity.
    """
    stowaway = copy.deepcopy(report["verdicts"][0])
    stowaway["scenario_id"] = "workflow-submission-ingest-rss"
    report["verdicts"].append(stowaway)
    report["total_scenarios"] += 1
    report["passed"] += 1
    report["pass_rate"] = report["passed"] / report["total_scenarios"]

    findings = credibility(report, expectation)
    assert any("ran but was not in the selection" in f for f in findings), findings


def test_a_short_category_is_rejected(report: dict[str, Any], expectation: Expectation) -> None:
    """Per-category counts catch a shortfall that hides inside a correct total."""
    report["per_category"]["plumbing"]["total"] = 4
    report["per_category"]["discovery"]["total"] = 8
    findings = credibility(report, expectation)
    assert any("category 'plumbing' expected 9" in f for f in findings), findings


def test_an_unexpected_category_is_rejected(
    report: dict[str, Any], expectation: Expectation
) -> None:
    report["per_category"]["operation-control"] = {"pass": 1, "fail": 0, "error": 0, "total": 1}
    findings = credibility(report, expectation)
    assert any("'operation-control' appears in the report" in f for f in findings), findings


# ---------------------------------------------------------------------------
# Coverage, scoped to the selection
# ---------------------------------------------------------------------------


def test_a_selected_interface_reported_unevaluated_is_rejected(
    report: dict[str, Any], expectation: Expectation
) -> None:
    report["unevaluated_interfaces"] = ["cli:operations"]
    findings = credibility(report, expectation)
    assert any("'cli:operations'" in f and "unevaluated" in f for f in findings), findings


def test_an_unselected_interface_reported_unevaluated_is_accepted(
    report: dict[str, Any],
) -> None:
    """The rule that would otherwise fail every partial run.

    Measured, not hypothesised: `--categories validation --offline` evaluates 2
    scenarios, passes 100%, and leaves 29 of 31 declared interfaces unevaluated. It is
    correct to do so, so the check is scoped to the interfaces the selection addresses
    rather than to emptiness.
    """
    narrow = Expectation(
        categories=["validation"],
        scenario_ids=["validation-malformed-arguments"],
        per_category={"validation": 1},
        interfaces=["cli:capabilities"],
        declared_interfaces=list(_load("expectation-full-pass.json")["declared_interfaces"]),
    )
    report["unevaluated_interfaces"] = ["cli:ingest", "cli:digest", "cli:worker"]
    report["verdicts"] = [
        v for v in report["verdicts"] if v["scenario_id"] == "validation-malformed-arguments"
    ]
    report.update(total_scenarios=1, passed=1, failed=0, errors=0, skipped=0, pass_rate=1.0)
    report["per_category"] = {"validation": {"pass": 1, "fail": 0, "error": 0, "total": 1}}
    report["per_interface"] = {"cli:capabilities": {"pass": 1, "fail": 0, "error": 0}}

    verdict = validate(report, narrow)
    assert verdict.ok, verdict.messages()


def test_a_missing_interface_is_rejected(report: dict[str, Any], expectation: Expectation) -> None:
    del report["per_interface"]["cli:operations"]
    findings = credibility(report, expectation)
    assert any("absent from per_interface" in f for f in findings), findings


def test_a_phantom_interface_is_rejected(report: dict[str, Any], expectation: Expectation) -> None:
    """A mistyped `command` credits an interface that does not exist.

    The runner reports no error for this — it just adds `cli:operatoins` to
    `per_interface` while `cli:operations` quietly goes uncovered.
    """
    report["per_interface"]["cli:operatoins"] = {"pass": 1, "fail": 0, "error": 0}
    findings = credibility(report, expectation)
    assert any("'cli:operatoins'" in f and "not declared" in f for f in findings), findings


def test_the_reviewed_undeclared_command_is_allowed(
    report: dict[str, Any], expectation: Expectation
) -> None:
    """`cli:definitely-not-a-command` is in every report and is deliberate."""
    assert INTENTIONALLY_UNDECLARED_COMMANDS
    for name in INTENTIONALLY_UNDECLARED_COMMANDS:
        assert f"cli:{name}" in report["per_interface"]
    assert validate(report, expectation).ok


# ---------------------------------------------------------------------------
# Range sanity and self-consistency — the gaps the published schema leaves
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pass_rate", 1.5),
        ("pass_rate", -0.1),
        ("coverage_pct", 101.0),
        ("coverage_pct", -12.0),
    ],
)
def test_out_of_range_values_are_rejected(report: dict[str, Any], field: str, value: float) -> None:
    """These are all schema-VALID. The published schema bounds nothing (UP-5)."""
    report[field] = value
    assert validate_schema(report) == []
    findings = credibility(report)
    assert any(field in f and "outside the valid range" in f for f in findings), findings


def test_a_negative_count_is_rejected(report: dict[str, Any]) -> None:
    report["skipped"] = -1
    assert validate_schema(report) == []
    assert any("skipped is negative" in f for f in credibility(report)), credibility(report)


def test_a_report_that_disagrees_with_itself_is_rejected(report: dict[str, Any]) -> None:
    report["passed"] = 3
    findings = credibility(report)
    assert any("passed+failed+errors+skipped" in f for f in findings), findings
    assert any("pass_rate is" in f for f in findings), findings


def test_a_verdict_count_mismatch_is_rejected(report: dict[str, Any]) -> None:
    """Catches a hand-edited artifact, and the runner losing verdicts on the way out."""
    report["verdicts"] = report["verdicts"][:5]
    findings = credibility(report)
    assert any("carries 5 verdicts" in f for f in findings), findings


def test_a_schema_invalid_report_stops_at_the_schema(report: dict[str, Any]) -> None:
    """Later checks index by key; against an invalid document they would be guesses."""
    del report["per_interface"]
    verdict = validate(report, None)
    assert not verdict.credible
    assert all(f.startswith("schema: ") for f in verdict.messages(Severity.CREDIBILITY))
    assert verdict.summary == {"schema_valid": False, "completeness_checked": False}


def test_a_non_mapping_report_is_rejected() -> None:
    assert credibility(["not", "a", "report"])


# ---------------------------------------------------------------------------
# Threshold, kept apart from credibility
# ---------------------------------------------------------------------------


def test_a_below_threshold_run_fails_but_stays_credible(
    report: dict[str, Any], expectation: Expectation
) -> None:
    """A real regression: everything ran, some of it failed. That is a product defect,
    not a harness one, and the verdict has to be able to say which."""
    for verdict_document in report["verdicts"][:4]:
        verdict_document["status"] = "fail"
    report.update(passed=12, failed=4, pass_rate=12 / 16)

    verdict = validate(report, expectation, fail_threshold=0.95)
    assert verdict.credible
    assert not verdict.ok
    assert any("below the threshold" in m for m in verdict.messages(Severity.THRESHOLD))


def test_the_threshold_is_honoured_exactly(report: dict[str, Any]) -> None:
    report.update(passed=15, failed=1, pass_rate=15 / 16)
    assert validate(report, None, fail_threshold=15 / 16).ok
    assert not validate(report, None, fail_threshold=0.95).ok


# ---------------------------------------------------------------------------
# The expectation is built from the selection, not restated by hand
# ---------------------------------------------------------------------------


def test_the_expectation_matches_the_checked_in_suite(
    templates: list[dict[str, Any]], descriptor: dict[str, Any]
) -> None:
    built = expectation_from(
        templates, descriptor, categories=["discovery", "plumbing", "validation"]
    )
    recorded = Expectation.from_dict(_load("expectation-full-pass.json"))
    assert built.to_dict() == recorded.to_dict()


def test_an_expectation_round_trips() -> None:
    recorded = _load("expectation-full-pass.json")
    assert Expectation.from_dict(recorded).to_dict() == recorded


def test_an_incomplete_expectation_is_refused() -> None:
    with pytest.raises(ValueError, match="missing"):
        Expectation.from_dict({"categories": ["plumbing"]})


# ---------------------------------------------------------------------------
# The script wrapper
# ---------------------------------------------------------------------------


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *argv],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_script_accepts_a_real_run() -> None:
    result = _run(
        str(FIXTURES / "report-full-pass.json"),
        "--expectation",
        str(FIXTURES / "expectation-full-pass.json"),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VALID" in result.stdout


def test_the_script_refuses_to_guess_about_completeness() -> None:
    """Silence about an unchecked property is the failure mode this change exists to
    remove, so skipping completeness has to be asked for by name."""
    result = _run(str(FIXTURES / "report-full-pass.json"))
    assert result.returncode == 2
    assert "--no-expectation" in result.stderr


def test_the_script_says_what_it_gave_up(tmp_path: Path) -> None:
    result = _run(str(FIXTURES / "report-full-pass.json"), "--no-expectation")
    assert result.returncode == 0
    assert "completeness NOT checked" in result.stderr
    # The reduction is recorded in the artifact too, not only in the operator's terminal.
    machine = _run(str(FIXTURES / "report-full-pass.json"), "--no-expectation", "--json")
    assert json.loads(machine.stdout)["summary"]["completeness_checked"] is False


def test_the_script_separates_its_two_failures(tmp_path: Path) -> None:
    report = _load("report-full-pass.json")
    report.update(passed=0, failed=16, pass_rate=0.0)
    for verdict_document in report["verdicts"]:
        verdict_document["status"] = "fail"
    below = tmp_path / "below.json"
    below.write_text(json.dumps(report))

    threshold = _run(str(below), "--expectation", str(FIXTURES / "expectation-full-pass.json"))
    assert threshold.returncode == 1
    assert "BELOW THRESHOLD" in threshold.stdout

    report["verdicts"] = report["verdicts"][:3]
    report.update(total_scenarios=3, failed=3, passed=0)
    truncated = tmp_path / "truncated.json"
    truncated.write_text(json.dumps(report))

    credibility_run = _run(
        str(truncated), "--expectation", str(FIXTURES / "expectation-full-pass.json")
    )
    assert credibility_run.returncode == 5
    assert "NOT CREDIBLE" in credibility_run.stdout


def test_the_script_rejects_an_unreadable_report(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    result = _run(str(broken), "--no-expectation")
    assert result.returncode == 5
    assert "not valid JSON" in result.stdout


def test_the_script_rejects_contradictory_flags() -> None:
    result = _run(
        str(FIXTURES / "report-full-pass.json"),
        "--expectation",
        str(FIXTURES / "expectation-full-pass.json"),
        "--no-expectation",
    )
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# Grouping (task 4.5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("run", RECORDED_RUNS)
def test_the_report_groups_results_by_category(run: str) -> None:
    report = _load(f"report-{run}.json")
    expectation = _load(f"expectation-{run}.json")
    assert set(report["per_category"]) == set(expectation["per_category"])
    for category, bucket in report["per_category"].items():
        assert set(bucket) >= {"pass", "fail", "error", "total"}
        assert bucket["total"] == expectation["per_category"][category]
        assert bucket["pass"] + bucket["fail"] + bucket["error"] == bucket["total"]


@pytest.mark.parametrize("run", RECORDED_RUNS)
def test_the_report_groups_results_by_command(run: str) -> None:
    report = _load(f"report-{run}.json")
    expectation = _load(f"expectation-{run}.json")
    assert set(report["per_interface"]) == set(expectation["interfaces"])
    for interface, bucket in report["per_interface"].items():
        assert set(bucket) == {"pass", "fail", "error"}, interface
        assert sum(bucket.values()) >= 1, interface


def test_every_grouped_command_is_traceable_to_a_scenario() -> None:
    """Grouping is only useful if a failing bucket leads somewhere.

    `per_interface` is a count, so the route from "`cli:ingest` failed" back to which
    scenario to open runs through the verdicts.
    """
    report = _load("report-full-pass.json")
    from_verdicts = {
        interface
        for verdict_document in report["verdicts"]
        for interface in verdict_document["interfaces_tested"]
    }
    assert from_verdicts == set(report["per_interface"])
