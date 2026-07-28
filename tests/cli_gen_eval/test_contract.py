"""Contract-layer tests for the gen-eval evaluation contract (ri-06 Phase 1).

The property under test throughout: contract validation is *runner-independent*. It
must reach a definite verdict with no gen-eval installed, never skip, and never import
gen_eval. That is what allows CI to enforce even when runner acquisition fails.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

from src.cli_gen_eval import CONTRACT_VERSION
from src.cli_gen_eval.contract import (
    KNOWN_CATEGORIES,
    MUTATING_CATEGORIES,
    ContractError,
    is_mutating,
    schema,
    validate_descriptor,
    validate_report,
    validate_scenario,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PIN_PATH = REPO_ROOT / "evaluation" / "contract" / "pin.json"
DURABLE_DIR = REPO_ROOT / "openspec" / "contracts" / "cli-gen-eval"
RUNTIME_DIR = REPO_ROOT / "src" / "cli_gen_eval" / "schemas"
VALIDATOR = REPO_ROOT / "scripts" / "validate_gen_eval_contract.py"

SCHEMA_FILENAMES = (
    "interface-descriptor.schema.json",
    "scenario.schema.json",
    "eval-report.schema.json",
)


def minimal_descriptor() -> dict[str, Any]:
    """Smallest descriptor the pinned schema accepts. ``startup`` is required."""
    return {
        "project": "agentic-newsletter-aggregator",
        "version": "0.1.0",
        "services": [{"name": "cli", "type": "cli", "command": "aca"}],
        "startup": {
            "command": "true",
            "health_check": "true",
            "teardown": "true",
        },
    }


def minimal_scenario(category: str = "plumbing") -> dict[str, Any]:
    return {
        "id": "cli-version",
        "name": "aca --version exits 0",
        "description": "Smallest possible plumbing check.",
        "category": category,
        "interfaces": ["cli:--version"],
        "steps": [
            {
                "id": "version",
                "transport": "cli",
                "args": ["--version"],
                "expect": {"exit_code": 0, "not_empty": True},
            }
        ],
    }


def minimal_report(total: int = 1, passed: int = 1) -> dict[str, Any]:
    return {
        "total_scenarios": total,
        "passed": passed,
        "failed": total - passed,
        "errors": 0,
        "skipped": 0,
        "pass_rate": (passed / total) if total else 0.0,
        "coverage_pct": 100.0,
        "duration_seconds": 1.5,
        "budget_exhausted": False,
        "iterations_completed": 1,
        "cost_summary": {"cli_calls": 0.0, "time_minutes": 0.1, "sdk_cost_usd": 0.0},
        "per_interface": {"cli:--version": {"pass": passed, "fail": total - passed, "error": 0}},
        "per_category": {
            "plumbing": {"pass": passed, "fail": total - passed, "error": 0, "total": total}
        },
        "unevaluated_interfaces": [],
        "verdicts": [
            {
                "scenario_id": "cli-version",
                "scenario_name": "aca --version exits 0",
                "status": "pass",
                "steps": [],
            }
        ],
    }


# ── Pin and schema provenance ──────────────────────────────────────────────────


def test_pin_declares_required_keys() -> None:
    pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    for key in (
        "contract_version",
        "runner_package",
        "runner_source",
        "runner_subdirectory",
        "runner_ref",
        "schemas_generated_from_ref",
    ):
        assert pin.get(key), f"pin.json missing {key!r}"


def test_contract_version_agrees_across_pin_module_and_schemas() -> None:
    """Three-way agreement. A regenerated schema that forgot the pin bump fails here."""
    pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    assert pin["contract_version"] == CONTRACT_VERSION

    for kind in ("descriptor", "scenario", "report"):
        assert schema(kind)["x-gen-eval-contract-version"] == CONTRACT_VERSION


def test_schemas_record_the_generating_ref() -> None:
    pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    for kind in ("descriptor", "scenario", "report"):
        assert schema(kind)["x-generated-from-ref"] == pin["schemas_generated_from_ref"]


@pytest.mark.parametrize("filename", SCHEMA_FILENAMES)
def test_durable_and_runtime_schema_copies_are_byte_identical(filename: str) -> None:
    """Same parity guarantee release-smoke enforces for its evidence schema."""
    durable = (DURABLE_DIR / filename).read_bytes()
    runtime = (RUNTIME_DIR / filename).read_bytes()
    assert durable == runtime, (
        f"{filename} differs between openspec/contracts/cli-gen-eval/ and "
        f"src/cli_gen_eval/schemas/; regenerate with "
        f"scripts/generate_gen_eval_contract_schemas.py"
    )


def test_stale_vendored_schema_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A schema annotated with a different contract version must not validate anything."""
    monkeypatch.setattr("src.cli_gen_eval.contract.CONTRACT_VERSION", "999")
    schema.cache_clear()
    try:
        with pytest.raises(ContractError, match="contract version"):
            schema("descriptor")
    finally:
        schema.cache_clear()


# ── Runner independence ────────────────────────────────────────────────────────


def test_contract_layer_does_not_import_gen_eval() -> None:
    """Static check: no module in the contract layer may import the framework."""
    targets = [*(REPO_ROOT / "src" / "cli_gen_eval").rglob("*.py"), VALIDATOR]
    offenders: list[str] = []
    for path in targets:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name == "gen_eval" or name.startswith("gen_eval.") for name in names):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert not offenders, f"contract layer imports gen_eval at {offenders}"


def test_validator_reaches_a_verdict_with_no_runner_available(tmp_path: Path) -> None:
    """The headline Phase 1 property: definite exit status, no skip, no runner.

    PATH is emptied of any gen-eval and the override points at a nonexistent binary.
    """
    descriptor = tmp_path / "descriptor.yaml"
    descriptor.write_text(json.dumps(minimal_descriptor()), encoding="utf-8")

    env = {
        "PATH": "/usr/bin:/bin",
        "ACA_GEN_EVAL_BIN": str(tmp_path / "definitely-not-here"),
        "PYTHONPATH": str(REPO_ROOT),
    }
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR), "--descriptor", str(descriptor)],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    combined = completed.stdout + completed.stderr
    assert "SKIP" not in combined.upper(), "contract validation must never skip"


def test_validator_fails_on_invalid_descriptor(tmp_path: Path) -> None:
    descriptor = tmp_path / "descriptor.yaml"
    broken = minimal_descriptor()
    del broken["services"]
    descriptor.write_text(json.dumps(broken), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(VALIDATOR), "--descriptor", str(descriptor)],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(REPO_ROOT)},
        cwd=REPO_ROOT,
        check=False,
    )
    assert completed.returncode == 1
    assert "services" in completed.stdout + completed.stderr


# ── Descriptor validation ──────────────────────────────────────────────────────


def test_minimal_descriptor_is_valid() -> None:
    assert validate_descriptor(minimal_descriptor()) == []


def test_descriptor_requires_services() -> None:
    document = minimal_descriptor()
    del document["services"]
    errors = validate_descriptor(document)
    assert any("services" in error for error in errors)


def test_descriptor_rejects_unknown_service_type() -> None:
    document = minimal_descriptor()
    document["services"][0]["type"] = "telepathy"
    assert validate_descriptor(document) != []


def test_descriptor_rejects_non_object() -> None:
    assert validate_descriptor(["not", "a", "descriptor"]) != []


# ── Scenario validation ────────────────────────────────────────────────────────


def test_minimal_scenario_is_valid() -> None:
    assert validate_scenario(minimal_scenario()) == []


@pytest.mark.parametrize("category", sorted(KNOWN_CATEGORIES))
def test_every_declared_category_is_accepted(category: str) -> None:
    assert validate_scenario(minimal_scenario(category)) == []


def test_scenario_rejects_undeclared_category() -> None:
    errors = validate_scenario(minimal_scenario("freeform"))
    assert any("category" in error for error in errors)


def test_scenario_requires_steps() -> None:
    document = minimal_scenario()
    del document["steps"]
    assert any("steps" in error for error in validate_scenario(document))


def test_scenario_rejects_unknown_transport() -> None:
    document = minimal_scenario()
    document["steps"][0]["transport"] = "carrier-pigeon"
    assert validate_scenario(document) != []


def test_mutating_categories_are_classified() -> None:
    assert is_mutating("workflow-submission")
    assert is_mutating("operation-control")
    assert not is_mutating("plumbing")
    assert not is_mutating("discovery")
    assert not is_mutating("validation")
    assert MUTATING_CATEGORIES.isdisjoint({"plumbing", "discovery", "validation"})


# ── Report validation (schema conformance only) ─────────────────────────────────


def test_minimal_report_is_valid() -> None:
    assert validate_report(minimal_report()) == []


def test_report_requires_unevaluated_interfaces() -> None:
    """Phase 4's coverage assertion reads this key, so its absence is malformed."""
    document = minimal_report()
    del document["unevaluated_interfaces"]
    assert any("unevaluated_interfaces" in error for error in validate_report(document))


def test_report_requires_per_category() -> None:
    document = minimal_report()
    del document["per_category"]
    assert any("per_category" in error for error in validate_report(document))


def test_report_schema_does_not_bound_numeric_ranges() -> None:
    """Records a deliberate limit of the published contract.

    The upstream schema is generated from pydantic models that declare no bounds, so
    ``pass_rate: 1.5`` and a negative ``total_scenarios`` are both schema-VALID. We
    vendor the published schema verbatim rather than tightening our copy — a locally
    stricter copy would disagree with upstream's own drift test and defeat the point of
    a shared contract.

    Range sanity therefore belongs to the report validator (Phase 4), alongside the
    other sufficiency rules. Suggested upstream as UP-5.
    """
    document = minimal_report()
    document["pass_rate"] = 1.5
    assert validate_report(document) == []

    document = minimal_report()
    document["total_scenarios"] = -1
    assert validate_report(document) == []


def test_report_rejects_wrong_types() -> None:
    """What the schema does still catch: type errors."""
    document = minimal_report()
    document["pass_rate"] = "not a number"
    assert validate_report(document) != []


def test_zero_scenario_report_is_schema_valid_but_not_sufficient() -> None:
    """Records the boundary between the two validators.

    A zero-scenario report is *well-formed* — schema validation cannot reject it, and
    must not pretend to. Rejecting it is the report validator's job (Phase 4, D7), which
    is precisely why threshold enforcement alone is insufficient.
    """
    document = minimal_report(total=0, passed=0)
    document["per_interface"] = {}
    document["per_category"] = {}
    document["verdicts"] = []
    assert validate_report(document) == []
    assert document["pass_rate"] == 0.0


# ── Dependency hygiene ─────────────────────────────────────────────────────────


def _requirement_name(requirement: str) -> str:
    """Extract the distribution name from a PEP 508 requirement string."""
    name = requirement.strip()
    for separator in ("[", "@", "=", ">", "<", "!", "~", ";", " "):
        name = name.split(separator, 1)[0]
    return name.strip().lower().replace("_", "-")


def test_no_dependency_declares_gen_eval() -> None:
    """D1: gen-eval must never appear as a dependency, extra requirement, or source.

    Compares *distribution names*, not raw substrings. The contract layer's own extra is
    named ``gen-eval`` — that name is fine, and matching on it would be a false positive.
    What must never appear is the gen-eval package as a requirement.
    """
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject.get("project", {})

    declared: list[tuple[str, str]] = [
        ("dependencies", requirement) for requirement in project.get("dependencies", [])
    ]
    for extra, requirements in project.get("optional-dependencies", {}).items():
        declared.extend((f"optional-dependencies.{extra}", req) for req in requirements)

    offenders = [
        f"{where}: {requirement}"
        for where, requirement in declared
        if _requirement_name(requirement) == "gen-eval"
    ]
    assert not offenders, f"gen-eval must not be a declared requirement: {offenders}"

    sources = pyproject.get("tool", {}).get("uv", {}).get("sources", {})
    offending_sources = [key for key in sources if key.lower().replace("_", "-") == "gen-eval"]
    assert not offending_sources, f"gen-eval must not appear in [tool.uv.sources]: {sources}"


def test_gen_eval_extra_carries_no_framework_requirement() -> None:
    """The contract-layer extra must stay jsonschema-only.

    Named separately from the check above because this is the extra most likely to
    acquire a gen-eval requirement by well-meaning accident.
    """
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extra = pyproject["project"]["optional-dependencies"]["gen-eval"]
    names = {_requirement_name(requirement) for requirement in extra}
    assert names == {"jsonschema"}, f"gen-eval extra should be jsonschema-only, got {names}"


def test_lockfile_does_not_contain_gen_eval() -> None:
    """The lockfile is the real proof that resolution is unaffected."""
    lock = REPO_ROOT / "uv.lock"
    if not lock.exists():
        pytest.skip("uv.lock not present in this checkout")
    text = lock.read_text(encoding="utf-8")
    assert 'name = "gen-eval"' not in text
