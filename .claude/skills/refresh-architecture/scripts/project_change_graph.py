#!/usr/bin/env python3
"""Project a code change onto the architecture graph as a change document.

Every delta is derived from artifacts the analyzer already produced -- the
architecture graph at two commits, the traced cross-layer flows, the impact
ranking, and the git diff.  No model participates: this repository computes its
call graph from AST, tree-sitter and ts-morph, so asking one to guess the
structure from a diff would trade ground truth for a guess and determinism for
a sample.

Two rules here are worth reading before changing anything:

``TEST_COVERS`` is not a dependency edge.  It is 96% of this repository's
edges, and test functions are 57% of its nodes, so expanding the neighbourhood
across it turns every change into a picture of the test suite.  Coverage
travels as a badge on the covered node instead, and a test appears as a node
only when the change edited it.

Graph ids are not document ids.  The graph uses ids like
``py:pkg.Class.__init__``, and the contract's id pattern allows no underscore,
so ids are rewritten -- deterministically, and with a digest whenever the
rewrite could collide.

Usage:
    python3 scripts/project_change_graph.py --base origin/main \\
        --artifacts docs/architecture-analysis \\
        --base-graph docs/architecture-analysis/tmp/baseline_graph.json
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import logging
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arch_utils import change_graph  # noqa: E402

logger = logging.getLogger(__name__)

#: Contract ceilings.  Exceeding them is a validation failure, so the projector
#: trims to fit rather than emitting a document that cannot be rendered.
MAX_NODES = 256
MAX_EDGES = 512
MAX_LANES = 16
MAX_CHIPS = 8

#: Contract string limits.
LABEL_MAX = 120
HEADING_MAX = 48
BODY_MAX = 140
CHIP_VALUE_MAX = 32

#: Edge types that mean "A depends on B".  Everything else is a side effect and
#: does not widen the neighbourhood.
DEPENDENCY_EDGE_TYPES = frozenset(
    {"call", "import", "api_call", "db_access", "hook_usage", "component_child"}
)
COVERAGE_EDGE_TYPE = "TEST_COVERS"

#: Language to lane, mirroring generate_views.LANGUAGE_CONTAINER so the change
#: document and the Mermaid views describe the same containers.
LANGUAGE_LANE = {
    "python": ("backend", "Backend", 1),
    "typescript": ("frontend", "Frontend", 0),
    "sql": ("database", "Database", 2),
}
EXTERNAL_LANE = ("external", "External", 3)
TESTS_LANE = ("tests", "Tests", 4)

#: Analyzer node kind to contract node kind.  The contract's set is coarse on
#: purpose: it drives the card icon and nothing else, and anything unmapped
#: still renders as `other`.
KIND_MAP = {
    "function": "function",
    "module": "module",
    "class": "other",
    "component": "ui",
    "hook": "ui",
    "table": "datastore",
    "column": "datastore",
    "index": "datastore",
    "stored_function": "function",
    "trigger": "job",
    "migration": "config",
    "test_function": "test",
    "test_class": "test",
}

#: Analyzer edge type to contract edge kind.
EDGE_KIND_MAP = {
    "call": "call",
    "import": "dependency",
    "api_call": "http",
    "db_access": "data",
    "fk_reference": "data",
    "hook_usage": "render",
    "component_child": "render",
}

_ID_ILLEGAL = re.compile(r"[^A-Za-z0-9._:/-]")
_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


class NothingToDraw(Exception):
    """The change leaves no node to draw.

    Either it touches nothing under the analyzed roots, or corrections excluded
    everything it did touch.  The contract requires at least one node, so no
    document can express this; inventing a placeholder would put a claim on the
    page that no artifact supports.  Callers report it and exit successfully:
    a tooling-only change is legitimate, and must not fail CI for being one.
    """


@dataclass(frozen=True, order=True)
class Hunk:
    """A post-image line range touched by the change, inclusive at both ends."""

    start: int
    end: int

    def intersects(self, start: int, end: int) -> bool:
        return self.start <= end and start <= self.end


def parse_unified_diff(text: str) -> dict[str, list[Hunk]]:
    """Return post-image hunk ranges per file, from ``git diff -U0`` output.

    Ranges are read from the ``+`` side because deltas are asked of the head
    graph, whose spans are head line numbers.  A zero-length ``+`` range marks
    a pure deletion; it is kept as a single line so that removing the body of a
    symbol still registers as touching it.
    """
    hunks: dict[str, list[Hunk]] = defaultdict(list)
    current: str | None = None

    for line in text.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            if target == "/dev/null":
                current = None
            else:
                current = target[2:] if target.startswith("b/") else target
            continue
        if current is None:
            continue
        match = _HUNK_HEADER.match(line)
        if not match:
            continue
        start = int(match.group(1))
        length = int(match.group(2)) if match.group(2) is not None else 1
        end = start + length - 1 if length else start
        hunks[current].append(Hunk(start=start, end=max(start, end)))

    return {path: sorted(ranges) for path, ranges in hunks.items()}


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------


def document_id(graph_id: str) -> str:
    """Rewrite a graph id into one the contract accepts.

    The contract allows ``[A-Za-z0-9._:/-]`` only, so ``__init__`` and every
    other underscore has to go.  Sanitising alone is not injective -- ``a_b``
    and ``a-b`` would collide -- so any id that had to change, or that is too
    long, carries a digest of the original.  The result is stable across runs,
    which is what keeps SVG ids and comment anchors from moving.
    """
    slug = _ID_ILLEGAL.sub("-", graph_id)
    if slug and not slug[0].isalnum():
        slug = f"n{slug}"
    if slug == graph_id and len(slug) <= 128:
        return slug
    digest = hashlib.blake2b(graph_id.encode("utf-8"), digest_size=4).hexdigest()
    budget = 128 - len(digest) - 1
    return f"{slug[:budget]}-{digest}"


def edge_graph_id(source: str, target: str) -> str:
    return f"{source}->{target}"


def _clip(text: str, limit: int) -> str:
    """Truncate on a word boundary where one is close to the limit."""
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    spaced = cut.rsplit(" ", 1)[0]
    stem = spaced if len(spaced) >= limit // 2 else cut
    return f"{stem}…"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _is_test(node: dict[str, Any]) -> bool:
    return str(node.get("kind", "")).startswith("test_")


def _lane_of(node: dict[str, Any]) -> tuple[str, str, int]:
    if _is_test(node):
        return TESTS_LANE
    return LANGUAGE_LANE.get(node.get("language", ""), EXTERNAL_LANE)


def _repo_path(node: dict[str, Any], prefixes: dict[str, str]) -> str:
    """Return the node's file as a repository-relative POSIX path.

    The analyzer records paths relative to each language's source root, so a
    Python node's ``file`` is ``services/user.py`` while git calls the same
    file ``src/services/user.py``.  Hunks are keyed by the git spelling, so the
    two have to be reconciled before any line range is compared.
    """
    prefix = prefixes.get(node.get("language", ""), "")
    path = str(node.get("file", "")).lstrip("/")
    if prefix and not path.startswith(prefix):
        return f"{prefix.rstrip('/')}/{path}"
    return path


def _touched(node: dict[str, Any], hunks: dict[str, list[Hunk]], path: str) -> bool:
    span = node.get("span") or {}
    start = int(span.get("start", 0) or 0)
    end = int(span.get("end", start) or start)
    return any(hunk.intersects(start, end) for hunk in hunks.get(path, ()))


def _coverage_counts(edges: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for edge in edges:
        if edge.get("type") == COVERAGE_EDGE_TYPE:
            counts[edge["to"]] += 1
    return counts


def _adjacency(edges: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Undirected adjacency over dependency edges only."""
    neighbours: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge.get("type") not in DEPENDENCY_EDGE_TYPES:
            continue
        neighbours[edge["from"]].add(edge["to"])
        neighbours[edge["to"]].add(edge["from"])
    return neighbours


# ---------------------------------------------------------------------------
# Corrections overlay
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Corrections:
    """Human corrections to the inferred map.

    An overlay, never a destination: inference does not write here, and every
    run re-applies it over fresh inference.  That is what makes a correction
    keep holding as the code moves, instead of being erased by the next
    projection.
    """

    renames: list[tuple[str, str]] = field(default_factory=list)
    excludes: list[str] = field(default_factory=list)
    lanes: list[tuple[str, str]] = field(default_factory=list)
    groups: list[tuple[str, str]] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.renames or self.excludes or self.lanes or self.groups)


@dataclass(frozen=True)
class Resolution:
    """Corrections resolved against the nodes actually present."""

    excluded: set[str] = field(default_factory=set)
    renames: dict[str, str] = field(default_factory=dict)
    lanes: dict[str, str] = field(default_factory=dict)
    groups: dict[str, str] = field(default_factory=dict)
    unmatched: list[str] = field(default_factory=list)


def load_corrections(path: Path) -> Corrections:
    """Read and validate an overlay file, or return no corrections.

    A missing overlay is the ordinary case, not an error.  A malformed one is
    refused whole rather than half-applied: corrections that silently drop are
    worse than corrections that fail loudly, because the picture still looks
    plausible.
    """
    path = Path(path)
    if not path.exists():
        return Corrections()

    import yaml  # local: only the overlay path needs it

    raw = yaml.safe_load(path.read_text()) or {}
    raw.setdefault("schemaVersion", change_graph.CONTRACT_VERSION)
    validator = jsonschema.Draft202012Validator(change_graph.load_corrections_schema())
    errors = sorted(
        f"{'.'.join(str(part) for part in error.absolute_path) or '<overlay>'}: "
        f"{error.message}"
        for error in validator.iter_errors(raw)
    )
    if errors:
        raise change_graph.DocumentInvalidError(errors)

    mapping = raw.get("map", {})
    return Corrections(
        renames=[(item["match"], item["to"]) for item in mapping.get("rename", [])],
        excludes=list(mapping.get("exclude", [])),
        lanes=[(item["match"], item["lane"]) for item in mapping.get("lane", [])],
        groups=[(item["match"], item["group"]) for item in mapping.get("group", [])],
    )


def _selector_matches(
    selector: str, graph_id: str, node: dict[str, Any], prefixes: dict[str, str]
) -> bool:
    """`id:<graph-id>` addresses one node; anything else is a path glob.

    The glob is matched against the node's backing file so that a correction
    outlives the analyzer renaming the symbol.
    """
    if selector.startswith("id:"):
        return graph_id == selector[3:]
    path = _repo_path(node, prefixes)
    return fnmatch.fnmatch(path, selector) or fnmatch.fnmatch(path, f"*/{selector}")


def resolve_corrections(
    corrections: Corrections,
    nodes: dict[str, dict[str, Any]],
    prefixes: dict[str, str],
) -> Resolution:
    """Bind each selector to the nodes it names, reporting the ones that miss."""
    excluded: set[str] = set()
    renames: dict[str, str] = {}
    lanes: dict[str, str] = {}
    groups: dict[str, str] = {}
    unmatched: list[str] = []

    def apply(selector: str, sink: Any, value: str | None) -> None:
        hits = [
            graph_id
            for graph_id, node in nodes.items()
            if _selector_matches(selector, graph_id, node, prefixes)
        ]
        if not hits:
            unmatched.append(selector)
            return
        for graph_id in hits:
            if value is None:
                sink.add(graph_id)
            else:
                sink[graph_id] = value

    for selector in corrections.excludes:
        apply(selector, excluded, None)
    for selector, label in corrections.renames:
        apply(selector, renames, label)
    for selector, lane in corrections.lanes:
        apply(selector, lanes, lane)
    for selector, group in corrections.groups:
        apply(selector, groups, group)

    return Resolution(
        excluded=excluded,
        renames=renames,
        lanes=lanes,
        groups=groups,
        unmatched=sorted(set(unmatched)),
    )


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


def project(
    *,
    base_graph: dict[str, Any],
    head_graph: dict[str, Any],
    hunks: dict[str, list[Hunk]],
    flows: dict[str, Any],
    impact: dict[str, Any],
    provenance: dict[str, Any],
    stats: dict[str, int],
    path_prefixes: dict[str, str] | None = None,
    coverage: dict[str, Any] | None = None,
    title: str | None = None,
    summary: str | None = None,
    corrections: Corrections | None = None,
) -> dict[str, Any]:
    """Return a change document describing head relative to base."""
    prefixes = path_prefixes or {}
    base_nodes = {node["id"]: node for node in base_graph.get("nodes", [])}
    head_nodes = {node["id"]: node for node in head_graph.get("nodes", [])}

    deltas = _node_deltas(base_nodes, head_nodes, hunks, prefixes)
    changed = {nid for nid, delta in deltas.items() if delta != "unchanged"}

    kept = _select_nodes(changed, deltas, head_graph, base_graph)

    # Corrections land after derivation and before anything reads the result,
    # so an exclusion takes its edges, view selections and walkthrough focus
    # with it rather than leaving half an arrow behind.
    resolution = Resolution()
    if corrections and not corrections.is_empty():
        resolution = resolve_corrections(
            corrections, {**base_nodes, **head_nodes}, prefixes
        )
        kept -= resolution.excluded
        changed -= resolution.excluded
        for graph_id in resolution.excluded:
            deltas.pop(graph_id, None)
        for selector in resolution.unmatched:
            logger.warning("correction selector matched nothing: %s", selector)

    coverage_counts = _coverage_counts(head_graph.get("edges", []))

    nodes, lanes = _build_nodes(
        kept, deltas, base_nodes, head_nodes, coverage_counts, prefixes, resolution
    )
    edges = _build_edges(kept, deltas, base_graph, head_graph, impact)
    document_flows = _build_flows(flows, kept, deltas)

    if not nodes:
        raise NothingToDraw(
            "no node survives: the change touches nothing in the architecture "
            "graph, or corrections excluded everything it touched"
        )

    lenses = ["architecture"] + (["data-flow"] if document_flows else [])
    views = _build_views(nodes, changed, lenses)
    document: dict[str, Any] = {
        "schemaVersion": change_graph.CONTRACT_VERSION,
        "kind": "graph",
        "title": _clip(title or _default_title(deltas, stats), LABEL_MAX),
        "summary": summary or _default_summary(deltas, stats, coverage),
        "lenses": lenses,
        "provenance": provenance,
        "lanes": lanes,
        "nodes": nodes,
        "edges": edges,
        "flows": document_flows,
        "stats": _build_stats(stats, deltas, coverage),
        "views": views,
    }
    walkthrough = _build_walkthrough(nodes, edges, views)
    if walkthrough:
        document["walkthrough"] = walkthrough
    return document


def _node_deltas(
    base_nodes: dict[str, dict],
    head_nodes: dict[str, dict],
    hunks: dict[str, list[Hunk]],
    prefixes: dict[str, str],
) -> dict[str, str]:
    deltas: dict[str, str] = {}
    for node_id, node in head_nodes.items():
        if node_id not in base_nodes:
            deltas[node_id] = "added"
        elif _touched(node, hunks, _repo_path(node, prefixes)):
            deltas[node_id] = "modified"
        else:
            deltas[node_id] = "unchanged"
    for node_id in base_nodes:
        if node_id not in head_nodes:
            deltas[node_id] = "removed"
    return deltas


def _select_nodes(
    changed: set[str],
    deltas: dict[str, str],
    head_graph: dict[str, Any],
    base_graph: dict[str, Any],
) -> set[str]:
    """Changed nodes, plus one dependency hop of context, bounded by the cap.

    Removed nodes have no neighbours in the head graph, so their context comes
    from the base graph's adjacency.
    """
    head_adjacency = _adjacency(head_graph.get("edges", []))
    base_adjacency = _adjacency(base_graph.get("edges", []))

    neighbours: set[str] = set()
    for node_id in changed:
        neighbours |= head_adjacency.get(node_id, set())
        neighbours |= base_adjacency.get(node_id, set())
    neighbours -= changed

    if len(changed) >= MAX_NODES:
        return set(sorted(changed)[:MAX_NODES])

    room = MAX_NODES - len(changed)
    # Prefer the best-connected neighbours: they are the ones a reader is most
    # likely to already hold in their head as the change's surroundings.
    ranked = sorted(
        neighbours,
        key=lambda nid: (-len(head_adjacency.get(nid, ())), nid),
    )
    return changed | set(ranked[:room])


def _build_nodes(
    kept: set[str],
    deltas: dict[str, str],
    base_nodes: dict[str, dict],
    head_nodes: dict[str, dict],
    coverage_counts: dict[str, int],
    prefixes: dict[str, str],
    resolution: Resolution | None = None,
) -> tuple[list[dict], list[dict]]:
    resolution = resolution or Resolution()
    nodes: list[dict] = []
    lanes_used: dict[str, tuple[str, int]] = {}

    for graph_id in sorted(kept):
        node = head_nodes.get(graph_id) or base_nodes.get(graph_id)
        if node is None:
            continue
        lane_id, lane_label, lane_order = _lane_of(node)
        corrected_lane = resolution.lanes.get(graph_id)
        if corrected_lane:
            # A lane correction may name a band inference never declared; it is
            # created, with its id for a label, so an author writes a name
            # rather than looking one up.
            lane_id, lane_label, lane_order = corrected_lane, corrected_lane, 9
        lanes_used[lane_id] = (lane_label, lane_order)

        path = _repo_path(node, prefixes)
        span = node.get("span") or {}
        entry: dict[str, Any] = {
            "id": document_id(graph_id),
            "label": _clip(
                resolution.renames.get(graph_id) or str(node.get("name") or graph_id),
                LABEL_MAX,
            ),
            "kind": KIND_MAP.get(str(node.get("kind")), "other"),
            "delta": deltas.get(graph_id, "unchanged"),
            "lane": lane_id,
            "files": [],
            "badges": [],
        }
        group = resolution.groups.get(graph_id) or _group_of(path)
        if group:
            entry["group"] = document_id(group)
        if path:
            file_ref: dict[str, Any] = {"path": path}
            if span.get("start"):
                file_ref["startLine"] = int(span["start"])
                file_ref["endLine"] = int(span.get("end") or span["start"])
            entry["files"] = [file_ref]

        badge = _coverage_badge(node, coverage_counts.get(graph_id, 0))
        if badge:
            entry["badges"] = [badge]
        nodes.append(entry)

    lanes = [
        {"id": lane_id, "label": label, "order": order}
        for lane_id, (label, order) in sorted(
            lanes_used.items(), key=lambda item: (item[1][1], item[0])
        )
    ][:MAX_LANES]
    return nodes, lanes


def _coverage_badge(node: dict[str, Any], count: int) -> str | None:
    """Coverage as a chip on the covered node, never as extra nodes."""
    if _is_test(node) or str(node.get("kind")) == "module":
        return None
    if count == 0:
        return "untested"
    return f"{count} test" if count == 1 else f"{count} tests"


def _group_of(path: str) -> str | None:
    """Cluster by the first two path segments, as the component views do."""
    parts = Path(path).parts
    if len(parts) < 2:
        return None
    return "/".join(parts[:2])


def _build_edges(
    kept: set[str],
    deltas: dict[str, str],
    base_graph: dict[str, Any],
    head_graph: dict[str, Any],
    impact: dict[str, Any],
) -> list[dict]:
    def signature(edge: dict) -> tuple[str, str, str]:
        return (edge["from"], edge["to"], edge.get("type", "call"))

    base_edges = {
        signature(edge)
        for edge in base_graph.get("edges", [])
        if edge.get("type") != COVERAGE_EDGE_TYPE
    }
    seen: set[tuple[str, str, str]] = set()
    built: list[dict] = []

    candidates = list(head_graph.get("edges", [])) + list(base_graph.get("edges", []))
    for edge in candidates:
        if edge.get("type") == COVERAGE_EDGE_TYPE:
            continue
        source, target = edge.get("from"), edge.get("to")
        if source not in kept or target not in kept:
            continue
        key = signature(edge)
        if key in seen:
            continue
        seen.add(key)

        in_head = any(
            signature(candidate) == key for candidate in head_graph.get("edges", [])
        )
        if key not in base_edges:
            delta = "added"
        elif not in_head:
            delta = "removed"
        elif "modified" in (deltas.get(source), deltas.get(target)):
            delta = "modified"
        else:
            delta = "unchanged"

        built.append(
            {
                "id": document_id(edge_graph_id(source, target)),
                "from": document_id(source),
                "to": document_id(target),
                "kind": EDGE_KIND_MAP.get(str(edge.get("type")), "other"),
                "delta": delta,
                "emphasis": "normal",
                "animated": False,
                "files": [],
            }
        )

    built.sort(key=lambda item: item["id"])
    built = built[:MAX_EDGES]
    _mark_hero(built, impact)
    return built


def _mark_hero(edges: list[dict], impact: dict[str, Any]) -> None:
    """Emphasise the added edge reaching the most depended-upon node.

    One hero, or none.  More than a couple and the emphasis stops meaning
    anything, which is the whole reason the contract has the field.
    """
    ranking = {
        document_id(entry["id"]): int(entry.get("dependent_count", 0))
        for entry in impact.get("high_impact_nodes", [])
    }
    added = [edge for edge in edges if edge["delta"] == "added"]
    if not added:
        return
    hero = max(added, key=lambda edge: (ranking.get(edge["to"], 0), edge["id"]))
    hero["emphasis"] = "hero"
    hero["animated"] = True


def _build_flows(
    flows: dict[str, Any], kept: set[str], deltas: dict[str, str]
) -> list[dict]:
    """Map traced cross-layer flows that pass through changed code.

    This repository currently traces none: the cross-layer linkers need
    api_call and db_access edges, and the graph holds only call edges today.
    The mapping is still exercised by synthetic fixtures so that it works the
    day those edges appear.
    """
    built: list[dict] = []
    for flow in flows.get("flows", []):
        path = [step for step in flow.get("path", []) if step in kept]
        if len(path) < 2 or not any(deltas.get(step) != "unchanged" for step in path):
            continue
        participants = [{"node": document_id(step)} for step in path[:12]]
        messages = []
        for index, (source, target) in enumerate(zip(path, path[1:], strict=False)):
            messages.append(
                {
                    "id": document_id(f"{flow.get('id', 'flow')}-{index}"),
                    "from": document_id(source),
                    "to": document_id(target),
                    "label": _clip(str(flow.get("label") or "calls"), LABEL_MAX),
                    "kind": "sync",
                    "delta": (
                        "modified"
                        if "modified" in (deltas.get(source), deltas.get(target))
                        else "unchanged"
                    ),
                    "animated": True,
                    "files": [],
                }
            )
        if messages:
            built.append(
                {
                    "id": document_id(str(flow.get("id", f"flow-{len(built)}"))),
                    "title": _clip(str(flow.get("title") or "Traced flow"), LABEL_MAX),
                    "delta": "modified",
                    "participants": participants,
                    "messages": messages[:64],
                }
            )
    return built[:16]


def _build_views(
    nodes: list[dict], changed: set[str], lenses: list[str]
) -> list[dict]:
    """A root view of everything, narrowed by package, then by changed symbols."""
    changed_ids = {document_id(graph_id) for graph_id in changed}
    present_changed = sorted(
        node["id"] for node in nodes if node["id"] in changed_ids
    )
    root: dict[str, Any] = {
        "id": "blast-radius",
        "title": "Blast radius",
        "lens": "architecture",
        "scope": {"kind": "all"},
        "defaultOpen": True,
        "children": [],
    }
    if not present_changed:
        return [root]

    by_group: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        if node["id"] in changed_ids and node.get("group"):
            by_group[node["group"]].append(node["id"])

    all_ids = {node["id"] for node in nodes}
    for group, members in sorted(by_group.items()):
        scope_nodes = sorted(set(members))
        if set(scope_nodes) == all_ids:
            # A child that selects the whole document repeats its parent.
            continue
        root["children"].append(
            {
                "id": document_id(f"group-{group}"),
                "title": _clip(group, LABEL_MAX),
                "lens": "architecture",
                "scope": {"kind": "selection", "nodes": scope_nodes},
                "defaultOpen": False,
                "children": [],
            }
        )
    root["children"] = root["children"][:32]
    return [root]


def _build_stats(
    stats: dict[str, int], deltas: dict[str, str], coverage: dict[str, Any] | None
) -> dict[str, Any]:
    chips: list[dict[str, str]] = []
    counts = defaultdict(int)
    for delta in deltas.values():
        counts[delta] += 1
    if counts["added"]:
        chips.append(
            {
                "label": "Symbols added",
                "value": _clip(str(counts["added"]), CHIP_VALUE_MAX),
                "tone": "added",
            }
        )
    if counts["removed"]:
        chips.append(
            {
                "label": "Symbols removed",
                "value": _clip(str(counts["removed"]), CHIP_VALUE_MAX),
                "tone": "removed",
            }
        )
    if coverage and coverage.get("uncovered_files"):
        chips.append(
            {
                "label": "Files outside the graph",
                "value": _clip(
                    f"{coverage['uncovered_files']} of {coverage.get('changed_files', '?')}",
                    CHIP_VALUE_MAX,
                ),
                "tone": "neutral",
            }
        )
    return {
        "filesChanged": int(stats.get("filesChanged", 0)),
        "additions": int(stats.get("additions", 0)),
        "deletions": int(stats.get("deletions", 0)),
        "chips": chips[:MAX_CHIPS],
    }


def _build_walkthrough(
    nodes: list[dict], edges: list[dict], views: list[dict]
) -> dict[str, Any] | None:
    """A structural tour.  Narration may fill the words; the ids are ours.

    Fewer than two steps is a caption rather than a tour, so the contract
    refuses it and so does this.
    """
    changed = sorted(node["id"] for node in nodes if node["delta"] != "unchanged")
    if not changed:
        return None

    steps: list[dict[str, Any]] = [
        {
            "id": "what-changed",
            "heading": _clip("What this change touches", HEADING_MAX),
            "body": _clip(
                f"{len(changed)} symbols changed, shown against the code around them.",
                BODY_MAX,
            ),
            "stage": {"kind": "view", "view": views[0]["id"]},
            "focus": {"kind": "selection", "nodes": changed[:256]},
        }
    ]

    # One step per touched package, so an ordinary change -- no new edges, no
    # removals -- still gets a tour rather than falling below the contract's
    # two-step floor and losing its walkthrough entirely.
    for child in views[0].get("children", []):
        scope = child.get("scope", {})
        focus_nodes = sorted(scope.get("nodes", []))
        if not focus_nodes:
            continue
        steps.append(
            {
                "id": document_id(f"tour-{child['id']}"),
                "heading": _clip(child["title"], HEADING_MAX),
                "body": _clip(
                    f"{len(focus_nodes)} changed "
                    f"{'symbol' if len(focus_nodes) == 1 else 'symbols'} here.",
                    BODY_MAX,
                ),
                "stage": {"kind": "view", "view": child["id"]},
                "focus": {"kind": "selection", "nodes": focus_nodes},
            }
        )

    hero = next((edge for edge in edges if edge.get("emphasis") == "hero"), None)
    if hero:
        steps.append(
            {
                "id": "the-new-path",
                "heading": _clip("The connection it turns on", HEADING_MAX),
                "body": _clip(
                    "The new edge reaching the most depended-upon code in view.",
                    BODY_MAX,
                ),
                "stage": {"kind": "view", "view": views[0]["id"]},
                "focus": {"kind": "selection", "edges": [hero["id"]]},
            }
        )

    removed = sorted(node["id"] for node in nodes if node["delta"] == "removed")
    if removed:
        steps.append(
            {
                "id": "what-went",
                "heading": _clip("What it retires", HEADING_MAX),
                "body": _clip(f"{len(removed)} symbols no longer exist.", BODY_MAX),
                "stage": {"kind": "view", "view": views[0]["id"]},
                "focus": {"kind": "selection", "nodes": removed[:256]},
            }
        )

    return {"steps": steps[:12]} if len(steps) >= 2 else None


def _default_title(deltas: dict[str, str], stats: dict[str, int]) -> str:
    files = stats.get("filesChanged", 0)
    changed = sum(1 for delta in deltas.values() if delta != "unchanged")
    return f"{changed} symbols across {files} files"


def _default_summary(
    deltas: dict[str, str], stats: dict[str, int], coverage: dict[str, Any] | None
) -> str:
    counts = defaultdict(int)
    for delta in deltas.values():
        counts[delta] += 1
    parts = [
        f"{counts['added']} added",
        f"{counts['modified']} modified",
        f"{counts['removed']} removed",
    ]
    sentence = (
        f"This change touches {', '.join(parts)} symbols in the architecture graph, "
        f"drawn against the code one dependency hop away."
    )
    if coverage and coverage.get("uncovered_files"):
        sentence += (
            f" {coverage['uncovered_files']} changed files are outside the analyzed "
            "roots and do not appear here."
        )
    return sentence


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _diff_stats(repo: Path, base: str, head: str) -> dict[str, int]:
    numstat = _git(repo, "diff", "--numstat", "--find-renames", f"{base}...{head}")
    files = additions = deletions = 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        files += 1
        if parts[0].isdigit():
            additions += int(parts[0])
        if parts[1].isdigit():
            deletions += int(parts[1])
    return {"filesChanged": files, "additions": additions, "deletions": deletions}


def _coverage_of(
    hunks: dict[str, list[Hunk]], head_graph: dict[str, Any], prefixes: dict[str, str]
) -> dict[str, Any]:
    """Count changed files the graph never saw.

    Reported rather than hidden: a picture that silently omits half a change
    is worse than one that says how much it is showing.
    """
    known = {
        _repo_path(node, prefixes) for node in head_graph.get("nodes", []) if node.get("file")
    }
    changed = sorted(hunks)
    uncovered = sorted(path for path in changed if path not in known)
    return {
        "changed_files": len(changed),
        "uncovered_files": len(uncovered),
        "uncovered": uncovered[:200],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="project_change_graph",
        description="Project a code change onto the architecture graph.",
    )
    parser.add_argument("--repo", default=".", help="Repository root (default: .)")
    parser.add_argument("--base", default="origin/main", help="Base ref")
    parser.add_argument("--head", default="HEAD", help="Head ref")
    parser.add_argument(
        "--artifacts",
        default="docs/architecture-analysis",
        help="Directory holding the architecture artifacts",
    )
    parser.add_argument(
        "--base-graph",
        help="Architecture graph at the base commit. Without it every node "
        "reads as unchanged unless a hunk touches it, because the graph is "
        "gitignored and has no committed history to compare against.",
    )
    parser.add_argument("-o", "--out", help="Output document path")
    parser.add_argument(
        "--python-src-dir", default="src", help="Python source root (default: src)"
    )
    parser.add_argument(
        "--ts-src-dir", default="web", help="TypeScript source root (default: web)"
    )
    parser.add_argument(
        "--corrections",
        default="settings/change-graph.yaml",
        help="Corrections overlay (default: settings/change-graph.yaml)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    args = build_parser().parse_args(argv)

    repo = Path(args.repo).resolve()
    artifacts = Path(args.artifacts)
    if not artifacts.is_absolute():
        artifacts = repo / artifacts

    head_graph_path = artifacts / "architecture.graph.json"
    if not head_graph_path.exists():
        logger.error(
            "no architecture graph at %s; run `make architecture-refresh` first",
            head_graph_path,
        )
        return 1

    merge_base = _git(repo, "merge-base", args.base, args.head).strip()
    head_sha = _git(repo, "rev-parse", args.head).strip()
    diff = _git(
        repo, "diff", "-U0", "--find-renames", f"{merge_base}...{head_sha}"
    )
    hunks = parse_unified_diff(diff)
    if not hunks:
        logger.error("%s and %s have the same content; there is nothing to draw", args.base, args.head)
        return 1

    head_graph = json.loads(head_graph_path.read_text())
    base_graph = (
        json.loads(Path(args.base_graph).read_text())
        if args.base_graph
        else {"nodes": head_graph.get("nodes", []), "edges": head_graph.get("edges", [])}
    )
    if not args.base_graph:
        logger.warning(
            "no --base-graph: added and removed symbols cannot be distinguished "
            "from unchanged ones, so only hunk-touched symbols are marked"
        )

    flows = _load(artifacts / "cross_layer_flows.json", {"flows": []})
    impact = _load(artifacts / "high_impact_nodes.json", {"high_impact_nodes": []})
    prefixes = {"python": args.python_src_dir, "typescript": args.ts_src_dir}
    coverage = _coverage_of(hunks, head_graph, prefixes)

    slug = f"{merge_base[:7]}..{head_sha[:7]}"
    out = Path(args.out) if args.out else artifacts / "change" / slug / "graph.json"

    try:
        document = project(
            base_graph=base_graph,
            head_graph=head_graph,
            hunks=hunks,
            flows=flows,
            impact=impact,
            provenance={
                "repo": _repo_slug(repo),
                "base": {"sha": merge_base[:40]},
                "head": {"sha": head_sha[:40]},
                "generator": {"name": "project_change_graph", "version": "0.1.0"},
            },
            stats=_diff_stats(repo, merge_base, head_sha),
            path_prefixes=prefixes,
            coverage=coverage,
            corrections=load_corrections(repo / args.corrections),
        )
    except NothingToDraw as reason:
        out.parent.mkdir(parents=True, exist_ok=True)
        (out.parent / "coverage.json").write_text(change_graph.serialize(coverage))
        roots = ", ".join(sorted(set(prefixes.values())))
        logger.warning(
            "%s; %d of %d changed files lie under the analyzed roots (%s). "
            "Wrote %s",
            reason,
            coverage["changed_files"] - coverage["uncovered_files"],
            coverage["changed_files"],
            roots,
            out.parent / "coverage.json",
        )
        return 0

    try:
        written = change_graph.write_document(out, document)
    except change_graph.ChangeGraphError as error:
        logger.error("the projected document does not validate: %s", error)
        return 1

    (out.parent / "coverage.json").write_text(change_graph.serialize(coverage))
    logger.info(
        "✓ %s — %d nodes, %d edges, %d flows (%d of %d changed files covered)",
        written,
        len(document["nodes"]),
        len(document["edges"]),
        len(document["flows"]),
        coverage["changed_files"] - coverage["uncovered_files"],
        coverage["changed_files"],
    )
    return 0


def _load(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        logger.warning("missing %s; continuing without it", path)
        return default
    return json.loads(path.read_text())


def _repo_slug(repo: Path) -> dict[str, str]:
    try:
        url = _git(repo, "remote", "get-url", "origin").strip()
    except subprocess.CalledProcessError:
        return {"owner": "local", "name": repo.name}
    match = re.search(r"[:/]([^/]+)/([^/]+?)(?:\.git)?$", url)
    if not match:
        return {"owner": "local", "name": repo.name}
    return {"owner": match.group(1), "name": match.group(2), "host": "github.com"}


if __name__ == "__main__":
    raise SystemExit(main())
