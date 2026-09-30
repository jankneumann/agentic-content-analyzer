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
parallel run-state store. It also carries each source's diagnostic codes from the
durable result, so a credential-gated source that failed closed is recorded as
``session_expired`` / ``credentials_missing`` with the command that refreshes it,
not as an anonymous adapter failure.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from src.ingestion.credential_failures import CREDENTIAL_FAILURE_CODES, refresh_command_for
from src.ingestion.result_sanitizer import SAFE_INGESTION_DIAGNOSTIC_CODES

#: Statuses that mean the durable operation never reached a terminal transition.
_NONTERMINAL_STATUSES = frozenset({"queued", "in_progress"})


class FailureClass(StrEnum):
    """The layer a real-ingestion source outcome is attributed to."""

    SUCCESS = "success"
    ADAPTER = "adapter"
    QUEUE = "queue"
    PERSISTENCE = "persistence"
    SKIPPED = "skipped"


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


#: Substrings that identify a database *write* failure rather than an upstream
#: adapter error. ``_ingestion_diagnostic`` embeds both ``type(exc).__name__`` and
#: ``str(exc)``, so a SQLAlchemy ``IntegrityError`` surfaces here as its type name
#: plus the Postgres constraint message — neither of which contains the words
#: "persist"/"database write" that the original check looked for. These signatures
#: are DB-write specific, so they cannot be produced by an HTTP/parse adapter error.
_PERSISTENCE_SIGNATURES: tuple[str, ...] = (
    "persist",
    "database write",
    "integrityerror",
    "dataerror",
    "duplicate key value",
    "violates unique constraint",
    "violates foreign key constraint",
    "violates not-null constraint",
    "violates check constraint",
    "violates exclusion constraint",
    "deadlock detected",
    "could not serialize access",
)


def _is_persistence_problem(detail: str | None) -> bool:
    if not detail:
        return False
    lowered = detail.lower()
    return any(signature in lowered for signature in _PERSISTENCE_SIGNATURES)


@dataclass(frozen=True)
class SourceEvidence:
    """One source's classified outcome, ready to render into CI evidence."""

    key: str
    operation_id: str
    failure_class: FailureClass
    claimed: int
    delta: int
    detail: str | None = None
    #: Closed diagnostic codes from the durable result, in first-seen order.
    codes: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.failure_class is FailureClass.SUCCESS


def result_diagnostic_codes(result: Mapping[str, Any] | None) -> tuple[str, ...]:
    """Read the closed diagnostic codes a durable ingestion result records.

    Only codes in the public vocabulary are kept: the artifact is uploaded from
    CI, so nothing but a fixed literal from a result may reach it.
    """

    if not isinstance(result, Mapping):
        return ()
    diagnostics: list[object] = [*_list(result.get("errors")), *_list(result.get("warnings"))]
    for outcome in _list(result.get("source_outcomes")):
        if isinstance(outcome, Mapping):
            diagnostics += [*_list(outcome.get("errors")), *_list(outcome.get("warnings"))]
    codes = (item.get("code") for item in diagnostics if isinstance(item, Mapping))
    return tuple(
        dict.fromkeys(
            code
            for code in codes
            if isinstance(code, str) and code in SAFE_INGESTION_DIAGNOSTIC_CODES
        )
    )


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _render_codes(item: SourceEvidence) -> str:
    rendered = ", ".join(item.codes)
    command = refresh_command_for(item.key)
    if command and not CREDENTIAL_FAILURE_CODES.isdisjoint(item.codes):
        rendered += f" (refresh: `{command}`)"
    return rendered


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
        f"persistence: {counts['persistence']} | "
        f"skipped: {counts['skipped']}"
    )
    lines = ["## Real-ingestion failure-class evidence", "", header]

    failures = [item for item in evidence if not item.succeeded]
    if failures:
        lines += [
            "",
            "| source | operation | class | claimed | delta | codes | detail |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for item in failures:
            detail = (item.detail or "").replace("|", "\\|")
            lines.append(
                f"| {item.key} | {item.operation_id} | {item.failure_class.value} "
                f"| {item.claimed} | {item.delta} | {_render_codes(item)} | {detail} |"
            )
    else:
        lines += ["", "All sources persisted their claimed content. No failures."]

    return "\n".join(lines)
