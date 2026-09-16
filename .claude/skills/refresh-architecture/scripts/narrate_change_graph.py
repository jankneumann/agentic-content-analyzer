#!/usr/bin/env python3
"""Fill a projected change document's prose, and nothing else.

Structure comes from the architecture artifacts; only the words come from a
model.  That split is enforced mechanically rather than by prompting: the merge
reads a closed set of text fields, so a hallucinated node or edge has no path
by which it could be written.  A structural comparison afterwards catches the
remaining case, where a text field the model returned changed something the
document derives.

Stat chips are deliberately not narratable.  A chip is a number sitting beside
a diagram, so it reads as measured; the comparison can catch an invented id but
not an invented quantity, because the value is exactly the free text the model
was asked for.  Every number on the page therefore stays traceable to an
artifact.

Narration is optional throughout.  No provider, a refusal, a non-JSON answer,
or output that fails validation all leave the projection standing, because a
document with template prose is useful and a missing document is not.

Usage:
    python3 scripts/narrate_change_graph.py .pr-lens/graph.json -o graph.narrated.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arch_utils import change_graph  # noqa: E402
from project_change_graph import BODY_MAX, HEADING_MAX, LABEL_MAX, _clip  # noqa: E402

logger = logging.getLogger(__name__)

#: The pipeline step whose model this reads from `settings/models.yaml`.
PIPELINE_STEP = "change_narration"

#: The closed set of keys the merge will read.  Everything else in the model's
#: answer is ignored, which is what makes "narration cannot change structure" a
#: property of the code rather than a hope about the prompt.
NARRATABLE = frozenset({"title", "summary", "nodes", "walkthrough"})

SUMMARY_MAX = 2000

Complete = Callable[[str, str], str]


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You write the prose for a diagram of a code change.

The diagram already exists. Its lanes, nodes, edges and steps were computed
from the repository's own call graph and from the diff, and they are not yours
to change. You are writing the words a reviewer reads beside them.

Write for someone who knows the codebase but has not seen this change. Say what
the change does and why the shape looks the way it does. Do not report bugs,
risks or style findings; there is nowhere to put them. Do not invent numbers,
file names or symbol names that are not in the material you were given.

Answer with one JSON object and nothing else."""


def build_prompt(document: dict[str, Any]) -> str:
    """Describe the document to narrate, naming every id that may be written."""
    nodes = [
        {
            "id": node["id"],
            "label": node["label"],
            "kind": node["kind"],
            "delta": node["delta"],
            "files": [ref.get("path") for ref in node.get("files", [])],
        }
        for node in document["nodes"][:120]
    ]
    steps = [
        {"id": step["id"], "current_heading": step["heading"]}
        for step in document.get("walkthrough", {}).get("steps", [])
    ]
    stats = document.get("stats", {})

    return "\n".join(
        [
            f"Repository: {document['provenance']['repo'].get('owner')}/"
            f"{document['provenance']['repo'].get('name')}",
            f"Files changed: {stats.get('filesChanged')} "
            f"(+{stats.get('additions')} -{stats.get('deletions')})",
            "",
            "Nodes in the diagram:",
            json.dumps(nodes, indent=1),
            "",
            "Walkthrough steps that need a heading and a one-line body:",
            json.dumps(steps, indent=1),
            "",
            "Return JSON with exactly these optional keys:",
            json.dumps(
                {
                    "title": f"one line, at most {LABEL_MAX} characters",
                    "summary": "a short paragraph answering: what does this change do?",
                    "nodes": {"<node id from above>": "one or two sentences"},
                    "walkthrough": {
                        "<step id from above>": {
                            "heading": f"at most {HEADING_MAX} characters",
                            "body": f"one line, at most {BODY_MAX} characters",
                        }
                    },
                },
                indent=1,
            ),
            "",
            "Use only the ids listed above. Any other key is discarded.",
        ]
    )


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def _read_json_object(text: str) -> dict[str, Any] | None:
    """Read the model's answer, tolerating a fence or a line of preamble."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("```")[1]
        candidate = candidate[4:] if candidate.startswith("json") else candidate
    start, end = candidate.find("{"), candidate.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def merge_narration(
    document: dict[str, Any], narration: dict[str, Any]
) -> dict[str, Any]:
    """Return *document* with its prose replaced where narration supplied it.

    Only the keys in ``NARRATABLE`` are read, and within them only ids the
    document already declares.  Over-long text is clipped rather than dropped:
    a caption one word too long should not cost the whole narration.
    """
    merged = json.loads(json.dumps(document))

    title = narration.get("title")
    if isinstance(title, str) and title.strip():
        merged["title"] = _clip(title.strip(), LABEL_MAX)

    summary = narration.get("summary")
    if isinstance(summary, str) and summary.strip():
        merged["summary"] = _clip(summary.strip(), SUMMARY_MAX)

    node_text = narration.get("nodes")
    if isinstance(node_text, dict):
        for node in merged["nodes"]:
            text = node_text.get(node["id"])
            if isinstance(text, str) and text.strip():
                node["summary"] = _clip(text.strip(), SUMMARY_MAX)

    step_text = narration.get("walkthrough")
    if isinstance(step_text, dict) and merged.get("walkthrough"):
        for step in merged["walkthrough"]["steps"]:
            supplied = step_text.get(step["id"])
            if not isinstance(supplied, dict):
                continue
            heading = supplied.get("heading")
            body = supplied.get("body")
            if isinstance(heading, str) and heading.strip():
                step["heading"] = _clip(heading.strip(), HEADING_MAX)
            if isinstance(body, str) and body.strip():
                step["body"] = _clip(body.strip(), BODY_MAX)

    return merged


def _skeleton(document: dict[str, Any]) -> dict[str, Any]:
    """The document with every narratable string removed.

    What remains is what narration must not have touched: ids, deltas,
    endpoints, orders, counts and every derived number.
    """
    stripped = json.loads(json.dumps(document))
    stripped.pop("title", None)
    stripped.pop("summary", None)
    for node in stripped.get("nodes", []):
        node.pop("summary", None)
    for step in stripped.get("walkthrough", {}).get("steps", []):
        step.pop("heading", None)
        step.pop("body", None)
    return stripped


def first_structural_difference(
    projected: dict[str, Any], narrated: dict[str, Any]
) -> str | None:
    """Return a path into the first non-prose difference, or None."""
    return _walk(_skeleton(projected), _skeleton(narrated), "")


def _walk(left: Any, right: Any, path: str) -> str | None:
    if type(left) is not type(right):
        return path or "<document>"
    if isinstance(left, dict):
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                return f"{path}.{key}".lstrip(".")
            found = _walk(left[key], right[key], f"{path}.{key}".lstrip("."))
            if found:
                return found
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return f"{path}[]"
        for index, (a, b) in enumerate(zip(left, right, strict=True)):
            found = _walk(a, b, f"{path}[{index}]")
            if found:
                return found
        return None
    return None if left == right else path or "<document>"


def narrate(document: dict[str, Any], complete: Complete) -> dict[str, Any]:
    """Return the narrated document, or the projection when narration fails.

    Every failure mode lands in the same place on purpose.  Narration is an
    improvement to a document that is already complete, so nothing it can do
    should be able to cost the reviewer the diagram.
    """
    try:
        answer = complete(SYSTEM_PROMPT, build_prompt(document))
    except Exception as error:  # noqa: BLE001 - any provider failure is the same answer
        logger.warning("narration unavailable (%s); keeping template prose", error)
        return document

    narration = _read_json_object(answer or "")
    if narration is None:
        logger.warning("narration was not a JSON object; keeping template prose")
        return document

    ignored = sorted(set(narration) - NARRATABLE)
    if ignored:
        logger.info("ignored non-prose keys from narration: %s", ", ".join(ignored))

    merged = merge_narration(document, narration)

    difference = first_structural_difference(document, merged)
    if difference is not None:
        logger.warning(
            "narration changed %s, which is not prose; keeping template prose",
            difference,
        )
        return document

    errors = change_graph.validation_errors(merged)
    if errors:
        logger.warning(
            "narrated document does not validate (%s); keeping template prose",
            errors[0],
        )
        return document

    return merged


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


DEFAULT_MODEL = "claude-haiku-4-5"


def resolve_model(repo: Path, override: str | None = None) -> str:
    """Choose the narration model without going through the product's enum.

    `ModelStep` is a closed enum over pipeline steps, and narration is
    developer tooling rather than a pipeline step, so adding a member there
    would make product code carry a dependency on this skill.  The step is
    declared as data in `settings/models.yaml` instead and read from here,
    which also keeps the skill portable to a repository that has no router.

    Precedence matches the router's own: environment, then the YAML default.
    """
    import os  # noqa: PLC0415

    if override:
        return override
    from_env = os.environ.get("MODEL_CHANGE_NARRATION")
    if from_env:
        return from_env

    settings = repo / "settings" / "models.yaml"
    if settings.exists():
        import yaml  # noqa: PLC0415

        loaded = yaml.safe_load(settings.read_text()) or {}
        chosen = (loaded.get("default_models") or {}).get(PIPELINE_STEP)
        if chosen:
            return str(chosen)
    return DEFAULT_MODEL


def _router_complete(repo: Path, model: str | None) -> Complete:
    """Bind this repository's model router, if it is importable.

    Imported lazily so the skill still runs where there is no router at all:
    narration is the only part of this pipeline that needs one, and every way
    it can fail leaves the projection standing.
    """

    def complete(system: str, user: str) -> str:
        from src.config.models import get_model_config  # noqa: PLC0415
        from src.services.llm_router import LLMRouter  # noqa: PLC0415

        config = get_model_config()
        response = LLMRouter(config).generate_sync(
            model=resolve_model(repo, model),
            system_prompt=system,
            user_prompt=user,
            max_tokens=4096,
            temperature=0.3,
        )
        return response.content

    return complete


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="narrate_change_graph",
        description="Fill a change document's prose through the model router.",
    )
    parser.add_argument("document", help="Projected change document")
    parser.add_argument("-o", "--out", help="Where to write the narrated document")
    parser.add_argument("--model", help="Override the model for this run")
    parser.add_argument("--repo", default=".", help="Repository root (default: .)")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    args = build_parser().parse_args(argv)

    source = Path(args.document)
    document = json.loads(source.read_text())
    narrated = narrate(document, _router_complete(Path(args.repo).resolve(), args.model))

    out = Path(args.out) if args.out else source.with_name("graph.narrated.json")
    written = change_graph.write_document(out, narrated)
    logger.info(
        "✓ %s — %s", written, "narrated" if narrated is not document else "template prose"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
