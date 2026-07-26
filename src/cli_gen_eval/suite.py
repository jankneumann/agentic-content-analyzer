"""Account for what the checked-in scenario suite should produce when it runs.

The runner's generator drops work quietly. Four separate paths in gen-eval's
``TemplateGenerator`` reduce a run's scenario count with a ``logger.warning`` and no
non-zero exit: an unparseable YAML file, a Jinja2 render error for one parameter
combination, an expansion that fails model validation, and a final
``scenarios[:max_scenarios_per_iteration]`` truncation. Any of them makes a run
evaluate less than the suite on disk claims while still reporting a pass rate.

That is the same defect class as a two-state runner gate: the failure is
indistinguishable from success. The answer is the same too — compute what the suite
*should* produce and compare, rather than trusting the run to complain.

This module does the computing. It deliberately does NOT re-implement Jinja2 rendering:
duplicating the runner's templating would drift from it, and a divergent second
implementation is worse than none. It computes the expansion *count* — which is plain
arithmetic over the ``parameters`` block and cannot drift — plus the cheap static checks
that catch the render errors without rendering anything.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from math import prod
from pathlib import Path
from typing import Any

# Jinja2 substitutions this suite uses: `{{ name }}`, optionally with filters we do not
# use. Anything more elaborate is rejected rather than guessed at — see
# `_reference_errors`.
_SUBSTITUTION = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
_ANY_JINJA = re.compile(r"\{\{|\{%")


@dataclass(frozen=True)
class TemplateAccount:
    """What one checked-in template contributes to a run."""

    path: Path
    scenario_id: str
    category: str
    priority: int
    expansions: int
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TierCapacity:
    """How many scenarios one run of the pinned runner can actually evaluate.

    Two stages of truncation, neither exposed on the runner's CLI. The generator returns
    ``scenarios[:max_scenarios_per_iteration]``; the orchestrator then buckets what
    survives and allocates a fixed share to each bucket:

        tier 1  int(total * 0.40)  interfaces matching --changed-features-ref
        tier 2  int(total * 0.35)  priority <= critical_priority_max
        tier 3  the remainder      everything else

    The trap is that tier 1 does not reflow. With no ``--changed-features-ref`` its
    allocation is simply unspent, so a run's real capacity is tier 2 plus tier 3 — 30 of
    a nominal 50 — and the non-critical share is only 13. Modelling this here is what
    turns "the report says 21 of an expected 39, and passed" into a failing assertion.
    """

    total: int
    changed: int
    critical: int
    remainder: int
    critical_priority_max: int

    @property
    def effective_total(self) -> int:
        """Capacity without change detection, where the tier-1 share is unspent."""
        return self.critical + self.remainder


def tier_capacity(
    max_scenarios_per_iteration: int,
    changed_share: float = 0.40,
    critical_share: float = 0.35,
    critical_priority_max: int = 1,
) -> TierCapacity:
    """Mirror the pinned runner's budget arithmetic exactly, including the int() floors."""
    total = int(max_scenarios_per_iteration)
    changed = int(total * changed_share)
    critical = int(total * critical_share)
    return TierCapacity(
        total=total,
        changed=changed,
        critical=critical,
        remainder=total - changed - critical,
        critical_priority_max=critical_priority_max,
    )


@dataclass(frozen=True)
class SuiteAccount:
    """What the whole checked-in suite contributes, per category and per runner tier."""

    templates: list[TemplateAccount]

    @property
    def errors(self) -> dict[str, list[str]]:
        return {str(t.path): t.errors for t in self.templates if t.errors}

    @property
    def per_category(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for template in self.templates:
            counts[template.category] += template.expansions
        return dict(counts)

    def expected_scenarios(self, categories: set[str] | None = None) -> int:
        """Scenarios the runner should generate for a selection of categories."""
        return sum(
            count
            for category, count in self.per_category.items()
            if categories is None or category in categories
        )

    def per_tier(
        self, capacity: TierCapacity, categories: set[str] | None = None
    ) -> dict[str, int]:
        """Split the expected scenarios the way the runner's orchestrator will."""
        critical = 0
        remainder = 0
        for template in self.templates:
            if categories is not None and template.category not in categories:
                continue
            if template.priority <= capacity.critical_priority_max:
                critical += template.expansions
            else:
                remainder += template.expansions
        return {"critical": critical, "remainder": remainder}

    def overflows(self, capacity: TierCapacity, categories: set[str] | None = None) -> list[str]:
        """Describe every way this selection would be silently truncated."""
        tiers = self.per_tier(capacity, categories)
        problems: list[str] = []
        if tiers["critical"] > capacity.critical:
            problems.append(
                f"{tiers['critical']} scenarios at priority "
                f"<= {capacity.critical_priority_max} exceed the runner's "
                f"{capacity.critical}-slot critical tier by "
                f"{tiers['critical'] - capacity.critical}"
            )
        if tiers["remainder"] > capacity.remainder:
            problems.append(
                f"{tiers['remainder']} scenarios at priority "
                f"> {capacity.critical_priority_max} exceed the runner's "
                f"{capacity.remainder}-slot remainder tier by "
                f"{tiers['remainder'] - capacity.remainder}"
            )
        total = tiers["critical"] + tiers["remainder"]
        if total > capacity.effective_total:
            problems.append(
                f"{total} scenarios exceed the runner's effective per-run capacity of "
                f"{capacity.effective_total} (its nominal {capacity.total} minus the "
                f"{capacity.changed}-slot change-detection tier, which does not reflow)"
            )
        return problems


def _strings(document: Any) -> list[str]:
    """Every string anywhere in the document, where substitutions may appear."""
    if isinstance(document, str):
        return [document]
    if isinstance(document, dict):
        return [s for value in document.values() for s in _strings(value)]
    if isinstance(document, list):
        return [s for item in document for s in _strings(item)]
    return []


def _reference_errors(document: Any, parameters: dict[str, Any]) -> list[str]:
    """Catch the render failures that would silently drop parameter combinations.

    gen-eval renders with ``StrictUndefined``, so a substitution naming something the
    ``parameters`` block does not declare raises ``UndefinedError`` — which the
    generator logs and swallows, dropping that combination. Checking references
    statically turns that into a validation failure before any run.
    """
    errors: list[str] = []
    declared = set(parameters)
    for text in _strings(document):
        if not _ANY_JINJA.search(text):
            continue
        if "{%" in text:
            errors.append(
                "uses a Jinja2 statement block ({% ... %}); this suite supports only "
                "simple {{ name }} substitutions, and the expansion count of a "
                "statement block cannot be computed statically"
            )
            continue
        referenced = set(_SUBSTITUTION.findall(text))
        # A `{{` that our substitution pattern did not match is something more
        # elaborate than a bare name — a filter, an expression, an attribute lookup.
        if text.count("{{") != len(_SUBSTITUTION.findall(text)):
            errors.append(f"contains a substitution this suite cannot account for: {text[:80]!r}")
            continue
        for name in sorted(referenced - declared):
            errors.append(
                f"references undeclared parameter {name!r}; gen-eval renders with "
                "StrictUndefined and would drop the expansion with only a warning"
            )
    if not declared:
        return errors
    used = {
        name
        for text in _strings(document)
        if _ANY_JINJA.search(text)
        for name in _SUBSTITUTION.findall(text)
    }
    for name in sorted(declared - used):
        errors.append(
            f"declares parameter {name!r} but no field substitutes it, so the "
            "expansions would be identical apart from their generated ids"
        )
    return errors


def iter_templates(document: Any) -> list[Any]:
    """A scenario file holds either one template or a list of them.

    gen-eval's loader accepts both (``templates.extend(data)`` for a list), so the
    contract layer has to as well — otherwise a file that the runner reads as eight
    scenarios validates here as one malformed document, or worse, validates by accident.
    """
    if isinstance(document, list):
        return list(document)
    return [document]


def account_template(document: Any, path: Path, max_expansions: int) -> TemplateAccount:
    """Account for a single scenario template.

    Schema validity is not re-checked here — ``validate_scenario`` owns that. This
    reports how many scenarios the template becomes, and the static errors that would
    make the runner quietly produce fewer.
    """
    if not isinstance(document, dict):
        return TemplateAccount(
            path=path,
            scenario_id="<unknown>",
            category="<unknown>",
            priority=0,
            expansions=0,
            errors=["template is not a mapping"],
        )

    scenario_id = str(document.get("id", "<unknown>"))
    category = str(document.get("category", "<unknown>"))
    priority = int(document.get("priority", 2) or 2)
    parameters = document.get("parameters") or {}

    errors: list[str] = []
    if not isinstance(parameters, dict):
        return TemplateAccount(
            path=path,
            scenario_id=scenario_id,
            category=category,
            priority=priority,
            expansions=0,
            errors=["parameters must be a mapping of name to list of values"],
        )

    lengths: list[int] = []
    for name, values in parameters.items():
        if not isinstance(values, list):
            # gen-eval wraps a scalar into a single-element list.
            lengths.append(1)
            continue
        if not values:
            errors.append(
                f"parameter {name!r} declares an empty value list, which expands to zero scenarios"
            )
            lengths.append(0)
            continue
        lengths.append(len(values))

    combinations = prod(lengths) if lengths else 1
    if combinations > max_expansions:
        errors.append(
            f"expands to {combinations} combinations but the pinned runner caps a "
            f"template at {max_expansions}, so {combinations - max_expansions} would "
            "be dropped without a non-zero exit"
        )
        combinations = max_expansions

    errors.extend(_reference_errors(document, parameters))

    return TemplateAccount(
        path=path,
        scenario_id=scenario_id,
        category=category,
        priority=priority,
        expansions=combinations,
        errors=errors,
    )


def derive_interfaces(document: Any) -> list[str]:
    """Which interfaces a template's steps will credit, in first-seen order.

    This mirrors gen-eval's ``Evaluator._extract_interfaces`` for CLI steps: the
    interface is ``cli:`` plus the words of ``step.command`` up to the first one
    starting with ``-``. A command that *is* a flag credits nothing, which is how a
    root-level ``--json`` spelling avoids inventing an interface named after a flag.

    Reimplementing it here is a deliberate exception to this module's rule against
    duplicating runner logic. The rule exists because Jinja2 rendering is large enough
    to drift; this is four lines of string splitting, and the alternative is having no
    way to predict coverage without running the suite. The duplication is pinned by
    ``tests/cli_gen_eval/test_report.py``, which asserts the derivation reproduces the
    ``per_interface`` keys of a real recorded report.

    Note that the runner ignores a scenario's declared ``interfaces`` field entirely and
    derives coverage from steps alone — so the declaration is documentation unless
    something checks it. That is what ``test_declared_interfaces_match_the_steps`` is
    for.
    """
    if not isinstance(document, dict):
        return []

    seen: set[str] = set()
    result: list[str] = []
    for step in document.get("steps") or []:
        if not isinstance(step, dict) or step.get("transport") != "cli":
            continue
        command = str(step.get("command") or "").strip()
        words: list[str] = []
        for word in command.split():
            if word.startswith("-"):
                break
            words.append(word)
        if not words:
            continue
        interface = f"cli:{' '.join(words)}"
        if interface not in seen:
            seen.add(interface)
            result.append(interface)
    return result
