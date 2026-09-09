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
