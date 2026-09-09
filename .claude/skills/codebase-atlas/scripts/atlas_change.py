"""Delta and test-coverage inputs for the atlas page.

The atlas colours nodes by language by default.  This module supplies the two
other things it can colour by: what a change touched, and how well the tests
reach the code.

Test nodes are deliberately not drawn.  In this repository test functions are
the majority of the graph's nodes and ``TEST_COVERS`` the overwhelming majority
of its edges, so drawing them turns a picture of the application into a picture
of its test suite.  Coverage becomes a property of the covered node instead,
which answers the question a reader actually has -- is this tested -- without
doubling the graph.

Two distinctions this module exists to keep:

**Untested is not unmeasured.**  A symbol with no covering test and a symbol the
coverage report never mentions are different facts.  Painting both in the zero
colour turns "we do not know" into "we know it is bad", so the second returns
``None`` everywhere and the page renders it in its own neutral.

**Coverage means two things.**  The atlas already reports how much of the
repository the *graph* saw.  This is how much of the code the *tests* exercise.
They never share a name; everything here says ``test`` or ``line``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree  # noqa: S405 - reading our own report
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

COVERAGE_EDGE_TYPE = "TEST_COVERS"

#: Ordinal buckets for linkage coverage.  Deliberately not a percentage: the
#: number of tests reaching a symbol says nothing about what fraction of it ran.
def LINKAGE_BUCKETS(count: int) -> str:  # noqa: N802 - a named scale, not a class
    if count <= 0:
        return "unlinked"
    if count == 1:
        return "1"
    if count <= 4:
        return "2-4"
    return "5+"


# ---------------------------------------------------------------------------
# Linkage coverage, from the graph itself
# ---------------------------------------------------------------------------


def linkage_counts(edges: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Count the distinct tests reaching each node.

    Always available, because the analyzer already emits these edges; no extra
    run and no report file needed.  Distinct, because the same test importing a
    module twice is still one test.
    """
    reached: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge.get("type") == COVERAGE_EDGE_TYPE:
            reached[edge["to"]].add(edge["from"])
    return {node: len(tests) for node, tests in reached.items()}


# ---------------------------------------------------------------------------
# Line coverage, from an optional report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LineReport:
    """Per-file line hit counts read from a Cobertura-style coverage report."""

    lines: dict[str, dict[int, int]]
    source: str

    def mentions(self, path: str) -> bool:
        return path in self.lines


def load_line_coverage(
    path: Path, *, newest_source_mtime: float | None = None
) -> LineReport | None:
    """Read a coverage report, refusing one that predates the source.

    A stale report colours the graph as confidently as a fresh one, and the
    reader has no way to tell.  Refusing it costs a colour mode and keeps the
    page honest; the caller falls back to linkage and says so in the legend.
    """
    path = Path(path)
    if not path.exists():
        return None
    if (
        newest_source_mtime is not None
        and path.stat().st_mtime < newest_source_mtime
    ):
        return None

    try:
        root = ElementTree.parse(path).getroot()  # noqa: S314 - our own report
    except ElementTree.ParseError:
        return None

    lines: dict[str, dict[int, int]] = defaultdict(dict)
    for klass in root.iter("class"):
        filename = klass.get("filename")
        if not filename:
            continue
        for line in klass.iter("line"):
            number, hits = line.get("number"), line.get("hits")
            if number is None or hits is None:
                continue
            lines[filename][int(number)] = int(hits)

    return LineReport(lines=dict(lines), source=path.name)


def symbol_coverage(
    report: LineReport | None, path: str, start: int, end: int
) -> tuple[int, int] | None:
    """Return (covered, total) statements within a symbol's span, or None.

    None means unmeasured, and the caller must render it differently from
    ``(0, n)``, which means measured and untested.
    """
    if report is None or not report.mentions(path):
        return None
    hits = report.lines[path]
    within = [count for line, count in hits.items() if start <= line <= end]
    if not within:
        return None
    return sum(1 for count in within if count > 0), len(within)


def module_coverage(symbols: Iterable[tuple[int, int]]) -> float | None:
    """Aggregate symbol coverage for a module, weighted by statements.

    Weighting by statements rather than by symbol count is what makes the
    number mean what a reader assumes: a module of twenty tested one-line
    accessors and one untested hundred-line handler is not well covered.
    """
    covered = total = 0
    for symbol_covered, symbol_total in symbols:
        covered += symbol_covered
        total += symbol_total
    return covered / total if total else None


# ---------------------------------------------------------------------------
# Change deltas
# ---------------------------------------------------------------------------


class ContractUnavailableError(Exception):
    """The change-graph contract module could not be located."""


def _contract() -> Any:
    """Import the contract module, reaching the sibling skill if need be.

    The atlas renders; the contract belongs to the skill that produces change
    documents.  Rather than keep a second copy of it here -- two copies of an
    id rewrite drifting apart would silently stop matching anything -- the
    module is imported, and the sibling skill's scripts directory is added to
    the path when it is not already there.

    A repository with the atlas installed and not the projector simply cannot
    load a change document, and is told so rather than shown a page that
    quietly colours nothing.
    """
    import sys  # noqa: PLC0415

    try:
        from arch_utils import change_graph  # noqa: PLC0415

        return change_graph
    except ImportError:
        pass

    sibling = (
        Path(__file__).resolve().parents[2] / "refresh-architecture" / "scripts"
    )
    if sibling.is_dir():
        if str(sibling) not in sys.path:
            sys.path.insert(0, str(sibling))
        try:
            from arch_utils import change_graph  # noqa: PLC0415

            return change_graph
        except ImportError:
            pass

    raise ContractUnavailableError(
        "reading a change document needs the refresh-architecture skill, which "
        f"was not found at {sibling}; the atlas renders without it, but cannot "
        "colour by change"
    )


def delta_index(
    document: dict[str, Any],
    graph_node_ids: Iterable[str],
    *,
    validate: bool = False,
) -> tuple[dict[str, str], list[str]]:
    """Map architecture-graph ids to the deltas a change document gives them.

    Matching is forward-only.  A document addresses nodes by a rewritten id
    that carries a digest of the original, so the rewrite cannot be inverted;
    instead every graph id is rewritten and looked up.  Both sides therefore
    have to agree on one function, which is why it lives in the contract
    module rather than in either reader.

    Returns the deltas that matched, and the document ids that matched nothing
    -- reported rather than dropped, because a document naming nodes this graph
    does not have usually means the two were built from different commits.
    """
    change_graph = _contract()

    if validate:
        change_graph.validate_document(document)

    wanted = {node["id"]: node["delta"] for node in document.get("nodes", [])}
    deltas: dict[str, str] = {}
    for graph_id in graph_node_ids:
        rewritten = change_graph.document_id(graph_id)
        if rewritten in wanted:
            deltas[graph_id] = wanted[rewritten]

    matched = {change_graph.document_id(graph_id) for graph_id in deltas}
    unmatched = sorted(set(wanted) - matched)
    return deltas, unmatched
