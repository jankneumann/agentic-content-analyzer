"""Projection of a code change onto the architecture graph.

Every delta here is derived from artifacts the analyzer already produced, so
these tests feed the projector synthetic graphs and diff hunks rather than
running git: the rules under test are about set membership and line ranges,
and a fixture that needs a repository to exist tests the fixture.
"""

from __future__ import annotations

from typing import Any

import pytest

from arch_utils import change_graph
from project_change_graph import (
    Hunk,
    document_id,
    parse_unified_diff,
    project,
)

PROVENANCE = {
    "repo": {"owner": "acme", "name": "webapp", "host": "github.com"},
    "base": {"sha": "0000000"},
    "head": {"sha": "1111111"},
}


def _node(node_id: str, file: str, start: int, end: int, **kwargs: Any) -> dict:
    node = {
        "id": node_id,
        "kind": kwargs.pop("kind", "function"),
        "language": kwargs.pop("language", "python"),
        "name": node_id.split(".")[-1],
        "file": file,
        "span": {"start": start, "end": end},
        "tags": [],
        "signatures": {},
    }
    node.update(kwargs)
    return node


def _edge(source: str, target: str, kind: str = "call") -> dict:
    return {"from": source, "to": target, "type": kind, "confidence": "high"}


@pytest.fixture
def base_graph() -> dict:
    """A small backend graph: route -> service -> repository, plus a stranger."""
    return {
        "nodes": [
            _node("py:api.routes.signup", "src/api/routes.py", 10, 20),
            _node("py:services.user.create", "src/services/user.py", 5, 40),
            _node("py:db.users.insert", "src/db/users.py", 1, 15),
            _node("py:unrelated.helper", "src/util/helper.py", 1, 9),
        ],
        "edges": [
            _edge("py:api.routes.signup", "py:services.user.create"),
            _edge("py:services.user.create", "py:db.users.insert"),
        ],
        "snapshots": [{"git_sha": "0" * 40}],
    }


@pytest.fixture
def head_graph(base_graph: dict) -> dict:
    """The change adds a mailer the service now calls, and drops the stranger."""
    graph = {
        "nodes": [
            node for node in base_graph["nodes"] if node["id"] != "py:unrelated.helper"
        ],
        "edges": list(base_graph["edges"]),
        "snapshots": [{"git_sha": "1" * 40}],
    }
    graph["nodes"].append(_node("py:services.mail.send", "src/services/mail.py", 1, 30))
    graph["edges"].append(_edge("py:services.user.create", "py:services.mail.send"))
    return graph


def _project(base: dict, head: dict, hunks: dict, **kwargs: Any) -> dict:
    return project(
        base_graph=base,
        head_graph=head,
        hunks=hunks,
        flows=kwargs.pop("flows", {"flows": []}),
        impact=kwargs.pop("impact", {"high_impact_nodes": []}),
        provenance=kwargs.pop("provenance", PROVENANCE),
        stats=kwargs.pop("stats", {"filesChanged": 2, "additions": 30, "deletions": 4}),
        **kwargs,
    )


def _by_id(document: dict, collection: str) -> dict[str, dict]:
    return {item["id"]: item for item in document[collection]}


def _delta_of(document: dict, graph_id: str) -> str | None:
    node = _by_id(document, "nodes").get(document_id(graph_id))
    return node["delta"] if node else None


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------


def test_document_ids_are_legal_under_the_contract() -> None:
    """Graph ids carry underscores, which the contract's id pattern forbids."""
    import re

    pattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
    for graph_id in (
        "py:agents.approval.gates.ApprovalGate.__init__",
        "ts:web/src/components/Foo.tsx:useThing",
        "py:a" + "b" * 400,
    ):
        rendered = document_id(graph_id)
        assert pattern.match(rendered), rendered
        assert len(rendered) <= 128


def test_document_ids_are_stable_and_injective() -> None:
    assert document_id("py:a_b") == document_id("py:a_b")
    # Sanitisation alone would collapse these two onto the same id.
    assert document_id("py:a_b") != document_id("py:a-b")


# ---------------------------------------------------------------------------
# Deltas
# ---------------------------------------------------------------------------


def test_added_removed_and_unchanged_are_derived_from_the_two_graphs(
    base_graph: dict, head_graph: dict
) -> None:
    document = _project(base_graph, head_graph, hunks={})

    assert _delta_of(document, "py:services.mail.send") == "added"
    assert _delta_of(document, "py:unrelated.helper") == "removed"
    assert _delta_of(document, "py:services.user.create") == "unchanged"


def test_modified_requires_a_hunk_intersecting_the_symbol_span(
    base_graph: dict, head_graph: dict
) -> None:
    hunks = {"src/services/user.py": [Hunk(start=10, end=12)]}

    document = _project(base_graph, head_graph, hunks=hunks)

    assert _delta_of(document, "py:services.user.create") == "modified"


def test_a_hunk_outside_the_symbol_span_leaves_it_unchanged(
    base_graph: dict, head_graph: dict
) -> None:
    """The file changed, but not this symbol: a file-level delta would lie."""
    hunks = {"src/services/user.py": [Hunk(start=100, end=104)]}

    document = _project(base_graph, head_graph, hunks=hunks)

    assert _delta_of(document, "py:services.user.create") == "unchanged"


def test_edges_are_modified_when_an_endpoint_is(
    base_graph: dict, head_graph: dict
) -> None:
    hunks = {"src/services/user.py": [Hunk(start=10, end=12)]}

    document = _project(base_graph, head_graph, hunks=hunks)
    edges = _by_id(document, "edges")
    signup_to_service = edges[
        document_id("py:api.routes.signup->py:services.user.create")
    ]

    assert signup_to_service["delta"] == "modified"


# ---------------------------------------------------------------------------
# Neighbourhood
# ---------------------------------------------------------------------------


def test_unchanged_neighbours_are_kept_so_the_picture_shows_blast_radius(
    base_graph: dict, head_graph: dict
) -> None:
    document = _project(base_graph, head_graph, hunks={})

    deltas = {node["delta"] for node in document["nodes"]}
    assert "unchanged" in deltas


def test_nodes_more_than_one_hop_away_are_dropped() -> None:
    base = {
        "nodes": [
            _node("py:a.one", "src/a.py", 1, 5),
            _node("py:b.two", "src/b.py", 1, 5),
            _node("py:c.three", "src/c.py", 1, 5),
            _node("py:d.four", "src/d.py", 1, 5),
        ],
        "edges": [
            _edge("py:a.one", "py:b.two"),
            _edge("py:b.two", "py:c.three"),
            _edge("py:c.three", "py:d.four"),
        ],
        "snapshots": [{"git_sha": "0" * 40}],
    }
    head = {
        "nodes": list(base["nodes"]),
        "edges": list(base["edges"]),
        "snapshots": [{"git_sha": "1" * 40}],
    }
    head["nodes"].append(_node("py:new.symbol", "src/new.py", 1, 5))
    head["edges"].append(_edge("py:new.symbol", "py:a.one"))

    document = _project(base, head, hunks={})
    present = set(_by_id(document, "nodes"))

    assert document_id("py:a.one") in present, "one hop from the change is context"
    assert document_id("py:b.two") not in present, "two hops is not"


def test_test_covers_edges_never_pull_tests_into_the_neighbourhood() -> None:
    """TEST_COVERS is 96% of this repository's edges.

    Expanding across it would make every change a picture of the test suite,
    so coverage travels as a badge on the covered node instead.
    """
    base = {
        "nodes": [
            _node("py:services.user.create", "src/services/user.py", 1, 20),
            _node(
                "py:tests.test_user.test_create",
                "tests/test_user.py",
                1,
                9,
                kind="test_function",
            ),
        ],
        "edges": [
            _edge(
                "py:tests.test_user.test_create",
                "py:services.user.create",
                kind="TEST_COVERS",
            )
        ],
        "snapshots": [{"git_sha": "0" * 40}],
    }
    head = {
        "nodes": list(base["nodes"]),
        "edges": list(base["edges"]),
        "snapshots": [{"git_sha": "1" * 40}],
    }

    # The covered node is the one that changed, so its covering test sits
    # exactly one hop away.  Only the edge-type rule can exclude it; a test
    # that changed a node further out would pass on the hop limit alone.
    document = _project(
        base, head, hunks={"src/services/user.py": [Hunk(start=3, end=4)]}
    )
    nodes = _by_id(document, "nodes")

    assert nodes[document_id("py:services.user.create")]["delta"] == "modified"
    assert document_id("py:tests.test_user.test_create") not in nodes
    assert any("test" in badge for badge in nodes[document_id("py:services.user.create")]["badges"])


def test_a_changed_test_appears_in_its_own_lane() -> None:
    base = {
        "nodes": [_node("py:services.user.create", "src/services/user.py", 1, 20)],
        "edges": [],
        "snapshots": [{"git_sha": "0" * 40}],
    }
    head = {
        "nodes": [
            *base["nodes"],
            _node(
                "py:tests.test_user.test_new",
                "tests/test_user.py",
                1,
                9,
                kind="test_function",
            ),
        ],
        "edges": [],
        "snapshots": [{"git_sha": "1" * 40}],
    }

    document = _project(base, head, hunks={})
    node = _by_id(document, "nodes")[document_id("py:tests.test_user.test_new")]
    lane = _by_id(document, "lanes")[node["lane"]]

    assert node["delta"] == "added"
    assert lane["label"].lower().startswith("test")


# ---------------------------------------------------------------------------
# Emphasis
# ---------------------------------------------------------------------------


def test_hero_edge_is_the_added_edge_into_the_highest_impact_node(
    base_graph: dict, head_graph: dict
) -> None:
    head_graph["nodes"].append(_node("py:core.audit.record", "src/core/audit.py", 1, 8))
    head_graph["edges"].append(
        _edge("py:services.user.create", "py:core.audit.record")
    )
    impact = {
        "high_impact_nodes": [
            {"id": "py:core.audit.record", "dependent_count": 500},
            {"id": "py:services.mail.send", "dependent_count": 12},
        ]
    }

    document = _project(base_graph, head_graph, hunks={}, impact=impact)
    heroes = [
        edge for edge in document["edges"] if edge.get("emphasis") == "hero"
    ]

    assert len(heroes) == 1
    assert heroes[0]["to"] == document_id("py:core.audit.record")


def test_hero_tie_is_broken_by_edge_id_so_two_runs_agree(
    base_graph: dict, head_graph: dict
) -> None:
    head_graph["nodes"].append(_node("py:core.audit.record", "src/core/audit.py", 1, 8))
    head_graph["edges"].append(_edge("py:services.user.create", "py:core.audit.record"))
    impact = {
        "high_impact_nodes": [
            {"id": "py:core.audit.record", "dependent_count": 7},
            {"id": "py:services.mail.send", "dependent_count": 7},
        ]
    }

    first = _project(base_graph, head_graph, hunks={}, impact=impact)
    second = _project(base_graph, head_graph, hunks={}, impact=impact)
    hero_of = lambda doc: [  # noqa: E731
        edge["id"] for edge in doc["edges"] if edge.get("emphasis") == "hero"
    ]

    assert hero_of(first) == hero_of(second)
    assert len(hero_of(first)) == 1


# ---------------------------------------------------------------------------
# Contract and determinism
# ---------------------------------------------------------------------------


def test_projected_document_satisfies_the_contract(
    base_graph: dict, head_graph: dict
) -> None:
    document = _project(base_graph, head_graph, hunks={})

    assert change_graph.validation_errors(document) == []


def test_projection_is_byte_identical_across_runs(
    base_graph: dict, head_graph: dict
) -> None:
    first = change_graph.serialize(_project(base_graph, head_graph, hunks={}))
    second = change_graph.serialize(_project(base_graph, head_graph, hunks={}))

    assert first == second


def test_repository_facts_overwrite_anything_a_producer_supplied(
    base_graph: dict, head_graph: dict
) -> None:
    document = _project(
        base_graph,
        head_graph,
        hunks={},
        stats={"filesChanged": 7, "additions": 70, "deletions": 3},
    )

    assert document["stats"]["filesChanged"] == 7
    assert document["provenance"]["head"]["sha"] == "1111111"


# ---------------------------------------------------------------------------
# Diff parsing
# ---------------------------------------------------------------------------


def test_parse_unified_diff_reads_post_image_ranges() -> None:
    diff = (
        "diff --git a/src/services/user.py b/src/services/user.py\n"
        "--- a/src/services/user.py\n"
        "+++ b/src/services/user.py\n"
        "@@ -10,0 +11,3 @@\n"
        "+one\n+two\n+three\n"
        "@@ -40,2 +44,0 @@\n"
        "-gone\n-also\n"
    )

    hunks = parse_unified_diff(diff)

    assert hunks["src/services/user.py"] == [Hunk(start=11, end=13), Hunk(start=44, end=44)]


def test_parse_unified_diff_handles_renames_and_deletions() -> None:
    diff = (
        "diff --git a/old.py b/new.py\n"
        "similarity index 90%\n"
        "rename from old.py\n"
        "rename to new.py\n"
        "--- a/old.py\n"
        "+++ b/new.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-a\n+b\n"
        "diff --git a/dead.py b/dead.py\n"
        "deleted file mode 100644\n"
        "--- a/dead.py\n"
        "+++ /dev/null\n"
        "@@ -1,3 +0,0 @@\n"
        "-x\n-y\n-z\n"
    )

    hunks = parse_unified_diff(diff)

    assert "new.py" in hunks
    assert "/dev/null" not in hunks


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def test_coverage_counts_changed_files_the_graph_never_saw() -> None:
    from project_change_graph import _coverage_of

    head = {
        "nodes": [
            _node("py:services.user.create", "services/user.py", 1, 20),
        ]
    }
    hunks = {
        "src/services/user.py": [Hunk(start=1, end=2)],
        "docs/README.md": [Hunk(start=1, end=1)],
    }

    coverage = _coverage_of(hunks, head, {"python": "src"})

    assert coverage["changed_files"] == 2
    assert coverage["uncovered_files"] == 1
    assert coverage["uncovered"] == ["docs/README.md"]


def test_uncovered_count_becomes_a_stat_chip(
    base_graph: dict, head_graph: dict
) -> None:
    document = _project(
        base_graph,
        head_graph,
        hunks={},
        coverage={"changed_files": 9, "uncovered_files": 4},
    )

    chips = {chip["label"]: chip["value"] for chip in document["stats"]["chips"]}
    assert chips["Files outside the graph"] == "4 of 9"


def test_an_ordinary_change_still_gets_a_walkthrough(
    base_graph: dict, head_graph: dict
) -> None:
    """No new edges and no removals must not cost the tour.

    The contract's floor is two steps, so a skeleton that only emitted an
    overview plus optional extras left most changes with no walkthrough at all.
    """
    hunks = {"src/services/user.py": [Hunk(start=10, end=12)]}

    document = _project(base_graph, head_graph, hunks=hunks)
    steps = document["walkthrough"]["steps"]

    assert len(steps) >= 2
    assert steps[0]["id"] == "what-changed"
    assert change_graph.validation_errors(document) == []


@pytest.mark.parametrize(
    "fixture", ["repo-wide.graph.json", "recent-fixes.graph.json"]
)
def test_documents_projected_from_this_repository_validate(fixture: str) -> None:
    """Real projections, kept as fixtures so a regression shows up here.

    Synthetic graphs cannot reproduce what the analyzer actually emits: spans
    on classes, source-root-relative paths, and the coverage ratio that made
    TEST_COVERS worth excluding in the first place.
    """
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent / "fixtures" / "change" / fixture
    document = json.loads(path.read_text())

    assert change_graph.validation_errors(document) == []
    assert document["nodes"], "a projected fixture with no nodes proves nothing"
