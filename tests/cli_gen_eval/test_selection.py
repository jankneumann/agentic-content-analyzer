"""Tests for gate-side scenario selection and target resolution (ri-06 Phase 3).

The property under test: the gate runs exactly the scenarios it says it runs, and refuses
rather than reduces when a prerequisite is missing.

Both properties exist because the pinned runner supplies neither. Its `--categories` flag
is inert, so without gate-side selection every run evaluates everything on disk — which
would make Phase 5's mutating scenarios run by default. And a CLI whose canonical surface
is HTTP-only simply fails when no backend is listening, which a pass-rate threshold would
absorb as a low score rather than report as a missing precondition.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.cli_gen_eval.contract import MUTATING_CATEGORIES, READ_ONLY_CATEGORIES
from src.cli_gen_eval.selection import (
    SELECTION_DESCRIPTOR_NAME,
    SELECTION_DIRNAME,
    materialize,
    select,
)
from src.cli_gen_eval.suite import (
    SuiteAccount,
    account_template,
    iter_templates,
    tier_capacity,
)
from src.cli_gen_eval.target import (
    NO_TARGET_TAG,
    REQUIRES_TARGET_TAG,
    TargetState,
    probe,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_ROOT = REPO_ROOT / "evaluation" / "scenarios"
DESCRIPTOR_PATH = REPO_ROOT / "evaluation" / "descriptors" / "aca-cli.yaml"


def scenario(scenario_id: str, category: str, tags: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": scenario_id,
        "name": scenario_id,
        "description": "fixture",
        "category": category,
        "tags": tags or [],
        "interfaces": [],
        "steps": [{"id": "s", "transport": "cli", "command": "capabilities"}],
    }


@pytest.fixture
def suite(tmp_path: Path) -> Path:
    root = tmp_path / "scenarios"
    (root / "plumbing").mkdir(parents=True)
    (root / "discovery").mkdir(parents=True)
    (root / "plumbing" / "a.yaml").write_text(
        yaml.safe_dump(scenario("p-1", "plumbing", [NO_TARGET_TAG]))
    )
    # A multi-scenario file, the shape the real help sweep uses.
    (root / "plumbing" / "b.yaml").write_text(
        yaml.safe_dump(
            [
                scenario("p-2", "plumbing", [NO_TARGET_TAG]),
                scenario("p-3", "plumbing", [NO_TARGET_TAG]),
            ]
        )
    )
    (root / "discovery" / "a.yaml").write_text(
        yaml.safe_dump(scenario("d-1", "discovery", [REQUIRES_TARGET_TAG]))
    )
    return root


# ---------------------------------------------------------------------------
# select()
# ---------------------------------------------------------------------------


def test_selects_by_category(suite: Path) -> None:
    chosen = select(suite, categories={"plumbing"})
    assert sorted(s.scenario_id for s in chosen) == ["p-1", "p-2", "p-3"]


def test_flattens_multi_scenario_files(suite: Path) -> None:
    """A file holding a list must contribute every scenario in it, not one."""
    chosen = select(suite, categories={"plumbing"})
    from_list_file = [s for s in chosen if s.source.name == "b.yaml"]
    assert len(from_list_file) == 2


def test_required_tags_are_conjunctive(suite: Path) -> None:
    """Every named tag must be present.

    Disjunction would be the wrong default for a selection whose job is to *exclude*: a
    scenario needing a backend must not slip into an offline run because one of its other
    tags matched.
    """
    assert select(suite, require_tags={NO_TARGET_TAG, "nonexistent"}) == []
    assert len(select(suite, require_tags={NO_TARGET_TAG})) == 3


def test_tag_selection_excludes_target_dependent_scenarios(suite: Path) -> None:
    chosen = select(suite, categories={"plumbing", "discovery"}, require_tags={NO_TARGET_TAG})
    assert "d-1" not in {s.scenario_id for s in chosen}


def test_unknown_category_selects_nothing(suite: Path) -> None:
    """The gate turns this into a refusal rather than a 0-scenario pass."""
    assert select(suite, categories={"not-a-category"}) == []


# ---------------------------------------------------------------------------
# materialize()
# ---------------------------------------------------------------------------


def test_materialized_descriptor_points_only_at_the_selection(suite: Path, tmp_path: Path) -> None:
    chosen = select(suite, categories={"plumbing"})
    descriptor = yaml.safe_load(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    work = tmp_path / "run"
    work.mkdir()

    path = materialize(chosen, descriptor, work)

    written = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert written["scenario_dirs"] == [SELECTION_DIRNAME]
    materialized = [
        template
        for file in sorted((work / SELECTION_DIRNAME).glob("*.yaml"))
        for template in iter_templates(yaml.safe_load(file.read_text(encoding="utf-8")))
    ]
    assert sorted(t["id"] for t in materialized) == ["p-1", "p-2", "p-3"]


def test_materialized_descriptor_preserves_the_declared_command_surface(
    suite: Path, tmp_path: Path
) -> None:
    """The declared commands are the coverage denominator, so they must survive intact.

    Dropping them would make every partial run report 100% coverage of nothing.
    """
    chosen = select(suite, categories={"discovery"})
    descriptor = yaml.safe_load(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    work = tmp_path / "run"
    work.mkdir()

    written = yaml.safe_load(materialize(chosen, descriptor, work).read_text(encoding="utf-8"))

    original = descriptor["services"][0]["commands"]
    assert written["services"][0]["commands"] == original
    assert len(written["services"][0]["commands"]) == 31


def test_materialize_does_not_leak_a_previous_selection(suite: Path, tmp_path: Path) -> None:
    """The failure mode that would silently widen a run.

    A stale file left in the scratch directory is read by the runner just like a fresh
    one, so a narrow selection would quietly execute a previous wide one — including, once
    Phase 5 lands, mutating scenarios in a run that asked for none.
    """
    descriptor = yaml.safe_load(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    work = tmp_path / "run"
    work.mkdir()

    materialize(select(suite, categories={"plumbing", "discovery"}), descriptor, work)
    materialize(select(suite, categories={"discovery"}), descriptor, work)

    remaining = [
        template
        for file in sorted((work / SELECTION_DIRNAME).glob("*.yaml"))
        for template in iter_templates(yaml.safe_load(file.read_text(encoding="utf-8")))
    ]
    assert sorted(t["id"] for t in remaining) == ["d-1"]


def test_source_paths_that_share_a_basename_do_not_collide(tmp_path: Path) -> None:
    root = tmp_path / "scenarios"
    (root / "plumbing").mkdir(parents=True)
    (root / "discovery").mkdir(parents=True)
    (root / "plumbing" / "same.yaml").write_text(yaml.safe_dump(scenario("p", "plumbing")))
    (root / "discovery" / "same.yaml").write_text(yaml.safe_dump(scenario("d", "discovery")))

    descriptor = yaml.safe_load(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    work = tmp_path / "run"
    work.mkdir()
    materialize(select(root), descriptor, work)

    ids = [
        template["id"]
        for file in sorted((work / SELECTION_DIRNAME).glob("*.yaml"))
        for template in iter_templates(yaml.safe_load(file.read_text(encoding="utf-8")))
    ]
    assert sorted(ids) == ["d", "p"]


def test_descriptor_filename_is_stable(suite: Path, tmp_path: Path) -> None:
    descriptor = yaml.safe_load(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    work = tmp_path / "run"
    work.mkdir()
    assert materialize(select(suite), descriptor, work).name == SELECTION_DESCRIPTOR_NAME


# ---------------------------------------------------------------------------
# target resolution
# ---------------------------------------------------------------------------


def test_probe_reports_a_refused_connection_as_unreachable() -> None:
    reachable, detail = probe("http://127.0.0.1:1", timeout=1.0)
    assert not reachable
    assert "not answering" in detail


@pytest.fixture
def local_server() -> Any:
    """A localhost HTTP server whose /health status the test chooses.

    Deliberately local: a probe test that reaches the internet fails in exactly the
    offline environments this gate is supposed to behave predictably in.
    """
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    def serve(status: int) -> Any:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(status)
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *args: Any) -> None:
                return  # keep pytest output clean

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server

    servers: list[Any] = []

    def factory(status: int) -> str:
        server = serve(status)
        servers.append(server)
        host, port = server.server_address[:2]
        return f"http://{host}:{port}"

    yield factory
    for server in servers:
        server.shutdown()
        server.server_close()


def test_probe_accepts_a_healthy_target(local_server: Any) -> None:
    reachable, detail = probe(local_server(200), timeout=5.0)
    assert reachable, detail


def test_probe_rejects_a_listening_but_unhealthy_target(local_server: Any) -> None:
    """A backend answering 503 on /health is not a usable target.

    Worth pinning separately from a refused connection, because the tempting
    implementation catches only connection errors. An unhealthy-but-listening service
    would then be classified reachable, every discovery scenario would fail, and the
    report would attribute those failures to the CLI rather than to the target.
    """
    reachable, detail = probe(local_server(503), timeout=5.0)
    assert not reachable
    assert "503" in detail


def test_target_states_are_distinct() -> None:
    assert TargetState.REACHABLE != TargetState.UNREACHABLE != TargetState.ABSENT


# ---------------------------------------------------------------------------
# `{{ }}` means two different things, and which one depends on `parameters`
# (ri-06 Phase 5)
# ---------------------------------------------------------------------------


def captured_scenario(**overrides: Any) -> dict[str, Any]:
    """A scenario that captures a value in step one and uses it in step two."""
    document: dict[str, Any] = {
        "id": "capture-fixture",
        "name": "capture fixture",
        "description": "fixture",
        "category": "operation-control",
        "interfaces": [],
        "steps": [
            {
                "id": "submit",
                "transport": "cli",
                "command": "--json",
                "args": ["summarize", "run"],
                "capture": {"operation_id": "$.operation_id"},
            },
            {
                "id": "use",
                "transport": "cli",
                "command": "operations",
                "args": ["get", "{{ operation_id }}"],
            },
        ],
    }
    document.update(overrides)
    return document


def account(document: dict[str, Any]) -> Any:
    return account_template(document, Path("fixture.yaml"), 100)


def test_a_capture_reference_is_not_an_undeclared_parameter() -> None:
    """The distinction the pinned generator draws, and nothing else records.

    `TemplateGenerator._expand_parameters` returns `[raw]` untouched when a template
    declares no `parameters`, so `{{ operation_id }}` is never rendered by Jinja2 and
    reaches the evaluator, which interpolates it from captured values at run time.
    Reading it as a generation-time parameter would reject every scenario that chains
    steps — which is every scenario in the operation-control category.
    """
    assert account(captured_scenario()).errors == []


def test_a_capture_reference_in_a_parameterized_template_is_rejected() -> None:
    """The two mechanisms share `{{ }}` and cannot coexist.

    With a `parameters` block the generator renders the whole template through Jinja2
    with StrictUndefined, so the capture reference raises UndefinedError — logged,
    swallowed, and the expansion silently dropped.
    """
    document = captured_scenario(parameters={"limit": ["1", "2"]})
    document["steps"][1]["args"].append("{{ limit }}")
    errors = account(document).errors
    assert any("destroyed before the evaluator" in error for error in errors)


def test_a_reference_to_a_name_nothing_captures_is_rejected() -> None:
    document = captured_scenario()
    document["steps"][0].pop("capture")
    errors = account(document).errors
    assert any("no step captures" in error for error in errors)
    assert any("literal braces are dispatched" in error for error in errors)


def test_a_reference_before_its_capture_is_rejected() -> None:
    """Interpolation reads what earlier steps bound; a forward reference binds nothing."""
    document = captured_scenario()
    document["steps"].reverse()
    errors = account(document).errors
    assert any("before the step that captures it has run" in error for error in errors)


def test_the_checked_in_mutating_scenarios_use_capture_correctly() -> None:
    templates = [
        item.template for item in select(SCENARIO_ROOT, categories=set(MUTATING_CATEGORIES))
    ]
    assert templates, "the mutating categories must be populated"
    for template in templates:
        assert account(template).errors == [], template["id"]


# ---------------------------------------------------------------------------
# The gate refuses a selection that would be truncated, before it runs
# ---------------------------------------------------------------------------


def _capacity_and_expansions(pin: dict[str, Any]):
    limits = pin["runner_limits"]
    return (
        tier_capacity(
            int(limits["max_scenarios_per_iteration"]),
            changed_share=float(limits["tier_changed_share"]),
            critical_share=float(limits["tier_critical_share"]),
            critical_priority_max=int(limits["critical_priority_max"]),
        ),
        int(limits["max_expansions_per_template"]),
    )


def _overflows(categories: set[str] | None) -> list[str]:
    pin = json.loads((REPO_ROOT / "evaluation" / "contract" / "pin.json").read_text())
    capacity, max_expansions = _capacity_and_expansions(pin)
    selected = select(SCENARIO_ROOT, categories=categories)
    return SuiteAccount(
        [account_template(item.template, item.source, max_expansions) for item in selected]
    ).overflows(capacity)


def test_each_supported_selection_fits_the_runners_tier_budget() -> None:
    """Both dispatched runs fit. Neither is close enough to the cap to be a surprise."""
    assert _overflows(set(READ_ONLY_CATEGORIES)) == []
    assert _overflows(set(MUTATING_CATEGORIES)) == []


def test_the_combined_selection_does_not_fit_and_that_is_recorded() -> None:
    """Read-only and mutating are separate dispatches, and this is one reason why.

    Together they exceed the pinned runner's critical tier, which it would resolve by
    dropping scenarios and exiting 0. That is not a silent failure here — the gate
    computes the same arithmetic before the run and refuses — but the number is worth
    pinning, because it is the thing that changes when UPSTREAM.md UP-6 lands or when
    the suite grows. When this test starts failing because the selection now fits, the
    two runs can be merged.
    """
    problems = _overflows(set(READ_ONLY_CATEGORIES | MUTATING_CATEGORIES))
    assert problems, "a combined run now fits; see UPSTREAM.md UP-6 before merging them"
    assert "critical tier" in problems[0]
