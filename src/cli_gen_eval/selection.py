"""Select which scenarios a run evaluates, because the runner cannot.

The pinned runner accepts `--categories` and does nothing with it. `args.categories`
reaches `GenEvalConfig.categories` and is never read again: the only path into the
generator's filter is `feedback.suggested_focus`, which is `None` on the first iteration,
and `max_iterations` defaults to 1. Verified rather than inferred — `--categories
discovery` against this suite evaluates all sixteen scenarios across all three
categories.

That is not a cosmetic gap. Three separate requirements in this change assume selective
execution, and one of them is a safety property: mutating categories must not run unless
explicitly asked for. Had Phase 5's `workflow-submission` scenarios been checked in under
the assumption that `--categories` filters, every `make gen-eval` would have submitted
durable work against whatever database was configured. The gate's existing refusal only
inspects the categories *requested*; it cannot stop scenarios that are simply present on
disk.

So selection happens here, before the runner is invoked. The runner reads what a
descriptor's `scenario_dirs` points at, so the gate resolves the selection itself, copies
the chosen templates into a scratch directory, and hands the runner a descriptor pointing
there. Everything else in the descriptor — notably the declared command list that forms
the coverage denominator — is carried over unchanged.

Selecting by copying rather than by pointing at the checked-in per-category directories is
deliberate: predicates that are not directory-shaped need it. `--offline` selects on a
tag, and `validation/` is deliberately mixed — two of its scenarios need a backend and two
do not.

Raised upstream as UPSTREAM.md UP-6. If the filter starts working, this module becomes a
thin argument-builder rather than a materializer; nothing else here changes.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .suite import iter_templates

SELECTION_DIRNAME = ".selection"
SELECTION_DESCRIPTOR_NAME = "selection-descriptor.yaml"


@dataclass(frozen=True)
class Selected:
    """One template chosen for a run, with the file it came from."""

    source: Path
    template: dict[str, Any]

    @property
    def scenario_id(self) -> str:
        return str(self.template.get("id", "<unknown>"))

    @property
    def category(self) -> str:
        return str(self.template.get("category", "<unknown>"))

    @property
    def tags(self) -> set[str]:
        return set(self.template.get("tags") or [])


def select(
    scenario_root: Path,
    categories: set[str] | None = None,
    require_tags: set[str] | None = None,
) -> list[Selected]:
    """Choose templates by category and, optionally, by required tags.

    `require_tags` is a conjunction: a template must carry every named tag. That is the
    conservative reading — a selection meant to exclude something must not admit it
    because one of several tags happened to match.
    """
    chosen: list[Selected] = []
    for path in sorted(p for p in scenario_root.rglob("*.yaml") if p.is_file()):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for template in iter_templates(document):
            if not isinstance(template, dict):
                continue
            candidate = Selected(source=path, template=template)
            if categories is not None and candidate.category not in categories:
                continue
            if require_tags and not require_tags.issubset(candidate.tags):
                continue
            chosen.append(candidate)
    return chosen


def materialize(
    selected: list[Selected],
    descriptor: dict[str, Any],
    work_dir: Path,
) -> Path:
    """Write the selection and a descriptor pointing at it. Returns the descriptor path.

    The scratch directory is rebuilt from empty every run. Leaving a previous selection
    behind would silently widen the next one, which is the failure this module exists to
    prevent.
    """
    selection_dir = work_dir / SELECTION_DIRNAME
    if selection_dir.exists():
        shutil.rmtree(selection_dir)
    selection_dir.mkdir(parents=True)

    grouped: dict[Path, list[dict[str, Any]]] = {}
    for item in selected:
        grouped.setdefault(item.source, []).append(item.template)

    for source, templates in sorted(grouped.items()):
        # Flatten the source tree into unique names so scenarios/plumbing/x.yaml and
        # scenarios/discovery/x.yaml cannot collide.
        relative = source.relative_to(source.parents[1])
        destination = selection_dir / str(relative).replace("/", "__")
        payload: Any = templates if len(templates) > 1 else templates[0]
        destination.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

    selection_descriptor = dict(descriptor)
    selection_descriptor["scenario_dirs"] = [SELECTION_DIRNAME]
    descriptor_path = work_dir / SELECTION_DESCRIPTOR_NAME
    descriptor_path.write_text(
        yaml.safe_dump(selection_descriptor, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return descriptor_path
