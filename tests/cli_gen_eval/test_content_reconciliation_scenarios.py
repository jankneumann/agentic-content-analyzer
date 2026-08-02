"""RI-08 gen-eval contracts for bounded Content reconciliation controls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.cli_gen_eval.contract import MUTATING_CATEGORIES, READ_ONLY_CATEGORIES
from src.cli_gen_eval.selection import select

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_ROOT = REPO_ROOT / "evaluation" / "scenarios"
DESCRIPTOR = REPO_ROOT / "evaluation" / "descriptors" / "aca-cli.yaml"


def _scenario(relative_path: str) -> dict[str, Any]:
    document = yaml.safe_load((SCENARIO_ROOT / relative_path).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def test_descriptor_declares_reconciliation_under_operations() -> None:
    descriptor = yaml.safe_load(DESCRIPTOR.read_text(encoding="utf-8"))
    commands = descriptor["services"][0]["commands"]
    operations = next(command for command in commands if command["name"] == "operations")

    assert "reconcile-content" in operations["subcommands"]


def test_reconciliation_preview_is_read_only_selected_and_safe_json() -> None:
    scenario = _scenario("validation/reconciliation-preview.yaml")
    selected = {
        item.scenario_id for item in select(SCENARIO_ROOT, categories=set(READ_ONLY_CATEGORIES))
    }

    assert scenario["id"] == "validation-reconciliation-preview"
    assert scenario["category"] in READ_ONLY_CATEGORIES
    assert {"read-only", "requires-target"} <= set(scenario["tags"])
    assert "mutating" not in scenario["tags"]
    assert scenario["id"] in selected
    json_step = next(step for step in scenario["steps"] if step["id"].endswith("json"))
    assert json_step["command"] == "--json"
    assert json_step["args"][:2] == ["operations", "reconcile-content"]
    assert json_step["expect"]["body_contains"]["mode"] == "dry_run"
    assert set(json_step["expect"]["body_contains"]) == {
        "mode",
        "scanned",
        "reported",
        "counts",
        "items",
    }


def test_reconciliation_apply_cases_are_mutation_guarded_and_target_specific() -> None:
    read_only_ids = {
        item.scenario_id for item in select(SCENARIO_ROOT, categories=set(READ_ONLY_CATEGORIES))
    }
    cases = {
        "operation-control/reconciliation-disabled-apply.yaml": (
            "operation-control-reconciliation-disabled-apply",
            "requires-apply-disabled",
        ),
        "operation-control/reconciliation-guarded-apply.yaml": (
            "operation-control-reconciliation-guarded-apply",
            "requires-apply-enabled",
        ),
        "operation-control/reconciliation-apply-failure.yaml": (
            "operation-control-reconciliation-apply-failure",
            "requires-seeded-reconciliation-apply-failure",
        ),
    }

    for path, (scenario_id, prerequisite) in cases.items():
        scenario = _scenario(path)
        assert scenario["id"] == scenario_id
        assert scenario["category"] in MUTATING_CATEGORIES
        assert {"mutating", "requires-target", prerequisite} <= set(scenario["tags"])
        assert scenario_id not in read_only_ids
        assert any("--apply" in step.get("args", []) for step in scenario["steps"])

    failure = _scenario("operation-control/reconciliation-apply-failure.yaml")
    step = next(step for step in failure["steps"] if step["id"].endswith("json"))
    assert step["expect"]["exit_code"] == 1
    assert step["expect"]["body_contains"]["items"] == [{"reason": "apply_failed"}]
