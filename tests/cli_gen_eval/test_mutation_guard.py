"""Tests for the mutating-category target guard (ri-06 Phase 5).

The property under test is a negative one, and negatives are easy to test badly. "The
guard refused" is not the claim — a guard that refuses everything refuses correctly here
and is useless. The claim is that it refuses *these* targets, permits *that* one, and in
every refusal reaches its decision with nothing submitted.

That last clause is why several tests below assert on `subprocess.run` never being
called rather than on a return value. A guard that decided correctly but decided late —
after the runner had already been handed a selection — would satisfy every assertion
about its verdict and none about its purpose.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, get_args

import pytest

from src.cli_gen_eval.contract import MUTATING_CATEGORIES, READ_ONLY_CATEGORIES
from src.cli_gen_eval.mutation_guard import (
    MUTABLE_TARGET_CLASSES,
    evaluate,
    load_policy,
)
from src.cli_gen_eval.selection import select
from src.release_smoke.models import TargetClass

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_ROOT = REPO_ROOT / "evaluation" / "scenarios"

STAGING_ORIGIN = "https://api-staging.example.com"
PRODUCTION_ORIGIN = "https://api.example.com"


def policy_document(**overrides: Any) -> dict[str, Any]:
    """A valid staging policy, before whatever the caller breaks about it."""
    document: dict[str, Any] = {
        "target_id": "aca-staging",
        "target": "staging",
        "frontend_origin": "https://staging.example.com",
        "api_origin": STAGING_ORIGIN,
        "expected_frontend_revision": "a" * 40,
        "expected_api_revision": "b" * 40,
        "production_target_ids": ["aca-production"],
        "production_origins": [PRODUCTION_ORIGIN, "https://app.example.com"],
    }
    document.update(overrides)
    return document


def _guard_code() -> str:
    """The guard module's source with every docstring and comment removed.

    Prose about production is not a second classification of it; code is. Stripping both
    is what lets the single-sourcing tests below assert on `production` appearing at all.
    Done through `ast` rather than by splitting on quote characters, because the naive
    version silently truncates at the first function docstring and then asserts over a
    fragment of the module — passing for the wrong reason.
    """
    source = (REPO_ROOT / "src" / "cli_gen_eval" / "mutation_guard.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            body.pop(0)
    return ast.unparse(tree)  # comments do not survive a round trip


def _explode(*args: Any, **kwargs: Any) -> None:
    raise AssertionError(f"nothing may be executed on a refusal path: {args}")


@pytest.fixture(autouse=True)
def clean_gate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """No ambient gate configuration may reach a guard test."""
    for name in ("ACA_GEN_EVAL_TARGET_POLICY", "ACA_GEN_EVAL_REQUIRE", "ACA_GEN_EVAL_BIN"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def write_policy(tmp_path: Path):
    def _write(**overrides: Any) -> Path:
        path = tmp_path / "target-policy.json"
        path.write_text(json.dumps(policy_document(**overrides)), encoding="utf-8")
        return path

    return _write


# ---------------------------------------------------------------------------
# What the guard permits. Asserted first: a guard whose accept path is broken is
# indistinguishable from one that works, if only the refusals are tested.
# ---------------------------------------------------------------------------


def test_a_staging_target_the_cli_actually_dials_is_permitted(write_policy) -> None:
    verdict = evaluate(["workflow-submission"], write_policy(), STAGING_ORIGIN)
    assert verdict.allowed
    assert verdict.policy is not None
    assert verdict.guarded_categories == ["workflow-submission"]


def test_an_ephemeral_target_is_permitted(write_policy) -> None:
    verdict = evaluate(["operation-control"], write_policy(target="ephemeral"), STAGING_ORIGIN)
    assert verdict.allowed


def test_a_read_only_selection_needs_no_policy_at_all() -> None:
    verdict = evaluate(sorted(READ_ONLY_CATEGORIES), None, "http://localhost:8000")
    assert verdict.allowed
    assert verdict.guarded_categories == []
    assert verdict.policy is None


def test_a_trailing_slash_is_not_a_different_target(write_policy) -> None:
    """The CLI's settings may carry one; the policy's api_origin never does."""
    verdict = evaluate(["workflow-submission"], write_policy(), f"{STAGING_ORIGIN}/")
    assert verdict.allowed


# ---------------------------------------------------------------------------
# Task 5.1: the three refusal paths the spec names.
# ---------------------------------------------------------------------------


def test_a_mutating_category_with_no_policy_is_refused() -> None:
    verdict = evaluate(["workflow-submission"], None, STAGING_ORIGIN)
    assert verdict.refused
    assert verdict.guarded_categories == ["workflow-submission"]
    joined = " ".join(verdict.reasons)
    assert "workflow-submission" in joined
    assert "--target-policy" in joined


def test_a_production_target_class_is_refused(write_policy) -> None:
    path = write_policy(
        target="production",
        target_id="aca-production",
        api_origin=PRODUCTION_ORIGIN,
        frontend_origin="https://app.example.com",
    )
    verdict = evaluate(["workflow-submission"], path, PRODUCTION_ORIGIN)
    assert verdict.refused
    assert any("classified 'production'" in reason for reason in verdict.reasons)


def test_a_non_production_target_using_a_production_identity_is_refused(write_policy) -> None:
    """Rejected by ProtectedTargetPolicy itself — the guard adds no rule of its own."""
    path = write_policy(target_id="aca-production")
    verdict = evaluate(["workflow-submission"], path, STAGING_ORIGIN)
    assert verdict.refused
    assert any("production identity" in reason for reason in verdict.reasons)


def test_a_non_production_target_resolving_to_a_production_origin_is_refused(
    write_policy,
) -> None:
    path = write_policy(api_origin=PRODUCTION_ORIGIN)
    verdict = evaluate(["workflow-submission"], path, PRODUCTION_ORIGIN)
    assert verdict.refused
    assert any("production origin" in reason for reason in verdict.reasons)


def test_a_mutation_capable_target_without_deny_registries_is_refused(write_policy) -> None:
    """An empty registry would make every identity check vacuously pass."""
    path = write_policy(production_target_ids=[], production_origins=[])
    verdict = evaluate(["workflow-submission"], path, STAGING_ORIGIN)
    assert verdict.refused
    assert any("deny registries" in reason for reason in verdict.reasons)


# ---------------------------------------------------------------------------
# The binding between the policy and the target the scenarios will actually use.
# Without this the policy is a claim about a target nobody is pointed at.
# ---------------------------------------------------------------------------


def test_a_valid_staging_policy_for_a_different_target_is_refused(write_policy) -> None:
    verdict = evaluate(["workflow-submission"], write_policy(), PRODUCTION_ORIGIN)
    assert verdict.refused
    assert any(
        "the CLI will submit to https://api.example.com" in reason for reason in verdict.reasons
    )
    assert any("is a registered production origin" in reason for reason in verdict.reasons)


def test_a_valid_staging_policy_against_localhost_is_refused(write_policy) -> None:
    """The likeliest accident: a correct policy file and an unchanged local profile."""
    verdict = evaluate(["workflow-submission"], write_policy(), "http://localhost:8000")
    assert verdict.refused
    assert any("is not about this target" in reason for reason in verdict.reasons)


def test_an_unresolvable_base_url_is_refused_rather_than_assumed(write_policy) -> None:
    verdict = evaluate(["workflow-submission"], write_policy(), None)
    assert verdict.refused
    assert any("could not be resolved" in reason for reason in verdict.reasons)


def test_a_base_url_that_is_not_a_bare_origin_is_refused(write_policy) -> None:
    verdict = evaluate(
        ["workflow-submission"], write_policy(), "https://api-staging.example.com/api/v1"
    )
    assert verdict.refused
    assert any("is not a bare origin" in reason for reason in verdict.reasons)


def test_every_reason_is_reported_not_just_the_first(write_policy) -> None:
    """Two mistakes in one invocation should cost one round trip, not two."""
    path = write_policy(
        target="production",
        target_id="aca-production",
        api_origin=PRODUCTION_ORIGIN,
        frontend_origin="https://app.example.com",
    )
    verdict = evaluate(["workflow-submission"], path, "https://elsewhere.example.com")
    assert verdict.refused
    assert len(verdict.reasons) == 2
    assert any("classified 'production'" in reason for reason in verdict.reasons)
    assert any("is not about this target" in reason for reason in verdict.reasons)


# ---------------------------------------------------------------------------
# Unusable policy documents. A guard that cannot read its policy must not proceed.
# ---------------------------------------------------------------------------


def test_a_missing_policy_file_is_refused(tmp_path: Path) -> None:
    verdict = evaluate(["workflow-submission"], tmp_path / "absent.json", STAGING_ORIGIN)
    assert verdict.refused
    assert any("could not be read" in reason for reason in verdict.reasons)


def test_an_unparseable_policy_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "target-policy.json"
    path.write_text("{not json", encoding="utf-8")
    verdict = evaluate(["workflow-submission"], path, STAGING_ORIGIN)
    assert verdict.refused
    assert any("not valid JSON" in reason for reason in verdict.reasons)


def test_load_policy_never_raises(tmp_path: Path) -> None:
    """Callers branch on the verdict; an exception path would bypass the branch."""
    for content in ("{not json", "[]", "null", json.dumps({"target": "staging"})):
        path = tmp_path / "policy.json"
        path.write_text(content, encoding="utf-8")
        policy, errors = load_policy(path)
        assert policy is None
        assert errors


# ---------------------------------------------------------------------------
# Task 5.2: the classification is single-sourced on release-smoke's model.
# ---------------------------------------------------------------------------


def test_the_mutable_classes_are_a_subset_of_release_smoke_target_classes() -> None:
    assert set(get_args(TargetClass)) > MUTABLE_TARGET_CLASSES


def test_the_guard_defines_no_target_classification_of_its_own() -> None:
    """D6: exactly one place decides what production is.

    Read as source rather than asserted through behaviour on purpose. A second
    classification would not change any verdict on the day it was introduced — it would
    change one later, after the two copies drifted, which is precisely when no test is
    being written.
    """
    code = _guard_code()

    assert "class TargetClass" not in code
    assert "Literal[" not in code
    assert "Enum" not in code
    assert "ProtectedTargetPolicy" in code

    # The precise claim: of release-smoke's four target classes, the only ones this
    # module names as literal values are the two it permits. `production` and `local`
    # appear nowhere as a value — naming either would mean the guard had started
    # deciding for itself what they are, instead of asking the policy.
    named = {
        node.value
        for node in ast.walk(ast.parse(code))
        if isinstance(node, ast.Constant) and node.value in set(get_args(TargetClass))
    }
    assert named == set(MUTABLE_TARGET_CLASSES)


def test_the_guard_never_inspects_the_deny_registries_itself(write_policy) -> None:
    """Every deny-registry refusal must come from the model, not from this module.

    `production_target_ids` appears nowhere in the guard's code: the identity rule is
    the model's entirely. `production_origins` appears once, applied to the *live*
    resolved origin rather than to the policy's declaration of itself — a check the
    model structurally cannot make, since it never sees the CLI's settings.
    """
    code = _guard_code()
    assert "production_target_ids" not in code
    assert code.count("production_origins") == 2  # the live-origin check, and its message

    # And the refusals the model owns still happen through this guard.
    for overrides in (
        {"target_id": "aca-production"},
        {"production_target_ids": [], "production_origins": []},
    ):
        assert evaluate(["workflow-submission"], write_policy(**overrides), STAGING_ORIGIN).refused


# ---------------------------------------------------------------------------
# Task 5.5: the default pull-request run cannot reach a mutating scenario.
# ---------------------------------------------------------------------------


def test_the_gate_defaults_to_the_read_only_categories(monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserted through the gate's behaviour, not by reading its source."""
    from scripts import run_gen_eval_gate

    seen: list[list[str]] = []

    def record(categories, policy_path, base_url):
        seen.append(sorted(categories))
        raise SystemExit(99)

    monkeypatch.setattr(run_gen_eval_gate, "evaluate_guard", record)
    monkeypatch.setattr(run_gen_eval_gate.subprocess, "run", _explode)
    monkeypatch.setattr("sys.argv", ["run_gen_eval_gate.py", "--skip-contract"])

    with pytest.raises(SystemExit):
        run_gen_eval_gate.main()

    assert seen == [sorted(READ_ONLY_CATEGORIES)]
    assert not (READ_ONLY_CATEGORIES & MUTATING_CATEGORIES)


def test_the_default_selection_resolves_to_no_mutating_scenario() -> None:
    selected = select(SCENARIO_ROOT, categories=set(READ_ONLY_CATEGORIES))
    assert selected, "the read-only selection must not be empty"
    assert {item.category for item in selected} <= READ_ONLY_CATEGORIES


def test_mutating_scenarios_exist_on_disk_and_are_still_excluded() -> None:
    """The exclusion is only meaningful once there is something to exclude.

    Before Phase 5 this test would have passed vacuously — there were no mutating
    scenarios to leave out. It asserts both halves so it cannot go quiet again.
    """
    everything = select(SCENARIO_ROOT)
    mutating = {item.scenario_id for item in everything if item.category in MUTATING_CATEGORIES}
    assert mutating, "Phase 5 checks in mutating scenarios; this test guards their exclusion"

    default = {item.scenario_id for item in select(SCENARIO_ROOT, set(READ_ONLY_CATEGORIES))}
    assert not (mutating & default)


def test_every_mutating_scenario_declares_it_needs_a_target() -> None:
    """A mutating scenario tagged `no-target` would run under --offline, unguarded."""
    for item in select(SCENARIO_ROOT, categories=set(MUTATING_CATEGORIES)):
        assert "requires-target" in item.tags, item.scenario_id
        assert "no-target" not in item.tags, item.scenario_id


# ---------------------------------------------------------------------------
# Task 5.1's final clause: no workflow is submitted in any rejection path.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv_extra",
    [
        pytest.param([], id="no-policy"),
        pytest.param(["--target-policy", "PRODUCTION"], id="production-policy"),
        pytest.param(["--target-policy", "WRONG_TARGET"], id="policy-for-another-target"),
    ],
)
def test_the_gate_refuses_before_running_anything(
    argv_extra: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_policy,
) -> None:
    from scripts import run_gen_eval_gate

    policies = {
        "PRODUCTION": write_policy(
            target="production",
            target_id="aca-production",
            api_origin=PRODUCTION_ORIGIN,
            frontend_origin="https://app.example.com",
        ),
        "WRONG_TARGET": write_policy(),
    }
    argv = ["--categories", "workflow-submission", *argv_extra]
    argv = [str(policies[part]) if part in policies else part for part in argv]
    output_dir = tmp_path / "reports"
    argv += ["--output-dir", str(output_dir)]

    monkeypatch.setattr(run_gen_eval_gate.subprocess, "run", _explode)
    monkeypatch.setattr(run_gen_eval_gate, "resolve", _explode)
    monkeypatch.setattr(
        run_gen_eval_gate, "resolve_base_url", lambda *a, **k: ("http://localhost:8000", "local")
    )
    monkeypatch.setattr("sys.argv", ["run_gen_eval_gate.py", *argv])

    status = run_gen_eval_gate.main()

    assert status == run_gen_eval_gate.EXIT_MUTATION_REFUSED
    # `resolve` and `subprocess.run` both explode if reached: the refusal is decided
    # before a runner is even looked for, let alone invoked. And a written selection is
    # a loaded gun — the next run's `--offline` would find it — so nothing is on disk.
    assert not output_dir.exists()


def test_the_environment_variable_supplies_the_policy(
    monkeypatch: pytest.MonkeyPatch, write_policy
) -> None:
    """CI dispatches the mutating run with a secret path, not an argv the logs keep."""
    from scripts import run_gen_eval_gate

    monkeypatch.setenv("ACA_GEN_EVAL_TARGET_POLICY", str(write_policy()))
    monkeypatch.setattr(
        run_gen_eval_gate, "resolve_base_url", lambda *a, **k: (PRODUCTION_ORIGIN, "prod")
    )
    monkeypatch.setattr(run_gen_eval_gate.subprocess, "run", _explode)
    monkeypatch.setattr(run_gen_eval_gate, "resolve", _explode)
    monkeypatch.setattr(
        "sys.argv",
        ["run_gen_eval_gate.py", "--categories", "workflow-submission"],
    )

    # The env-supplied policy is read, and then refused for the right reason: it
    # describes staging while the CLI is pointed at production.
    assert run_gen_eval_gate.main() == run_gen_eval_gate.EXIT_MUTATION_REFUSED


def test_the_gate_refuses_before_subprocess_when_deployment_identity_is_untrusted(
    monkeypatch: pytest.MonkeyPatch, write_policy
) -> None:
    from scripts import run_gen_eval_gate
    from src.release_smoke.runner import ReleaseSmokeError

    policy_path = write_policy()
    monkeypatch.setattr(
        run_gen_eval_gate, "resolve_base_url", lambda *a, **k: (STAGING_ORIGIN, "staging")
    )
    monkeypatch.setattr(
        run_gen_eval_gate,
        "verify_api_identity",
        lambda *a, **k: (_ for _ in ()).throw(ReleaseSmokeError("revision mismatch")),
    )
    monkeypatch.setattr(run_gen_eval_gate.subprocess, "run", _explode)
    monkeypatch.setattr(run_gen_eval_gate, "resolve", _explode)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_gen_eval_gate.py",
            "--categories",
            "workflow-submission",
            "--target-policy",
            str(policy_path),
        ],
    )

    assert run_gen_eval_gate.main() == run_gen_eval_gate.EXIT_MUTATION_REFUSED


def test_the_refusal_exit_code_is_distinct_from_every_other_outcome() -> None:
    from scripts import run_gen_eval_gate

    codes = {
        run_gen_eval_gate.EXIT_TARGET_UNREACHABLE,
        run_gen_eval_gate.EXIT_REPORT_NOT_CREDIBLE,
        run_gen_eval_gate.EXIT_MUTATION_REFUSED,
    }
    assert len(codes) == 3
    assert run_gen_eval_gate.EXIT_MUTATION_REFUSED not in {0, 1, 2, 3}


def test_subprocess_is_the_only_way_the_gate_executes_anything() -> None:
    """Pins the assumption the refusal tests rest on.

    They prove nothing was submitted by asserting `subprocess.run` was not called. If the
    gate ever grew a second execution path, those assertions would keep passing while
    protecting nothing.
    """
    source = (REPO_ROOT / "scripts" / "run_gen_eval_gate.py").read_text(encoding="utf-8")
    assert source.count("subprocess.run") == 2  # contract validator, then the runner
    for forbidden in ("os.system", "Popen", "os.exec", "asyncio.create_subprocess"):
        assert forbidden not in source


def test_the_checked_in_example_policy_is_a_valid_policy() -> None:
    """An example that does not load is worse than no example.

    It carries no explanatory keys because `ProtectedTargetPolicy` forbids extra fields,
    so a `_comment` would make the file fail the moment someone copied it. The
    explanation lives in evaluation/README.md instead.
    """
    policy, errors = load_policy(REPO_ROOT / "evaluation" / "target-policy.example.json")
    assert errors == []
    assert policy is not None
    assert policy.target in MUTABLE_TARGET_CLASSES


def test_the_example_policy_cannot_be_used_as_it_ships() -> None:
    """Its hosts are under .invalid, so it can only ever describe a target nobody has."""
    verdict = evaluate(
        ["workflow-submission"],
        REPO_ROOT / "evaluation" / "target-policy.example.json",
        "https://api-staging.example.com",
    )
    assert verdict.refused


def test_release_smoke_mutation_helper_agrees_on_the_mutable_classes() -> None:
    """If release-smoke ever permits `local`, this suite should be told, not surprised."""
    source = (REPO_ROOT / "src" / "release_smoke" / "mutation.py").read_text(encoding="utf-8")
    assert 'policy.target not in {"staging", "ephemeral"}' in source
    assert frozenset({"staging", "ephemeral"}) == MUTABLE_TARGET_CLASSES
