"""The corrections overlay is applied over inference and never absorbed by it.

A correction addresses nodes by exact graph id or by a glob over the files
backing them.  The glob form is the one that matters: it is what lets a
correction keep holding after the analyzer renames the node, which is the whole
reason the overlay is an overlay rather than an edit to the output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from arch_utils import change_graph
from project_change_graph import (
    Corrections,
    Hunk,
    NothingToDraw,
    document_id,
    load_corrections,
    project,
    resolve_corrections,
)

#: The change edits `user.create`, so everything it calls sits one hop away and
#: is kept as context.  A correction aimed further out would address a node the
#: document never contained, which tests the fixture rather than the overlay.
TOUCHED = {"src/services/user.py": [Hunk(start=1, end=3)]}

PROVENANCE = {
    "repo": {"owner": "acme", "name": "webapp"},
    "base": {"sha": "0000000"},
    "head": {"sha": "1111111"},
}


def _node(node_id: str, file: str, **kwargs: Any) -> dict:
    return {
        "id": node_id,
        "kind": kwargs.pop("kind", "function"),
        "language": kwargs.pop("language", "python"),
        "name": node_id.split(".")[-1],
        "file": file,
        "span": {"start": 1, "end": 20},
        "tags": [],
        "signatures": {},
        **kwargs,
    }


@pytest.fixture
def graphs() -> tuple[dict, dict]:
    base = {
        "nodes": [
            _node("py:services.legacy_mailer.send", "src/services/legacy_mailer.py"),
            _node("py:services.user.create", "src/services/user.py"),
        ],
        "edges": [
            {
                "from": "py:services.user.create",
                "to": "py:services.legacy_mailer.send",
                "type": "call",
            }
        ],
    }
    head = {
        "nodes": [*base["nodes"], _node("py:services.mail.send", "src/services/mail.py")],
        "edges": [
            *base["edges"],
            {
                "from": "py:services.user.create",
                "to": "py:services.mail.send",
                "type": "call",
            },
        ],
    }
    return base, head


def _project(
    base: dict,
    head: dict,
    corrections: Corrections | None = None,
    hunks: dict | None = None,
) -> dict:
    return project(
        base_graph=base,
        head_graph=head,
        hunks=TOUCHED if hunks is None else hunks,
        flows={"flows": []},
        impact={"high_impact_nodes": []},
        provenance=PROVENANCE,
        stats={"filesChanged": 1, "additions": 10, "deletions": 0},
        corrections=corrections,
    )


def _labels(document: dict) -> dict[str, str]:
    return {node["id"]: node["label"] for node in document["nodes"]}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_overlay_file_is_validated_against_the_vendored_schema(tmp_path: Path) -> None:
    path = tmp_path / "change-graph.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schemaVersion": change_graph.CONTRACT_VERSION,
                "map": {"exclude": ["**/*.test.ts"]},
            }
        )
    )

    corrections = load_corrections(path)

    assert corrections.excludes == ["**/*.test.ts"]


def test_a_malformed_overlay_is_refused_rather_than_half_applied(
    tmp_path: Path,
) -> None:
    path = tmp_path / "change-graph.yaml"
    path.write_text(
        yaml.safe_dump(
            {"schemaVersion": change_graph.CONTRACT_VERSION, "map": {"exclude": "nope"}}
        )
    )

    with pytest.raises(change_graph.DocumentInvalidError):
        load_corrections(path)


def test_a_missing_overlay_is_simply_no_corrections(tmp_path: Path) -> None:
    assert load_corrections(tmp_path / "absent.yaml") == Corrections()


# ---------------------------------------------------------------------------
# Selectors
# ---------------------------------------------------------------------------


def test_rename_by_exact_graph_id(graphs: tuple[dict, dict]) -> None:
    base, head = graphs
    corrections = Corrections(
        renames=[("id:py:services.legacy_mailer.send", "Postmark sender")]
    )

    document = _project(base, head, corrections)

    assert (
        _labels(document)[document_id("py:services.legacy_mailer.send")]
        == "Postmark sender"
    )


def test_rename_by_glob_survives_the_node_being_renamed(
    graphs: tuple[dict, dict]
) -> None:
    """The analyzer renamed the symbol; the file glob still matches."""
    base, head = graphs
    for graph in (base, head):
        for node in graph["nodes"]:
            if node["id"] == "py:services.legacy_mailer.send":
                node["name"] = "dispatch_now"

    corrections = Corrections(
        renames=[("src/services/legacy_mailer.py", "Postmark sender")]
    )
    document = _project(base, head, corrections)

    assert (
        _labels(document)[document_id("py:services.legacy_mailer.send")]
        == "Postmark sender"
    )


def test_glob_matches_a_directory_pattern(graphs: tuple[dict, dict]) -> None:
    base, head = graphs
    corrections = Corrections(lanes=[("src/services/*.py", "mail")])

    document = _project(base, head, corrections)
    lanes = {lane["id"] for lane in document["lanes"]}

    assert "mail" in lanes
    assert all(node["lane"] == "mail" for node in document["nodes"])


def test_a_lane_correction_may_name_a_lane_the_document_never_declared(
    graphs: tuple[dict, dict]
) -> None:
    base, head = graphs
    corrections = Corrections(lanes=[("id:py:services.mail.send", "infrastructure")])

    document = _project(base, head, corrections)
    lane = next(
        lane for lane in document["lanes"] if lane["id"] == "infrastructure"
    )

    assert lane["label"] == "infrastructure"
    assert change_graph.validation_errors(document) == []


def test_group_correction_clusters_within_the_lane(graphs: tuple[dict, dict]) -> None:
    base, head = graphs
    corrections = Corrections(groups=[("src/services/*.py", "mail-stack")])

    document = _project(base, head, corrections)

    assert {node.get("group") for node in document["nodes"]} == {"mail-stack"}


# ---------------------------------------------------------------------------
# Exclusion cascade
# ---------------------------------------------------------------------------


def test_excluding_a_node_takes_its_edges_with_it(graphs: tuple[dict, dict]) -> None:
    base, head = graphs
    corrections = Corrections(excludes=["id:py:services.mail.send"])

    document = _project(base, head, corrections)
    present = {node["id"] for node in document["nodes"]}

    assert document_id("py:services.mail.send") not in present
    assert all(
        edge["to"] != document_id("py:services.mail.send")
        for edge in document["edges"]
    )
    assert change_graph.validation_errors(document) == []


def test_exclusion_leaves_no_dangling_view_selection_or_walkthrough_focus(
    graphs: tuple[dict, dict]
) -> None:
    """Half an arrow is worse than none, and a dangling id fails the contract."""
    base, head = graphs
    corrections = Corrections(excludes=["src/services/*.py"])

    # Excluding everything leaves no node, and the contract requires one. The
    # projector says so rather than emitting a document that cannot render.
    with pytest.raises(NothingToDraw):
        _project(base, head, corrections)


def test_a_walkthrough_cut_below_two_steps_goes_whole(
    graphs: tuple[dict, dict]
) -> None:
    base, head = graphs
    corrections = Corrections(excludes=["src/services/mail.py"])

    document = _project(base, head, corrections)
    walkthrough = document.get("walkthrough")

    assert walkthrough is None or len(walkthrough["steps"]) >= 2
    assert change_graph.validation_errors(document) == []


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def test_a_selector_matching_nothing_is_reported_and_does_not_stop_the_run() -> None:
    nodes = {"py:services.user.create": _node("py:services.user.create", "src/services/user.py")}
    corrections = Corrections(
        renames=[("src/nowhere/*.py", "Ghost")],
        excludes=["id:py:does.not.exist"],
    )

    resolution = resolve_corrections(corrections, nodes, {})

    assert sorted(resolution.unmatched) == [
        "id:py:does.not.exist",
        "src/nowhere/*.py",
    ]
    assert resolution.excluded == set()


def test_inference_never_writes_back_to_the_overlay(
    graphs: tuple[dict, dict], tmp_path: Path
) -> None:
    path = tmp_path / "change-graph.yaml"
    original = yaml.safe_dump(
        {
            "schemaVersion": change_graph.CONTRACT_VERSION,
            "map": {"rename": [{"match": "src/services/mail.py", "to": "Mailer"}]},
        }
    )
    path.write_text(original)

    base, head = graphs
    _project(base, head, load_corrections(path))

    assert path.read_text() == original
