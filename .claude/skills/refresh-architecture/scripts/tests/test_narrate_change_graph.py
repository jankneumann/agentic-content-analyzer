"""Narration writes words onto a projected document and nothing else.

The rule that matters is mechanical rather than prompted: the merge accepts a
closed set of text fields, and anything the model returns outside that set is
ignored.  A hallucinated node therefore cannot survive, because there is no
path by which it could be written.  The structural comparison afterwards is the
belt to that braces -- it catches a text field whose content changed a count or
an order that the document itself derives.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from arch_utils import change_graph
from narrate_change_graph import (
    NARRATABLE,
    build_prompt,
    first_structural_difference,
    narrate,
)
from project_change_graph import Hunk, project

PROVENANCE = {
    "repo": {"owner": "acme", "name": "webapp"},
    "base": {"sha": "0000000"},
    "head": {"sha": "1111111"},
}


def _node(node_id: str, file: str) -> dict:
    return {
        "id": node_id,
        "kind": "function",
        "language": "python",
        "name": node_id.split(".")[-1],
        "file": file,
        "span": {"start": 1, "end": 20},
        "tags": [],
        "signatures": {},
    }


@pytest.fixture
def document() -> dict[str, Any]:
    base = {
        "nodes": [_node("py:services.user.create", "src/services/user.py")],
        "edges": [],
    }
    head = {
        "nodes": [*base["nodes"], _node("py:services.mail.send", "src/services/mail.py")],
        "edges": [
            {
                "from": "py:services.user.create",
                "to": "py:services.mail.send",
                "type": "call",
            }
        ],
    }
    return project(
        base_graph=base,
        head_graph=head,
        hunks={"src/services/user.py": [Hunk(start=1, end=3)]},
        flows={"flows": []},
        impact={"high_impact_nodes": []},
        provenance=PROVENANCE,
        stats={"filesChanged": 2, "additions": 30, "deletions": 1},
    )


def _stub(payload: dict[str, Any]):
    def complete(system: str, user: str) -> str:  # noqa: ARG001
        return json.dumps(payload)

    return complete


# ---------------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------------


def test_text_fields_are_merged(document: dict) -> None:
    node_id = document["nodes"][0]["id"]
    narrated = narrate(
        document,
        _stub(
            {
                "title": "Signup now sends a welcome email",
                "summary": "The signup path gained a mailer call.",
                "nodes": {node_id: "Creates the user row."},
            }
        ),
    )

    assert narrated["title"] == "Signup now sends a welcome email"
    assert narrated["summary"] == "The signup path gained a mailer call."
    assert narrated["nodes"][0]["summary"] == "Creates the user row."


def test_walkthrough_captions_are_merged_by_step_id(document: dict) -> None:
    step_id = document["walkthrough"]["steps"][0]["id"]
    narrated = narrate(
        document,
        _stub(
            {
                "walkthrough": {
                    step_id: {"heading": "Start here", "body": "What the change does."}
                }
            }
        ),
    )

    assert narrated["walkthrough"]["steps"][0]["heading"] == "Start here"
    assert narrated["walkthrough"]["steps"][0]["body"] == "What the change does."


def test_the_narrated_document_still_satisfies_the_contract(document: dict) -> None:
    narrated = narrate(document, _stub({"title": "A readable title"}))

    assert change_graph.validation_errors(narrated) == []


# ---------------------------------------------------------------------------
# Structure is not the model's to change
# ---------------------------------------------------------------------------


def test_keys_outside_the_narratable_set_are_ignored(document: dict) -> None:
    """A hallucinated node has no path by which it could be written."""
    narrated = narrate(
        document,
        _stub(
            {
                "title": "Fine",
                "nodes": {"py-invented-node": "I made this up"},
                "edges": [{"id": "ghost", "from": "a", "to": "b"}],
                "lanes": [{"id": "ghost-lane", "label": "Ghost"}],
            }
        ),
    )

    assert len(narrated["nodes"]) == len(document["nodes"])
    assert narrated["edges"] == document["edges"]
    assert narrated["lanes"] == document["lanes"]


def test_a_structural_difference_discards_the_narration(document: dict) -> None:
    def sabotage(system: str, user: str) -> str:  # noqa: ARG001
        return json.dumps({"title": "Fine"})

    tampered = json.loads(json.dumps(document))
    tampered["nodes"][0]["delta"] = "removed"

    difference = first_structural_difference(document, tampered)

    assert difference is not None
    assert "delta" in difference


def test_narration_that_fails_validation_leaves_the_projection_standing(
    document: dict,
) -> None:
    narrated = narrate(document, _stub({"title": ""}))

    assert narrated["title"] == document["title"]
    assert change_graph.validation_errors(narrated) == []


def test_a_provider_failure_leaves_the_projection_standing(document: dict) -> None:
    def explode(system: str, user: str) -> str:  # noqa: ARG001
        raise RuntimeError("no API key configured")

    narrated = narrate(document, explode)

    assert narrated == document


def test_a_non_json_answer_leaves_the_projection_standing(document: dict) -> None:
    narrated = narrate(document, lambda system, user: "I'm afraid I can't do that")

    assert narrated == document


def test_narration_never_writes_stat_chips(document: dict) -> None:
    """A chip is a number, and a model writing numbers is how a diagram lies."""
    narrated = narrate(
        document,
        _stub({"stats": {"chips": [{"label": "Calls", "value": "500x fewer"}]}}),
    )

    assert narrated["stats"] == document["stats"]
    assert "stats" not in NARRATABLE


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------


def test_over_long_text_is_truncated_rather_than_rejected(document: dict) -> None:
    narrated = narrate(document, _stub({"title": "word " * 200}))

    assert len(narrated["title"]) <= 120
    assert change_graph.validation_errors(narrated) == []


def test_the_prompt_carries_the_ids_the_model_must_write_against(
    document: dict,
) -> None:
    prompt = build_prompt(document)

    assert document["nodes"][0]["id"] in prompt
    assert document["walkthrough"]["steps"][0]["id"] in prompt
    # It must not invite structural edits.
    assert "delta" not in prompt.split("Return JSON")[-1]


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------


def test_the_model_is_read_from_settings_not_from_the_product_enum(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """Narration is tooling, so it must not add a member to ModelStep."""
    from narrate_change_graph import resolve_model

    (tmp_path / "settings").mkdir()
    (tmp_path / "settings" / "models.yaml").write_text(
        "default_models:\n  change_narration: some-cheap-model\n"
    )
    monkeypatch.delenv("MODEL_CHANGE_NARRATION", raising=False)

    assert resolve_model(tmp_path) == "some-cheap-model"


def test_the_environment_overrides_the_settings_default(
    tmp_path: Any, monkeypatch: Any
) -> None:
    from narrate_change_graph import resolve_model

    monkeypatch.setenv("MODEL_CHANGE_NARRATION", "from-the-environment")

    assert resolve_model(tmp_path) == "from-the-environment"


def test_this_repository_declares_the_narration_step() -> None:
    import yaml as _yaml
    from pathlib import Path as _Path

    from narrate_change_graph import PIPELINE_STEP

    root = _Path(__file__).resolve().parents[5]
    settings = _yaml.safe_load((root / "settings" / "models.yaml").read_text())

    assert PIPELINE_STEP in settings["default_models"]
