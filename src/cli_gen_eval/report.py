"""Decide whether an evaluation report is *credible* before believing its pass rate.

A schema-valid report with `pass_rate: 1.0` is not evidence that the CLI works. It is
evidence that whatever ran, passed. Phase 3 produced the demonstration: a 39-scenario
suite reported `total_scenarios: 21`, `pass_rate: 1.0`, `PASS (100.0%)`, exit 0, having
silently dropped eighteen scenarios and seventeen interfaces inside the runner. Nothing
in the report said so, because a run that evaluates less than it was given looks exactly
like a run that had less to do.

So this module answers a different question from the threshold: *did the run do what it
was asked to do?* It compares the report against an `Expectation` — computed from the
selection before the runner is invoked — and only then applies the pass-rate threshold.
The two verdicts are kept apart deliberately, because they land on different desks. A
threshold failure means `aca` regressed. A credibility failure means the harness cannot
be trusted to have noticed either way.

Three properties of the pinned runner shape what is checkable here, all verified against
its source at ref `600744a5` rather than assumed:

**Coverage is measured against the whole descriptor, not the selection.**
`coverage_pct = covered / descriptor.all_interfaces()`, so a legitimate single-category
run reports most interfaces as unevaluated. Measured: `--categories validation --offline`
gives 2 scenarios, 100% pass, and 29 of 31 interfaces unevaluated. The rule "fail when
any declared interface is unevaluated" would therefore reject every partial run, which is
why the expectation carries the interfaces *the selection is supposed to address* and the
check is scoped to those.

**Coverage is attempted, not passed.** `interfaces_tested` comes from a scenario's
declared steps regardless of which ones executed — and the runner short-circuits a
scenario at its first failing step. A batch that dies on step 1 still credits all four of
its commands. Coverage answers "was this addressed", never "does this work"; only the
pass rate answers the second.

**`per_interface` is keyed by what scenarios claimed, not by what exists.** A typo in a
step's `command` credits a phantom interface *and* leaves the real one uncovered, with no
error from the runner. Hence the check that every reported interface is one the
descriptor declares.

The report's own fields are read rather than recomputed (D7). Recomputing coverage from
verdicts would make this a second implementation of the runner's aggregation, and a
disagreement between the two would be indistinguishable from the defect it is meant to
find.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .contract import INTENTIONALLY_UNDECLARED_COMMANDS, validate_report as validate_schema
from .suite import derive_interfaces

#: Report fields whose value is a proportion, and the closed range each must fall in.
#: The published schema declares these as bare `number` with no bounds (UPSTREAM.md
#: UP-5), so `pass_rate: 1.5` is schema-valid. We vendor that schema verbatim rather than
#: tightening our copy — a locally-stricter contract would disagree with upstream's own
#: drift test — which leaves the range check here.
_RANGES: dict[str, tuple[float, float]] = {
    "pass_rate": (0.0, 1.0),
    "coverage_pct": (0.0, 100.0),
}

#: Report fields that count things and therefore cannot be negative.
_COUNTS = (
    "total_scenarios",
    "passed",
    "failed",
    "errors",
    "skipped",
    "iterations_completed",
)

#: How far the recomputed pass rate may sit from the reported one before it is a finding.
#: Floating-point division of small integers, not accumulated error, so this is tight.
_PASS_RATE_TOLERANCE = 1e-9


class Severity:
    """Why a report was rejected — the two answers go to different people."""

    CREDIBILITY = "credibility"
    THRESHOLD = "threshold"


@dataclass(frozen=True)
class Finding:
    """One reason a report is not acceptable."""

    severity: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.message}"


@dataclass(frozen=True)
class Expectation:
    """What a run was asked to do, computed before the runner is invoked.

    Written next to the report so the pair travels together: a report alone cannot say
    whether it is complete, because completeness is a fact about the *request*. CI
    publishes both as retained evidence for exactly that reason.
    """

    categories: list[str]
    scenario_ids: list[str]
    per_category: dict[str, int]
    interfaces: list[str]
    declared_interfaces: list[str]
    offline: bool = False

    @property
    def total_scenarios(self) -> int:
        return len(self.scenario_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "categories": sorted(self.categories),
            "scenario_ids": sorted(self.scenario_ids),
            "per_category": dict(sorted(self.per_category.items())),
            "interfaces": sorted(self.interfaces),
            "declared_interfaces": sorted(self.declared_interfaces),
            "offline": self.offline,
            "total_scenarios": self.total_scenarios,
        }

    @classmethod
    def from_dict(cls, document: Any) -> Expectation:
        if not isinstance(document, dict):
            raise ValueError("expectation document is not a mapping")
        missing = [
            key
            for key in ("categories", "scenario_ids", "per_category", "interfaces")
            if key not in document
        ]
        if missing:
            raise ValueError(f"expectation document is missing {missing}")
        return cls(
            categories=list(document["categories"]),
            scenario_ids=list(document["scenario_ids"]),
            per_category=dict(document["per_category"]),
            interfaces=list(document["interfaces"]),
            declared_interfaces=list(document.get("declared_interfaces") or []),
            offline=bool(document.get("offline", False)),
        )


def declared_interfaces(descriptor: Any) -> list[str]:
    """Every ``cli:<command>`` the descriptor declares — the coverage denominator.

    Mirrors gen-eval's ``InterfaceDescriptor.all_interfaces()`` for CLI services. Only
    the CLI branch is implemented: this repository declares one service and a descriptor
    that grew an HTTP or MCP service would need the expectation to grow with it, which
    should be a visible change rather than a silently partial denominator.
    """
    if not isinstance(descriptor, dict):
        return []
    interfaces: list[str] = []
    for service in descriptor.get("services") or []:
        if not isinstance(service, dict) or service.get("type") != "cli":
            continue
        for command in service.get("commands") or []:
            if isinstance(command, dict) and command.get("name"):
                interfaces.append(f"cli:{command['name']}")
    return interfaces


def expectation_from(
    templates: list[Any],
    descriptor: Any,
    categories: list[str],
    offline: bool = False,
) -> Expectation:
    """Build the expectation for a selection of scenario templates.

    ``templates`` are the selected templates themselves, so this stays independent of
    how the selection was resolved — the gate passes what it materialized, and a test
    can pass a hand-built list.
    """
    scenario_ids: list[str] = []
    per_category: Counter[str] = Counter()
    interfaces: set[str] = set()
    for template in templates:
        if not isinstance(template, dict):
            continue
        scenario_ids.append(str(template.get("id", "<unknown>")))
        per_category[str(template.get("category", "<unknown>"))] += 1
        interfaces.update(derive_interfaces(template))
    return Expectation(
        categories=sorted(categories),
        scenario_ids=scenario_ids,
        per_category=dict(per_category),
        interfaces=sorted(interfaces),
        declared_interfaces=sorted(declared_interfaces(descriptor)),
        offline=offline,
    )


@dataclass
class ReportVerdict:
    """The outcome of validating one report."""

    findings: list[Finding] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def credible(self) -> bool:
        """Whether the run can be believed, independent of whether it passed."""
        return not any(f.severity == Severity.CREDIBILITY for f in self.findings)

    def messages(self, severity: str | None = None) -> list[str]:
        return [f.message for f in self.findings if severity is None or f.severity == severity]


def _number(document: dict[str, Any], key: str) -> float | None:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _check_ranges(document: dict[str, Any], findings: list[Finding]) -> None:
    for key, (low, high) in _RANGES.items():
        value = _number(document, key)
        if value is None:
            continue
        if not low <= value <= high:
            findings.append(
                Finding(
                    Severity.CREDIBILITY,
                    f"{key} is {value}, outside the valid range [{low}, {high}] — the "
                    "published schema does not bound it (UPSTREAM.md UP-5)",
                )
            )
    for key in _COUNTS:
        value = _number(document, key)
        if value is not None and value < 0:
            findings.append(Finding(Severity.CREDIBILITY, f"{key} is negative ({value})"))
    duration = _number(document, "duration_seconds")
    if duration is not None and duration < 0:
        findings.append(Finding(Severity.CREDIBILITY, f"duration_seconds is negative ({duration})"))


def _check_internal_consistency(document: dict[str, Any], findings: list[Finding]) -> None:
    """The report must agree with itself.

    Cheap, and it catches both a hand-edited artifact and an aggregation bug upstream.
    Neither is hypothetical: the report is a file on disk that CI publishes and a human
    may re-upload, and the aggregation is the same code path that produced the
    Phase 3 truncation.
    """
    total = document.get("total_scenarios")
    if not isinstance(total, int):
        return

    parts = {
        key: value
        for key in ("passed", "failed", "errors", "skipped")
        if isinstance(value := document.get(key), int)
    }
    if len(parts) == 4:
        summed = sum(parts.values())
        if summed != total:
            findings.append(
                Finding(
                    Severity.CREDIBILITY,
                    f"passed+failed+errors+skipped is {summed} but total_scenarios is "
                    f"{total} ({parts})",
                )
            )

    verdicts = document.get("verdicts")
    if isinstance(verdicts, list) and len(verdicts) != total:
        findings.append(
            Finding(
                Severity.CREDIBILITY,
                f"the report carries {len(verdicts)} verdicts but claims total_scenarios={total}",
            )
        )

    passed = document.get("passed")
    reported_rate = _number(document, "pass_rate")
    if isinstance(passed, int) and reported_rate is not None:
        expected_rate = (passed / total) if total > 0 else 0.0
        if abs(expected_rate - reported_rate) > _PASS_RATE_TOLERANCE:
            findings.append(
                Finding(
                    Severity.CREDIBILITY,
                    f"pass_rate is {reported_rate} but passed/total_scenarios is {expected_rate}",
                )
            )


def _check_completeness(
    document: dict[str, Any],
    expectation: Expectation,
    findings: list[Finding],
) -> None:
    """Did the run evaluate what it was handed?

    This is the check the Phase 3 truncation would have failed, and the reason the
    expectation exists at all.
    """
    total = document.get("total_scenarios")
    if isinstance(total, int) and total != expectation.total_scenarios:
        findings.append(
            Finding(
                Severity.CREDIBILITY,
                f"the selection held {expectation.total_scenarios} scenarios but the "
                f"report evaluated {total} — the runner drops work without a non-zero "
                "exit (UPSTREAM.md UP-6)",
            )
        )

    verdicts = document.get("verdicts")
    if isinstance(verdicts, list):
        evaluated = {
            str(v.get("scenario_id"))
            for v in verdicts
            if isinstance(v, dict) and v.get("scenario_id")
        }
        expected = set(expectation.scenario_ids)
        # Naming *which* scenarios went missing is the difference between a usable
        # failure and a count that sends you back to the runner's logs.
        for scenario_id in sorted(expected - evaluated):
            findings.append(
                Finding(Severity.CREDIBILITY, f"scenario {scenario_id!r} was selected but not run")
            )
        for scenario_id in sorted(evaluated - expected):
            findings.append(
                Finding(
                    Severity.CREDIBILITY,
                    f"scenario {scenario_id!r} ran but was not in the selection",
                )
            )

    per_category = document.get("per_category")
    if isinstance(per_category, dict):
        for category, expected_count in sorted(expectation.per_category.items()):
            bucket = per_category.get(category)
            actual = bucket.get("total") if isinstance(bucket, dict) else None
            if actual != expected_count:
                findings.append(
                    Finding(
                        Severity.CREDIBILITY,
                        f"category {category!r} expected {expected_count} scenarios but "
                        f"the report groups {actual}",
                    )
                )
        for category in sorted(set(per_category) - set(expectation.per_category)):
            findings.append(
                Finding(
                    Severity.CREDIBILITY,
                    f"category {category!r} appears in the report but not in the selection",
                )
            )


def _check_coverage(
    document: dict[str, Any],
    expectation: Expectation,
    findings: list[Finding],
) -> None:
    """Coverage, scoped to what the selection was supposed to address.

    Read from the report's own `per_interface` and `unevaluated_interfaces` rather than
    recomputed from verdicts (D7). The denominator is the expectation's interfaces, not
    the descriptor's, because the descriptor's denominator makes every partial run look
    incomplete — measured, not assumed: a validation-only run leaves 29 of 31 declared
    interfaces unevaluated and is entirely correct to do so.
    """
    per_interface = document.get("per_interface")
    if isinstance(per_interface, dict):
        reported = set(per_interface)
        for interface in sorted(set(expectation.interfaces) - reported):
            findings.append(
                Finding(
                    Severity.CREDIBILITY,
                    f"interface {interface!r} is addressed by the selection but absent "
                    "from per_interface",
                )
            )
        allowed = set(expectation.declared_interfaces) | {
            f"cli:{name}" for name in INTENTIONALLY_UNDECLARED_COMMANDS
        }
        if expectation.declared_interfaces:
            for interface in sorted(reported - allowed):
                findings.append(
                    Finding(
                        Severity.CREDIBILITY,
                        f"interface {interface!r} is in the report but is not declared by "
                        "the descriptor — a mistyped step credits a phantom interface and "
                        "leaves the real one uncovered",
                    )
                )

    unevaluated = document.get("unevaluated_interfaces")
    if isinstance(unevaluated, list):
        # Scoped intersection, not emptiness: interfaces outside the selection are
        # *expected* to be unevaluated, and treating that as a failure would make every
        # category-scoped run unrunnable.
        missed = sorted(set(expectation.interfaces) & {str(i) for i in unevaluated})
        for interface in missed:
            findings.append(
                Finding(
                    Severity.CREDIBILITY,
                    f"interface {interface!r} is addressed by the selection but the "
                    "report lists it as unevaluated",
                )
            )


def validate(
    document: Any,
    expectation: Expectation | None = None,
    fail_threshold: float = 0.95,
) -> ReportVerdict:
    """Validate one report. Returns every finding rather than the first.

    Passing ``expectation=None`` runs only the runner-independent checks — schema, range
    sanity, internal consistency, non-vacuity, threshold. That is a real reduction in
    what is being asserted, so the caller is expected to say so out loud; the verdict's
    summary records ``completeness_checked: False`` to make it visible in the artifact
    rather than only in whoever ran it.
    """
    verdict = ReportVerdict()
    findings = verdict.findings

    schema_errors = validate_schema(document)
    if schema_errors:
        findings.extend(
            Finding(Severity.CREDIBILITY, f"schema: {error}") for error in schema_errors
        )
        # Every check below indexes into the document by key. Against a document that
        # already failed its schema, those would be guesses reported as findings.
        verdict.summary = {"schema_valid": False, "completeness_checked": False}
        return verdict

    assert isinstance(document, dict)  # guaranteed by the schema's "type": "object"

    _check_ranges(document, findings)
    _check_internal_consistency(document, findings)

    total = document.get("total_scenarios")
    if not isinstance(total, int) or total <= 0:
        findings.append(
            Finding(
                Severity.CREDIBILITY,
                f"the report evaluated {total} scenarios; a run with nothing in it has no "
                "pass rate to report",
            )
        )

    if expectation is not None:
        _check_completeness(document, expectation, findings)
        _check_coverage(document, expectation, findings)

    pass_rate = _number(document, "pass_rate")
    if pass_rate is not None and pass_rate < fail_threshold:
        findings.append(
            Finding(
                Severity.THRESHOLD,
                f"pass rate {pass_rate:.1%} is below the threshold {fail_threshold:.1%} "
                f"({document.get('failed')} failed, {document.get('errors')} errored)",
            )
        )

    verdict.summary = {
        "schema_valid": True,
        "completeness_checked": expectation is not None,
        "total_scenarios": document.get("total_scenarios"),
        "expected_scenarios": expectation.total_scenarios if expectation else None,
        "pass_rate": document.get("pass_rate"),
        "coverage_pct": document.get("coverage_pct"),
        "fail_threshold": fail_threshold,
    }
    return verdict


def load_json(path: Any) -> tuple[Any | None, str | None]:
    """Read a JSON document. Returns (document, error)."""
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except OSError as exc:
        return None, f"{path}: unreadable ({exc.strerror or exc})"
    except ValueError as exc:
        return None, f"{path}: not valid JSON ({exc})"
