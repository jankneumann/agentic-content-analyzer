"""RI-07 gen-eval scenario contracts for ingestion history and pipeline outcomes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.cli_gen_eval.contract import MUTATING_CATEGORIES, READ_ONLY_CATEGORIES
from src.cli_gen_eval.selection import select

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_ROOT = REPO_ROOT / "evaluation" / "scenarios"


def _scenario(relative_path: str) -> dict[str, Any]:
    path = SCENARIO_ROOT / relative_path
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def test_filtered_ingestion_history_is_read_only_and_selected_on_prs() -> None:
    selected = {
        item.scenario_id for item in select(SCENARIO_ROOT, categories=set(READ_ONLY_CATEGORIES))
    }

    scenario = _scenario("validation/ingestion-history-filtered.yaml")
    assert scenario["id"] == "validation-ingestion-history-filtered"
    assert scenario["category"] in READ_ONLY_CATEGORIES
    assert "read-only" in scenario["tags"]
    assert "mutating" not in scenario["tags"]
    assert scenario["id"] in selected


def test_pipeline_outcome_scenarios_are_mutating_and_excluded_from_pr_selection() -> None:
    read_only_ids = {
        item.scenario_id for item in select(SCENARIO_ROOT, categories=set(READ_ONLY_CATEGORIES))
    }

    for relative_path in (
        "workflow-submission/pipeline-zero-items.yaml",
        "workflow-submission/pipeline-partial-warning.yaml",
    ):
        scenario = _scenario(relative_path)
        assert scenario["category"] in MUTATING_CATEGORIES
        assert {"mutating", "requires-target"} <= set(scenario["tags"])
        assert scenario["id"] not in read_only_ids

    scenario = _scenario("workflow-submission/pipeline-partial-warning.yaml")
    waited = next(step for step in scenario["steps"] if step["id"] == "pipeline-partial-json")
    assert "--wait" in waited["args"]
    assert waited["expect"]["exit_code"] == 0
    assert waited["expect"]["body_contains"]["result"]["ingestion_summary"]["outcome"] == (
        "partial"
    )
    assert "partial source results" in waited["expect"]["error_contains"]
