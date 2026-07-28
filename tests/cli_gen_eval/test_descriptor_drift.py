"""Drift tests binding the checked-in descriptor to the live CLI (ri-06 Phase 3).

The property under test: the descriptor cannot fall behind the command surface without
someone noticing. A descriptor that quietly stops mentioning a command group is worse
than one that never mentioned it, because coverage is measured against what the
descriptor declares — so an omission silently *raises* the reported coverage percentage
while lowering real coverage.

Nothing here needs a runner, a backend, or a database: the assertions compare a
checked-in YAML file against Click's in-process command tree and against arithmetic
over the scenario templates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.main import get_command

from src.cli_gen_eval.contract import (
    INTENTIONALLY_UNDECLARED_COMMANDS,
    KNOWN_CATEGORIES,
    READ_ONLY_CATEGORIES,
)
from src.cli_gen_eval.suite import (
    SuiteAccount,
    account_template,
    iter_templates,
    tier_capacity,
)
from src.models.jobs import OperationType

REPO_ROOT = Path(__file__).resolve().parents[2]
DESCRIPTOR_PATH = REPO_ROOT / "evaluation" / "descriptors" / "aca-cli.yaml"
SCENARIO_ROOT = REPO_ROOT / "evaluation" / "scenarios"
PIN_PATH = REPO_ROOT / "evaluation" / "contract" / "pin.json"
HELP_SWEEP_PATH = SCENARIO_ROOT / "plumbing" / "group-help.yaml"

COVERAGE_TAG_PREFIX = "coverage:"
PLUMBING_TAG = "coverage:plumbing"

# Commands whose only declared coverage is the help surface, each with the reason no
# behavioural scenario exists. This is the "reviewed exclusion set with a stated
# reason" the spec asks for, and it is deliberately a table in a test rather than a
# field in the descriptor: the descriptor is consumed by the runner and should carry
# only what the runner acts on, while a reason exists to be read by a human deciding
# whether the exclusion still holds.
#
# Adding a command group therefore forces a choice — give it behavioural coverage, or
# write down why not. Neither can be skipped silently.
PLUMBING_ONLY_REASONS: dict[str, str] = {
    "agent": (
        "`task` submits agentic analysis with real model spend, and the read-only "
        "subcommands need seeded personas and insights to return anything meaningful."
    ),
    "auth": (
        "Interactive OAuth flows for Gmail and YouTube. `status` reads local credential "
        "files that no automated environment has."
    ),
    "batch": (
        "Gemini batch execution is disabled by default (GEMINI_BATCH_ENABLED), so "
        "`status` has nothing to report and no fixture exists to give it something."
    ),
    "curate": (
        "Performs live HTTP health checks against configured feeds. Network-dependent "
        "by design, which makes it inherently flaky inside a gate."
    ),
    "deploy": (
        "`sync-secrets` pushes secrets to Railway. Human-gated by intent; never "
        "appropriate for an automated suite."
    ),
    "edit": (
        "Every subcommand mutates persisted content, summaries, digests, or scripts, "
        "and none is a canonical workflow operation returning a durable handle — so it "
        "fits neither the read-only categories nor workflow-submission."
    ),
    "evaluate": ("Runs LLM-judge evaluation with model spend and requires seeded datasets."),
    "filter": (
        "Reads and re-runs the ingestion filter directly against the database, and "
        "`rerun` mutates content rows. There is no HTTP surface, so behavioural "
        "coverage belongs with the filter's own tests rather than a transport suite."
    ),
    "graph": (
        "`extract-entities` mutates the knowledge graph and `query` needs a populated "
        "graph database, which the read-only categories deliberately do not provision."
    ),
    "kb": (
        "Compiles and indexes the knowledge base against both the database and an "
        "embedding provider."
    ),
    "manage": (
        "Setup and backfill operations against the database, object storage, and "
        "Railway. Environment-mutating or destructive by nature."
    ),
    "models": (
        "`discover` and `refresh` call provider pricing APIs; `propose-default` mutates "
        "settings/models.yaml."
    ),
    "neon": (
        "Creates and deletes Neon branches — real infrastructure with real cost, and "
        "outside any target policy this gate models."
    ),
    "profile": (
        "Reads local profile files and secrets. Already covered by the profile "
        "validation tests in tests/config, which assert resolved settings rather than "
        "terminal output."
    ),
    "prompts": (
        "`set`, `reset`, and `import` mutate prompt overrides in the database, and the "
        "read-only subcommands need seeded overrides to return anything."
    ),
    "review": (
        "`list` and `view` are read-only but query the database directly rather than "
        "through the workflow API, so they need seeded digests."
    ),
    "settings": (
        "Same shape as `prompts`: `set` and `reset` mutate settings overrides, and the "
        "read path needs seeded rows."
    ),
    "sources": (
        "`add`, `remove`, `enable`, and `disable` mutate source overrides. The read "
        "path is already covered behaviourally through `configured-sources`, which "
        "returns the merged YAML-plus-database result."
    ),
    "sync": (
        "Moves data between environments including a remote database and file storage. "
        "Not safely exercisable without the mutation guard and a declared "
        "non-production target."
    ),
    "worker": (
        "`start` runs the queue worker as a long-lived process, whereas a scenario step "
        "is a bounded subprocess with a timeout."
    ),
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def descriptor() -> dict[str, Any]:
    return yaml.safe_load(DESCRIPTOR_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cli_service(descriptor: dict[str, Any]) -> dict[str, Any]:
    services = [s for s in descriptor["services"] if s["type"] == "cli"]
    assert len(services) == 1, "the descriptor declares exactly one CLI service"
    return services[0]


@pytest.fixture(scope="module")
def declared(cli_service: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["name"]: entry for entry in cli_service["commands"]}


@pytest.fixture(scope="module")
def registered() -> dict[str, list[str]]:
    """The live Click command tree: name -> sorted subcommand names (empty for leaves).

    Introspecting Click rather than parsing `--help` output on purpose. Rich wraps help
    text at the terminal width and interleaves description continuation lines with
    command names, so scraping it produces phantom entries.
    """
    from src.cli.app import app

    root = get_command(app)
    return {
        name: sorted(sub.commands) if hasattr(sub, "commands") else []
        for name, sub in root.commands.items()  # type: ignore[attr-defined]
    }


@pytest.fixture(scope="module")
def scenario_documents() -> list[tuple[Path, Any]]:
    """Every scenario template, with multi-scenario files flattened.

    A file holds one template or a list of them, and the runner reads both. Flattening
    here keeps the tests counting the same things the runner will.
    """
    flattened: list[tuple[Path, Any]] = []
    for path in sorted(p for p in SCENARIO_ROOT.rglob("*.yaml") if p.is_file()):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        flattened.extend((path, template) for template in iter_templates(document))
    return flattened


@pytest.fixture(scope="module")
def pin() -> dict[str, Any]:
    return json.loads(PIN_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# The descriptor tracks the registered command surface
# ---------------------------------------------------------------------------


def test_every_registered_command_is_declared(
    registered: dict[str, list[str]], declared: dict[str, dict[str, Any]]
) -> None:
    missing = sorted(set(registered) - set(declared))
    assert not missing, (
        f"registered on src/cli/app.py but absent from {DESCRIPTOR_PATH.name}: {missing}. "
        "Add an entry with a coverage:* tag, and either give it behavioural scenarios "
        "or record why not in PLUMBING_ONLY_REASONS."
    )


def test_no_declared_command_is_unregistered(
    registered: dict[str, list[str]], declared: dict[str, dict[str, Any]]
) -> None:
    """The direction that inflates coverage rather than deflating it.

    A declared command the CLI no longer has is never evaluated, so it lands in
    `unevaluated_interfaces` and depresses coverage — the *safe* failure. The dangerous
    variant is a renamed command: the old name goes unevaluated while scenarios silently
    stop addressing anything real. Either way the fix is the same, so both fail here.
    """
    stale = sorted(set(declared) - set(registered))
    assert not stale, f"declared in {DESCRIPTOR_PATH.name} but not registered on the CLI: {stale}"


def test_every_declared_command_carries_a_coverage_tag(
    declared: dict[str, dict[str, Any]],
) -> None:
    known = {f"{COVERAGE_TAG_PREFIX}{c}" for c in KNOWN_CATEGORIES}
    for name, entry in sorted(declared.items()):
        tags = set(entry.get("tags") or [])
        coverage = {t for t in tags if t.startswith(COVERAGE_TAG_PREFIX)}
        assert coverage, f"{name}: no coverage:* tag, so its coverage is undecided"
        unknown = sorted(coverage - known)
        assert not unknown, (
            f"{name}: coverage tags {unknown} name no known scenario category; "
            f"valid categories are {sorted(KNOWN_CATEGORIES)}"
        )
        assert PLUMBING_TAG in coverage, (
            f"{name}: every declared command is swept by the plumbing help sweep, so "
            f"it must carry {PLUMBING_TAG}"
        )


def test_plumbing_only_commands_state_a_reason(
    declared: dict[str, dict[str, Any]],
) -> None:
    plumbing_only = {
        name
        for name, entry in declared.items()
        if {t for t in (entry.get("tags") or []) if t.startswith(COVERAGE_TAG_PREFIX)}
        == {PLUMBING_TAG}
    }
    undocumented = sorted(plumbing_only - set(PLUMBING_ONLY_REASONS))
    assert not undocumented, (
        f"help-surface-only with no stated reason: {undocumented}. Add an entry to "
        "PLUMBING_ONLY_REASONS explaining why no behavioural scenario exists."
    )
    stale = sorted(set(PLUMBING_ONLY_REASONS) - plumbing_only)
    assert not stale, (
        f"PLUMBING_ONLY_REASONS explains {stale}, but they now carry behavioural "
        "coverage tags. Remove the stale exclusions."
    )
    for name, reason in sorted(PLUMBING_ONLY_REASONS.items()):
        assert len(reason.split()) >= 8, f"{name}: reason is too terse to review"


@pytest.mark.parametrize("exact", [True, False])
def test_declared_subcommands_track_the_registered_ones(
    registered: dict[str, list[str]],
    declared: dict[str, dict[str, Any]],
    exact: bool,
) -> None:
    """Exact for behaviourally covered groups, subset-only for help-only ones.

    The asymmetry is proportionate rather than lazy. For a group with behavioural
    scenarios — or one Phase 5 will script — a new subcommand is a new piece of the
    canonical surface and should force a coverage decision; `ingest` in particular
    already has this obligation under CLAUDE.md, which requires the generated contracts
    and fixture registry to be updated when an adapter is added.

    For the twenty help-only groups, exact matching would mean every new `manage`
    utility broke the evaluation suite while changing nothing it covers. The subset
    direction still catches what actually breaks scenarios: a removed or renamed
    subcommand.
    """
    for name, entry in sorted(declared.items()):
        coverage = {t for t in (entry.get("tags") or []) if t.startswith(COVERAGE_TAG_PREFIX)}
        is_plumbing_only = coverage == {PLUMBING_TAG}
        if is_plumbing_only == exact:
            continue
        declared_subs = set(entry.get("subcommands") or [])
        live_subs = set(registered.get(name, []))
        assert not declared_subs - live_subs, (
            f"{name}: declares subcommands the CLI no longer has: "
            f"{sorted(declared_subs - live_subs)}"
        )
        if exact:
            assert not live_subs - declared_subs, (
                f"{name}: has behavioural coverage, so its subcommands must be declared "
                f"exhaustively; missing {sorted(live_subs - declared_subs)}"
            )


# ---------------------------------------------------------------------------
# The help sweep tracks the descriptor
# ---------------------------------------------------------------------------


def _swept_commands() -> list[str]:
    documents = iter_templates(yaml.safe_load(HELP_SWEEP_PATH.read_text(encoding="utf-8")))
    return [step["command"] for document in documents for step in document["steps"]]


def test_help_sweep_covers_exactly_the_declared_commands(
    declared: dict[str, dict[str, Any]],
) -> None:
    """The sweep is the coverage floor, so its membership is load-bearing.

    A declared command absent from the sweep is credited by nothing and surfaces as
    unevaluated. A swept command absent from the descriptor credits an interface nobody
    declared, which inflates nothing but hides a rename. Both are silent, so both fail.
    """
    swept = set(_swept_commands())
    assert swept == set(declared), (
        f"help sweep and declared commands disagree — "
        f"only swept: {sorted(swept - set(declared))}; "
        f"only declared: {sorted(set(declared) - swept)}"
    )


def test_help_sweep_covers_each_command_once(declared: dict[str, dict[str, Any]]) -> None:
    """Batching must partition the commands, not sample them with replacement.

    A duplicated command spends a step on coverage already credited while some other
    command silently has none — and because the totals still look right, the batching is
    where that is easiest to get wrong.
    """
    swept = _swept_commands()
    duplicated = sorted({name for name in swept if swept.count(name) > 1})
    assert not duplicated, f"swept more than once: {duplicated}"


def test_scenario_steps_address_declared_commands(
    scenario_documents: list[tuple[Path, Any]],
    declared: dict[str, dict[str, Any]],
) -> None:
    """A typo in a step's `command` is otherwise invisible.

    gen-eval credits `cli:<command>` from the step, and an unrecognised name simply
    credits an interface the descriptor never declared — no error, no warning, and the
    interface the step *meant* to cover stays unevaluated.
    """
    for path, document in scenario_documents:
        for step in document.get("steps") or []:
            command = step.get("command")
            if not command or command.startswith("-"):
                continue  # a root-level flag credits no interface, by design
            if "{{" in command:
                continue  # covered by the parameter/descriptor agreement test above
            assert command in declared or command in INTENTIONALLY_UNDECLARED_COMMANDS, (
                f"{path.name} step {step['id']!r}: command {command!r} is neither a "
                f"declared command nor listed in INTENTIONALLY_UNDECLARED_COMMANDS"
            )


def test_every_scenario_declares_a_known_category(
    scenario_documents: list[tuple[Path, Any]],
) -> None:
    for path, document in scenario_documents:
        assert document["category"] in KNOWN_CATEGORIES, (
            f"{path.name}: category {document['category']!r} is not one of "
            f"{sorted(KNOWN_CATEGORIES)}"
        )


def test_workflow_submission_covers_every_canonical_operation_type(
    scenario_documents: list[tuple[Path, Any]],
) -> None:
    """The asserted operation handles must track the canonical enum exactly."""
    asserted_operation_types = {
        operation_type
        for _, document in scenario_documents
        if document["category"] == "workflow-submission"
        for step in document["steps"]
        for operation_type in [
            step.get("expect", {}).get("body_contains", {}).get("operation_type")
        ]
        if operation_type is not None
    }
    assert asserted_operation_types == {operation_type.value for operation_type in OperationType}


# ---------------------------------------------------------------------------
# The suite fits inside the pinned runner's limits
# ---------------------------------------------------------------------------


def _account(scenario_documents: list[tuple[Path, Any]], pin: dict[str, Any]) -> SuiteAccount:
    max_expansions = int(pin.get("runner_limits", {}).get("max_expansions_per_template", 100))
    return SuiteAccount(
        [account_template(doc, path, max_expansions) for path, doc in scenario_documents]
    )


def test_suite_accounting_reports_no_static_errors(
    scenario_documents: list[tuple[Path, Any]], pin: dict[str, Any]
) -> None:
    account = _account(scenario_documents, pin)
    assert not account.errors, account.errors


def _capacity(pin: dict[str, Any]):
    limits = pin["runner_limits"]
    return tier_capacity(
        int(limits["max_scenarios_per_iteration"]),
        changed_share=float(limits["tier_changed_share"]),
        critical_share=float(limits["tier_critical_share"]),
        critical_priority_max=int(limits["critical_priority_max"]),
    )


def test_read_only_suite_fits_the_runners_tier_budget(
    scenario_documents: list[tuple[Path, Any]], pin: dict[str, Any]
) -> None:
    """The assertion this suite exists for, and the one that was missing.

    An earlier revision checked only the nominal 50-scenario cap and passed, while the
    run it was guarding evaluated 21 of an expected 39 and reported "PASS (100.0%)" with
    exit 0. The nominal cap was never the binding constraint: the orchestrator buckets
    scenarios and allocates a fixed share per bucket, the change-detection share goes
    unspent without a `--changed-features-ref`, and the non-critical bucket is a third of
    the size the flat number suggests.

    So the check has to model the buckets rather than the total. All three read-only
    categories run in one invocation, so their combined shape is what must fit.
    """
    account = _account(scenario_documents, pin)
    problems = account.overflows(_capacity(pin), set(READ_ONLY_CATEGORIES))
    assert not problems, (
        "the read-only suite would be silently truncated: "
        + "; ".join(problems)
        + ". Remedies, in order of preference: land UPSTREAM.md UP-6 so the cap is "
        "settable and unused tier allocation reflows; group more commands per scenario "
        "in the help sweep (costing masking within a batch); or reduce coverage "
        "deliberately and record it in evaluation/README.md."
    )


def test_help_sweep_sorts_after_behavioural_coverage(
    scenario_documents: list[tuple[Path, Any]], pin: dict[str, Any]
) -> None:
    """If truncation ever happens, it must reach the cheapest coverage first.

    Priority decides which bucket a scenario lands in. The help sweep is the floor —
    valuable, but recoverable from a single `--help` run by hand. Behavioural scenarios
    are the expensive ones, so they take the critical bucket and the sweep takes the
    remainder, never the other way round.
    """
    capacity = _capacity(pin)
    account = _account(scenario_documents, pin)
    sweep = [a for a in account.templates if a.path == HELP_SWEEP_PATH]
    others = [a for a in account.templates if a.path != HELP_SWEEP_PATH]
    assert sweep, f"expected help sweep templates at {HELP_SWEEP_PATH}"
    assert others, "expected behavioural templates alongside the help sweep"
    for template in sweep:
        assert template.priority > capacity.critical_priority_max, (
            f"{template.scenario_id} has priority {template.priority}, which puts the "
            f"help sweep in the critical tier alongside behavioural coverage"
        )
    for template in others:
        assert template.priority <= capacity.critical_priority_max, (
            f"{template.scenario_id} has priority {template.priority}, which drops "
            "behavioural coverage into the same tier the help sweep competes for"
        )
