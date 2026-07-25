"""Failure-class evidence for the real-ingestion CI tiers (RI-05 / design D2).

A single pure function classifies a source's outcome by reading its durable
operation and result records — no new run-state representation is introduced.
The three failure layers, per the durable operation/result problem taxonomy:

- **adapter** — the operation terminated with a source/adapter-level problem
  (upstream HTTP or parse error) and wrote no ``Content`` rows.
- **queue** — the operation never reached a terminal transition (still queued /
  in progress), or failed before the adapter ran (dispatch/queue-layer failure).
- **persistence** — the operation claims success but the expected ``Content``
  rows are absent, or a database write error is recorded.

``render_failure_summary`` turns a batch of classifications into the CI evidence
artifact (a rendered summary), which is a *view* of these records rather than a
parallel run-state store.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

#: Statuses that mean the durable operation never reached a terminal transition.
_NONTERMINAL_STATUSES = frozenset({"queued", "in_progress"})


class FailureClass(StrEnum):
    """The layer a real-ingestion source outcome is attributed to."""

    SUCCESS = "success"
    ADAPTER = "adapter"
    QUEUE = "queue"
    PERSISTENCE = "persistence"


def classify_source_outcome(
    status: str,
    claimed_content_ids: Sequence[int],
    content_delta: int,
    problem_detail: str | None = None,
) -> FailureClass:
    """Attribute one source outcome to exactly one layer from its durable record.

    Args:
        status: The terminal operation status (``completed`` / ``failed`` /
            ``cancelled``) or a non-terminal status (``queued`` / ``in_progress``).
        claimed_content_ids: The content IDs the durable result claims to have
            persisted.
        content_delta: The number of ``Content`` rows actually committed.
        problem_detail: The operation's failure diagnostic, if any.
    """

    if status in _NONTERMINAL_STATUSES:
        return FailureClass.QUEUE

    if status == "completed":
        # A completed operation is trustworthy only if the DB backs its claim.
        if len(claimed_content_ids) == content_delta:
            return FailureClass.SUCCESS
        return FailureClass.PERSISTENCE

    # Terminal failure (failed / cancelled): read the recorded diagnostic.
    # Persistence signatures are checked first because a DB-write diagnostic also
    # carries the "Ingestion '<src>'" adapter prefix.
    if _is_persistence_problem(problem_detail):
        return FailureClass.PERSISTENCE
    if _is_adapter_problem(problem_detail):
        return FailureClass.ADAPTER
    return FailureClass.QUEUE


def _is_adapter_problem(detail: str | None) -> bool:
    """Match the ``_ingestion_diagnostic`` format from the ingestion handler."""

    return bool(detail) and detail.startswith("Ingestion '")  # type: ignore[union-attr]


def _is_persistence_problem(detail: str | None) -> bool:
    if not detail:
        return False
    lowered = detail.lower()
    return "persist" in lowered or "database write" in lowered


@dataclass(frozen=True)
class SourceEvidence:
    """One source's classified outcome, ready to render into CI evidence."""

    key: str
    operation_id: str
    failure_class: FailureClass
    claimed: int
    delta: int
    detail: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.failure_class is FailureClass.SUCCESS


def summarize_counts(evidence: Sequence[SourceEvidence]) -> dict[str, int]:
    """Count sources per class (every failure layer represented, even at zero)."""

    counts = {member.value: 0 for member in FailureClass}
    for item in evidence:
        counts[item.failure_class.value] += 1
    return counts


def render_failure_summary(evidence: Sequence[SourceEvidence]) -> str:
    """Render a Markdown CI summary mapping each source to one failure layer."""

    counts = summarize_counts(evidence)
    header = (
        f"Sources: {len(evidence)} | "
        f"success: {counts['success']} | "
        f"adapter: {counts['adapter']} | "
        f"queue: {counts['queue']} | "
        f"persistence: {counts['persistence']}"
    )
    lines = ["## Real-ingestion failure-class evidence", "", header]

    failures = [item for item in evidence if not item.succeeded]
    if failures:
        lines += [
            "",
            "| source | operation | class | claimed | delta | detail |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for item in failures:
            detail = (item.detail or "").replace("|", "\\|")
            lines.append(
                f"| {item.key} | {item.operation_id} | {item.failure_class.value} "
                f"| {item.claimed} | {item.delta} | {detail} |"
            )
    else:
        lines += ["", "All sources persisted their claimed content. No failures."]

    return "\n".join(lines)
