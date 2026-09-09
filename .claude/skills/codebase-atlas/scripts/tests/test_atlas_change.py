"""Delta and test-coverage inputs for the atlas.

Two things this module has to keep straight, because getting either wrong
produces a page that is confidently misleading:

Untested is not unmeasured.  A symbol with no covering test and a symbol the
coverage report never mentions are different facts, and painting both in the
zero colour turns "we do not know" into "we know it is bad".

The word coverage means two things here.  The atlas already reports how much of
the repository the graph saw; this is how much of the code the tests exercise.
They are different numbers, so they never share a name.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arch_utils import change_graph
from atlas_change import (
    LINKAGE_BUCKETS,
    delta_index,
    linkage_counts,
    load_line_coverage,
    module_coverage,
    symbol_coverage,
)

COVERAGE_XML = """<?xml version="1.0" ?>
<coverage>
  <packages><package><classes>
    <class filename="src/services/user.py">
      <lines>
        <line number="1" hits="1"/>
        <line number="2" hits="1"/>
        <line number="3" hits="0"/>
        <line number="40" hits="0"/>
      </lines>
    </class>
  </classes></package></packages>
</coverage>
"""


def _edge(source: str, target: str, kind: str) -> dict:
    return {"from": source, "to": target, "type": kind}


# ---------------------------------------------------------------------------
# Linkage coverage
# ---------------------------------------------------------------------------


def test_linkage_counts_distinct_covering_tests() -> None:
    edges = [
        _edge("t1", "py:a", "TEST_COVERS"),
        _edge("t2", "py:a", "TEST_COVERS"),
        _edge("t1", "py:a", "TEST_COVERS"),
        _edge("py:b", "py:a", "call"),
    ]

    counts = linkage_counts(edges)

    assert counts["py:a"] == 2, "a repeated edge is one test, not two"
    assert "py:b" not in counts


def test_linkage_buckets_are_ordinal_not_a_percentage() -> None:
    """Linkage says how many tests reach a symbol, never what fraction ran."""
    assert LINKAGE_BUCKETS(0) == "unlinked"
    assert LINKAGE_BUCKETS(1) == "1"
    assert LINKAGE_BUCKETS(3) == "2-4"
    assert LINKAGE_BUCKETS(9) == "5+"


# ---------------------------------------------------------------------------
# Line coverage
# ---------------------------------------------------------------------------


def test_line_report_is_read_per_file(tmp_path: Path) -> None:
    report_path = tmp_path / "coverage.xml"
    report_path.write_text(COVERAGE_XML)

    report = load_line_coverage(report_path)

    assert report is not None
    assert report.lines["src/services/user.py"] == {1: 1, 2: 1, 3: 0, 40: 0}


def test_a_stale_report_is_refused_rather_than_trusted(tmp_path: Path) -> None:
    """A confident colour from an old report is worse than no colour."""
    report_path = tmp_path / "coverage.xml"
    report_path.write_text(COVERAGE_XML)
    source = tmp_path / "later.py"
    source.write_text("x = 1\n")
    newer = report_path.stat().st_mtime + 60

    assert load_line_coverage(report_path, newest_source_mtime=newer) is None
    assert load_line_coverage(report_path, newest_source_mtime=0) is not None


def test_a_missing_report_is_simply_absent(tmp_path: Path) -> None:
    assert load_line_coverage(tmp_path / "nope.xml") is None


def test_symbol_coverage_uses_only_the_lines_in_its_span(tmp_path: Path) -> None:
    report_path = tmp_path / "coverage.xml"
    report_path.write_text(COVERAGE_XML)
    report = load_line_coverage(report_path)

    covered = symbol_coverage(report, "src/services/user.py", 1, 3)

    assert covered == (2, 3)


def test_a_symbol_the_report_never_mentions_is_unknown_not_zero(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "coverage.xml"
    report_path.write_text(COVERAGE_XML)
    report = load_line_coverage(report_path)

    assert symbol_coverage(report, "src/never/seen.py", 1, 10) is None


def test_module_coverage_is_weighted_by_statements_not_by_symbol_count() -> None:
    """Twenty covered one-liners do not outvote one uncovered hundred-liner."""
    symbols = [(1, 1)] * 20 + [(0, 100)]

    assert module_coverage(symbols) == pytest.approx(20 / 120)


def test_module_coverage_of_nothing_measured_is_unknown() -> None:
    assert module_coverage([]) is None


# ---------------------------------------------------------------------------
# Delta
# ---------------------------------------------------------------------------


@pytest.fixture
def document() -> dict:
    fixture = (
        Path(__file__).resolve().parents[3]
        / "refresh-architecture"
        / "scripts"
        / "tests"
        / "fixtures"
        / "change"
        / "recent-fixes.graph.json"
    )
    return json.loads(fixture.read_text())


def test_delta_index_matches_documents_back_onto_graph_ids() -> None:
    """A document addresses nodes by rewritten id, so matching is forward-only.

    One id here is past the contract's 128-character limit and is rewritten
    with a digest, so a reader that assumed identity would lose it.
    """
    from project_change_graph import Hunk, project

    def node(node_id: str, file: str) -> dict:
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

    deep = "py:services." + ".".join(["deeply_nested_package"] * 8) + ".handler"
    assert len(deep) > 128
    graph_ids = {deep, "py:services.user.create"}
    base = {"nodes": [node(i, "src/services/user.py") for i in sorted(graph_ids)], "edges": []}
    head = {
        "nodes": base["nodes"],
        "edges": [{"from": deep, "to": "py:services.user.create", "type": "call"}],
    }
    projected = project(
        base_graph=base,
        head_graph=head,
        hunks={"src/services/user.py": [Hunk(start=1, end=5)]},
        flows={"flows": []},
        impact={"high_impact_nodes": []},
        provenance={
            "repo": {"owner": "a", "name": "b"},
            "base": {"sha": "0000000"},
            "head": {"sha": "1111111"},
        },
        stats={"filesChanged": 1, "additions": 1, "deletions": 0},
    )

    # The rewrite is not the identity here, so a forward-only match is the
    # only thing that can work.
    assert {node["id"] for node in projected["nodes"]} != graph_ids

    deltas, unmatched = delta_index(projected, graph_ids)

    assert set(deltas) == graph_ids
    assert unmatched == []


def test_ids_the_atlas_graph_lacks_are_reported_not_dropped(document: dict) -> None:
    deltas, unmatched = delta_index(document, {"py:not.in.this.graph"})

    assert deltas == {}
    assert len(unmatched) == len(document["nodes"])


def test_an_invalid_document_is_refused(document: dict) -> None:
    document["nodes"][0]["delta"] = "vaporised"

    with pytest.raises(change_graph.DocumentInvalidError):
        delta_index(document, set(), validate=True)


# ---------------------------------------------------------------------------
# View-model wiring
# ---------------------------------------------------------------------------


def _graph(tmp_path: Path) -> dict:
    def node(node_id: str, file: str, start: int, end: int, kind: str = "function") -> dict:
        return {
            "id": node_id,
            "kind": kind,
            "language": "python",
            "name": node_id.split(".")[-1],
            "file": file,
            "span": {"start": start, "end": end},
            "tags": [],
            "signatures": {},
        }

    return {
        "nodes": [
            node("py:services.user.create", "services/user.py", 1, 3),
            node("py:services.user.audit", "services/user.py", 40, 40),
            node("py:tests.test_user.test_create", "tests/test_user.py", 1, 5, "test_function"),
        ],
        "edges": [
            {
                "from": "py:tests.test_user.test_create",
                "to": "py:services.user.create",
                "type": "TEST_COVERS",
            }
        ],
        "snapshots": [{"git_sha": "0" * 40}],
    }


def test_view_model_carries_linkage_counts_without_any_report(tmp_path: Path) -> None:
    from atlas_model import build_view_model

    model = build_view_model(_graph(tmp_path), tmp_path, measure=False)
    symbols = {symbol["id"]: symbol for symbol in model["symbols"]}

    assert symbols["py:services.user.create"]["tests"] == 1
    assert symbols["py:services.user.audit"]["tests"] == 0
    assert model["meta"]["testCoverage"]["source"] == "linkage"


def test_view_model_carries_line_coverage_when_a_fresh_report_exists(
    tmp_path: Path,
) -> None:
    from atlas_model import build_view_model

    report = tmp_path / "coverage.xml"
    report.write_text(COVERAGE_XML)

    model = build_view_model(
        _graph(tmp_path),
        tmp_path,
        measure=False,
        line_coverage=load_line_coverage(report),
        source_prefixes={"python": "src"},
    )
    symbols = {symbol["id"]: symbol for symbol in model["symbols"]}

    assert symbols["py:services.user.create"]["cov"] == pytest.approx(2 / 3)
    # Line 40 is in the report and never hit.
    assert symbols["py:services.user.audit"]["cov"] == 0.0
    assert model["meta"]["testCoverage"]["source"] == "line"


def test_a_symbol_outside_the_report_is_null_rather_than_zero(tmp_path: Path) -> None:
    from atlas_model import build_view_model

    report = tmp_path / "coverage.xml"
    report.write_text(COVERAGE_XML)
    graph = _graph(tmp_path)
    graph["nodes"].append(
        {
            "id": "py:elsewhere.thing",
            "kind": "function",
            "language": "python",
            "name": "thing",
            "file": "elsewhere.py",
            "span": {"start": 1, "end": 2},
            "tags": [],
            "signatures": {},
        }
    )

    model = build_view_model(
        graph,
        tmp_path,
        measure=False,
        line_coverage=load_line_coverage(report),
        source_prefixes={"python": "src"},
    )
    symbols = {symbol["id"]: symbol for symbol in model["symbols"]}

    assert symbols["py:elsewhere.thing"]["cov"] is None


def test_the_view_model_stamps_deltas_and_reports_unmatched_ids(
    tmp_path: Path,
) -> None:
    from atlas_model import build_view_model
    from project_change_graph import Hunk, project

    graph = _graph(tmp_path)
    base = {"nodes": graph["nodes"][:1], "edges": []}
    document = project(
        base_graph=base,
        head_graph={"nodes": graph["nodes"][:2], "edges": []},
        hunks={"services/user.py": [Hunk(start=1, end=2)]},
        flows={"flows": []},
        impact={"high_impact_nodes": []},
        provenance={
            "repo": {"owner": "a", "name": "b"},
            "base": {"sha": "0000000"},
            "head": {"sha": "1111111"},
        },
        stats={"filesChanged": 1, "additions": 1, "deletions": 0},
    )

    model = build_view_model(graph, tmp_path, measure=False, change=document)
    symbols = {symbol["id"]: symbol for symbol in model["symbols"]}

    assert symbols["py:services.user.audit"]["delta"] == "added"
    assert symbols["py:services.user.create"]["delta"] == "modified"
    assert "delta" not in symbols["py:tests.test_user.test_create"]
    assert model["meta"]["change"]["unmatched"] == []


def test_the_view_model_is_byte_stable_with_the_new_fields(tmp_path: Path) -> None:
    from atlas_model import build_view_model

    graph = _graph(tmp_path)
    first = json.dumps(build_view_model(graph, tmp_path, measure=False), sort_keys=True)
    second = json.dumps(build_view_model(graph, tmp_path, measure=False), sort_keys=True)

    assert first == second


def test_a_module_is_added_only_when_every_symbol_in_it_is(tmp_path: Path) -> None:
    from atlas_model import module_delta

    assert module_delta(["added", "added"]) == "added"
    assert module_delta(["added", "unchanged"]) == "modified"
    assert module_delta(["removed", "removed"]) == "removed"
    assert module_delta(["unchanged", "unchanged"]) == "unchanged"
    assert module_delta([]) is None


# ---------------------------------------------------------------------------
# Walkthrough
# ---------------------------------------------------------------------------


def test_walkthrough_steps_are_translated_into_graph_ids(document: dict) -> None:
    from atlas_change import walkthrough_steps

    graph_ids = _document_graph_ids(document)
    steps = walkthrough_steps(document, graph_ids)

    assert len(steps) >= 2
    assert all(step["heading"] and step["body"] for step in steps)
    assert all(node in graph_ids for step in steps for node in step["nodes"])


def test_a_step_whose_focus_survives_nothing_is_dropped(document: dict) -> None:
    from atlas_change import walkthrough_steps

    # The atlas graph shares no node with the document.
    assert walkthrough_steps(document, {"py:unrelated"}) == []


def test_a_walkthrough_cut_below_two_steps_goes_whole(document: dict) -> None:
    """One step is a caption, not a tour."""
    from atlas_change import walkthrough_steps

    document["walkthrough"]["steps"] = document["walkthrough"]["steps"][:1]

    assert walkthrough_steps(document, _document_graph_ids(document)) == []


def test_a_document_without_a_walkthrough_offers_none(document: dict) -> None:
    from atlas_change import walkthrough_steps

    document.pop("walkthrough", None)

    assert walkthrough_steps(document, _document_graph_ids(document)) == []


def _document_graph_ids(document: dict) -> set[str]:
    """The fixture was projected from ids that needed no rewriting."""
    return {node["id"] for node in document["nodes"]}
