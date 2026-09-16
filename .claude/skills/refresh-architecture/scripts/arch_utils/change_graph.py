"""Validation for change-graph documents.

The document contract is vendored under ``<skill>/contracts`` rather than
fetched at run time, so projection is deterministic and works offline.

Two validators read that contract: this module, and the Node renderer through
its pinned npm package.  They must agree, and the JSON Schema alone is not
enough to make them agree.  The upstream contract is authored in zod, where
rules such as "every edge endpoint is a declared node" live in ``.refine()``
calls -- and a refinement does not survive export to JSON Schema.  A document
with an edge pointing at a node that does not exist therefore passes the
exported schema and is rejected by the renderer.

So this module validates in two passes: the exported schema for shape, then
the referential rules the schema cannot express.  Skipping the second pass
would move that failure from projection, where the message names the offending
id, to CI at render time, where it does not.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

#: Contract version this skill is vendored against, as ``major.minor.patch``.
#: Deliberately a literal rather than a read of the schema: it is the
#: independent statement that the test compares the vendored file against.
CONTRACT_VERSION = "0.1.1"

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"
SCHEMA_PATH = CONTRACTS_DIR / "graph-doc.schema.json"
CORRECTIONS_SCHEMA_PATH = CONTRACTS_DIR / "corrections.schema.json"

#: Message kinds whose endpoints must differ, and the one that requires them equal.
_SELF_KIND = "self"


_ID_ILLEGAL = re.compile(r"[^A-Za-z0-9._:/-]")


def document_id(graph_id: str) -> str:
    """Rewrite an architecture-graph id into one the contract accepts.

    The contract allows ``[A-Za-z0-9._:/-]``, which most symbol ids already
    satisfy -- underscores included, so ``py:pkg.Class.__init__`` passes
    through unchanged.  Two things do not: an edge id, which this codebase
    spells ``<from>-><to>`` and whose ``>`` is illegal, and any id past the
    contract's 128-character limit, which deeply nested symbols reach.

    Rewriting alone is not injective, since ``a_b`` and ``a-b`` would collapse
    onto the same slug, so anything that had to change carries a digest of the
    original.  An id that needed no change is returned as it is, which keeps
    the common case readable in URLs and SVG ids.

    It lives here rather than in the projector because it is how a document
    addresses graph nodes: every reader matching a document back onto the
    graph needs exactly this function, and two copies of it drifting would
    silently stop matching anything.
    """
    slug = _ID_ILLEGAL.sub("-", graph_id)
    if slug and not slug[0].isalnum():
        slug = f"n{slug}"
    if slug == graph_id and len(slug) <= 128:
        return slug
    digest = hashlib.blake2b(graph_id.encode("utf-8"), digest_size=4).hexdigest()
    budget = 128 - len(digest) - 1
    return f"{slug[:budget]}-{digest}"


class ChangeGraphError(Exception):
    """Base class for change-graph contract failures."""


class ContractVersionError(ChangeGraphError):
    """The document declares a contract this skill cannot read."""


class DocumentInvalidError(ChangeGraphError):
    """The document does not satisfy the contract.

    Carries every error rather than the first, because a producer correcting
    one at a time needs as many round trips as it has mistakes.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


# ---------------------------------------------------------------------------
# Schema access
# ---------------------------------------------------------------------------


@lru_cache(maxsize=2)
def _load_schema(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_schema() -> dict[str, Any]:
    """Return the vendored graph document schema."""
    return _load_schema(str(SCHEMA_PATH))


def load_corrections_schema() -> dict[str, Any]:
    """Return the vendored corrections overlay schema."""
    return _load_schema(str(CORRECTIONS_SCHEMA_PATH))


def _minor_series(version: str) -> str:
    parts = version.split(".")
    return ".".join(parts[:2])


def check_contract_version(document: dict[str, Any]) -> None:
    """Raise when the document's contract is outside this skill's series.

    The error names both versions: a consumer told only that a document is
    "unsupported" cannot tell whether to upgrade the skill or re-project.
    """
    declared = document.get("schemaVersion")
    if not isinstance(declared, str) or not declared:
        raise ContractVersionError(
            f"document declares no schemaVersion; this skill reads {CONTRACT_VERSION}"
        )
    if _minor_series(declared) != _minor_series(CONTRACT_VERSION):
        raise ContractVersionError(
            f"document declares contract {declared}, but this skill reads "
            f"{CONTRACT_VERSION}"
        )


# ---------------------------------------------------------------------------
# Pass 1: shape
# ---------------------------------------------------------------------------


def _format_path(error: jsonschema.ValidationError) -> str:
    return ".".join(str(part) for part in error.absolute_path) or "<document>"


def schema_errors(document: dict[str, Any]) -> list[str]:
    """Return every JSON Schema violation, sorted for stable output."""
    validator = jsonschema.Draft202012Validator(load_schema())
    return sorted(
        f"{_format_path(error)}: {error.message}"
        for error in validator.iter_errors(document)
    )


# ---------------------------------------------------------------------------
# Pass 2: references the schema cannot express
# ---------------------------------------------------------------------------


def _duplicate_ids(items: list[dict[str, Any]], label: str) -> list[str]:
    seen: set[str] = set()
    errors: list[str] = []
    for item in items:
        identifier = item.get("id")
        if not isinstance(identifier, str):
            continue
        if identifier in seen:
            errors.append(f"{label}: duplicate id '{identifier}'")
        seen.add(identifier)
    return errors


def _file_path_errors(owner: str, refs: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for ref in refs:
        path = ref.get("path")
        if not isinstance(path, str):
            continue
        if path.startswith("/"):
            errors.append(f"{owner}: file path '{path}' must not start with '/'")
        if "\\" in path:
            errors.append(f"{owner}: file path '{path}' must use POSIX separators")
        if ".." in Path(path).parts:
            errors.append(f"{owner}: file path '{path}' must not contain '..'")
        if len(path) > 1 and path[1] == ":":
            errors.append(f"{owner}: file path '{path}' must not carry a drive letter")
    return errors


def _view_ids(views: list[dict[str, Any]]) -> set[str]:
    found: set[str] = set()
    for view in views:
        identifier = view.get("id")
        if isinstance(identifier, str):
            found.add(identifier)
        found |= _view_ids(view.get("children", []))
    return found


def _walk_views(views: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for view in views:
        flat.append(view)
        flat.extend(_walk_views(view.get("children", [])))
    return flat


def _scope_errors(
    owner: str,
    scope: dict[str, Any],
    *,
    lanes: set[str],
    nodes: set[str],
    edges: set[str],
    flows: set[str],
) -> list[str]:
    if scope.get("kind") != "selection":
        return []
    known = {"lanes": lanes, "nodes": nodes, "edges": edges, "flows": flows}
    errors: list[str] = []
    for field, universe in known.items():
        for identifier in scope.get(field, []):
            if identifier not in universe:
                errors.append(
                    f"{owner}: selects {field[:-1]} '{identifier}', which the "
                    "document does not declare"
                )
    return errors


def reference_errors(document: dict[str, Any]) -> list[str]:
    """Return violations of the rules the exported schema cannot express.

    These mirror the upstream zod refinements.  Keeping them here is what
    stops this validator from being laxer than the renderer's.
    """
    lanes = document.get("lanes", [])
    nodes = document.get("nodes", [])
    edges = document.get("edges", [])
    flows = document.get("flows", [])
    views = document.get("views", [])
    lenses = set(document.get("lenses", []))

    lane_ids = {lane["id"] for lane in lanes if isinstance(lane.get("id"), str)}
    node_ids = {node["id"] for node in nodes if isinstance(node.get("id"), str)}
    edge_ids = {edge["id"] for edge in edges if isinstance(edge.get("id"), str)}
    flow_ids = {flow["id"] for flow in flows if isinstance(flow.get("id"), str)}

    errors: list[str] = []
    errors += _duplicate_ids(lanes, "lanes")
    errors += _duplicate_ids(nodes, "nodes")
    errors += _duplicate_ids(edges, "edges")
    errors += _duplicate_ids(flows, "flows")

    for node in nodes:
        identifier = node.get("id", "<unknown>")
        lane = node.get("lane")
        if lane is not None and lane not in lane_ids:
            errors.append(
                f"nodes.{identifier}: sits in lane '{lane}', which the document "
                "does not declare"
            )
        errors += _file_path_errors(f"nodes.{identifier}", node.get("files", []))

    for edge in edges:
        identifier = edge.get("id", "<unknown>")
        for end in ("from", "to"):
            target = edge.get(end)
            if target is not None and target not in node_ids:
                errors.append(
                    f"edges.{identifier}: {end} '{target}' is not a declared node"
                )
        errors += _file_path_errors(f"edges.{identifier}", edge.get("files", []))

    for flow in flows:
        flow_id = flow.get("id", "<unknown>")
        participants = {
            participant["node"]
            for participant in flow.get("participants", [])
            if isinstance(participant.get("node"), str)
        }
        for participant in sorted(participants):
            if participant not in node_ids:
                errors.append(
                    f"flows.{flow_id}: participant '{participant}' is not a "
                    "declared node"
                )
        for message in flow.get("messages", []):
            message_id = message.get("id", "<unknown>")
            owner = f"flows.{flow_id}.messages.{message_id}"
            source, target = message.get("from"), message.get("to")
            for end, value in (("from", source), ("to", target)):
                if value is not None and value not in participants:
                    errors.append(
                        f"{owner}: {end} '{value}' is not a participant of this flow"
                    )
            is_self_kind = message.get("kind") == _SELF_KIND
            if is_self_kind != (source == target):
                errors.append(
                    f"{owner}: kind '{message.get('kind')}' and from == to must agree"
                )
            errors += _file_path_errors(owner, message.get("files", []))

    if flows and "data-flow" not in lenses:
        errors.append(
            "<document>: carries flows but does not declare the 'data-flow' lens"
        )

    flat_views = _walk_views(views)
    seen_view_ids: set[str] = set()
    for view in flat_views:
        view_id = view.get("id", "<unknown>")
        if view_id in seen_view_ids:
            errors.append(f"views: duplicate id '{view_id}'")
        seen_view_ids.add(view_id)
        lens = view.get("lens")
        if lens is not None and lens not in lenses:
            errors.append(
                f"views.{view_id}: uses lens '{lens}', which the document does "
                "not declare"
            )
        errors += _scope_errors(
            f"views.{view_id}",
            view.get("scope", {"kind": "all"}),
            lanes=lane_ids,
            nodes=node_ids,
            edges=edge_ids,
            flows=flow_ids,
        )

    errors += _walkthrough_errors(
        document.get("walkthrough"),
        lanes=lane_ids,
        nodes=node_ids,
        edges=edge_ids,
        flows=flows,
        view_ids=_view_ids(views),
    )
    errors += _layout_errors(document.get("layout"), lane_ids=lane_ids, node_ids=node_ids)
    return sorted(errors)


def _walkthrough_errors(
    walkthrough: dict[str, Any] | None,
    *,
    lanes: set[str],
    nodes: set[str],
    edges: set[str],
    flows: list[dict[str, Any]],
    view_ids: set[str],
) -> list[str]:
    if not walkthrough:
        return []
    flows_by_id = {
        flow["id"]: flow for flow in flows if isinstance(flow.get("id"), str)
    }
    errors: list[str] = []
    for step in walkthrough.get("steps", []):
        step_id = step.get("id", "<unknown>")
        owner = f"walkthrough.{step_id}"
        stage = step.get("stage")
        staged_messages: set[str] = set()
        if stage is not None:
            if stage.get("kind") == "view" and stage.get("view") not in view_ids:
                errors.append(
                    f"{owner}: stages view '{stage.get('view')}', which the "
                    "document does not declare"
                )
            elif stage.get("kind") == "flow":
                flow = flows_by_id.get(stage.get("flow"))
                if flow is None:
                    errors.append(
                        f"{owner}: stages flow '{stage.get('flow')}', which the "
                        "document does not declare"
                    )
                else:
                    staged_messages = {
                        message["id"]
                        for message in flow.get("messages", [])
                        if isinstance(message.get("id"), str)
                    }

        focus = step.get("focus", {"kind": "all"})
        if focus.get("kind") != "selection":
            continue
        for field, universe in (
            ("lanes", lanes),
            ("nodes", nodes),
            ("edges", edges),
            ("messages", staged_messages),
        ):
            for identifier in focus.get(field, []):
                if identifier not in universe:
                    errors.append(
                        f"{owner}: focuses {field[:-1]} '{identifier}', which is "
                        "not on this step's stage"
                    )
    return errors


def _layout_errors(
    layout: dict[str, Any] | None, *, lane_ids: set[str], node_ids: set[str]
) -> list[str]:
    if not layout:
        return []
    errors: list[str] = []
    for lane in layout.get("laneOrder", []):
        if lane not in lane_ids:
            errors.append(f"layout.laneOrder: '{lane}' is not a declared lane")
    for node in layout.get("rank", {}):
        if node not in node_ids:
            errors.append(f"layout.rank: '{node}' is not a declared node")
    return errors


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def validation_errors(document: dict[str, Any]) -> list[str]:
    """Return every contract violation: shape first, then references.

    References are only checked once the shape is sound, because a document
    whose ``nodes`` is not a list produces reference errors that are noise
    beside the one real problem.
    """
    errors = schema_errors(document)
    if errors:
        return errors
    return reference_errors(document)


def validate_document(document: dict[str, Any]) -> None:
    """Raise unless *document* satisfies the vendored contract."""
    check_contract_version(document)
    errors = validation_errors(document)
    if errors:
        raise DocumentInvalidError(errors)


def serialize(document: dict[str, Any]) -> str:
    """Render *document* as deterministic JSON text.

    Keys are sorted so that two runs over equal data produce equal bytes,
    which is what makes "nothing moved since the last push" checkable.
    """
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_document(path: Path, document: dict[str, Any]) -> Path:
    """Validate then write *document*, or write a rejection sidecar and raise.

    An invalid document never reaches its final path: a half-valid graph.json
    read by a later step is worse than no file at all.  The sidecar keeps the
    evidence next to where the file would have been.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        validate_document(document)
    except ContractVersionError as error:
        _write_rejection(path, document, [str(error)])
        raise
    except DocumentInvalidError as error:
        _write_rejection(path, document, error.errors)
        raise

    path.write_text(serialize(document), encoding="utf-8")
    return path


def _write_rejection(path: Path, document: dict[str, Any], errors: list[str]) -> Path:
    sidecar = path.parent / f"{path.stem}.rejected.json"
    sidecar.write_text(
        serialize({"errors": errors, "document": document}), encoding="utf-8"
    )
    return sidecar
