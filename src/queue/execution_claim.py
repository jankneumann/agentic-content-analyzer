"""Task-local ownership fence for the queue claim currently being executed."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select, text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from src.models.content import Content, ContentStatus
from src.queue.content_execution_lock import lock_content_transaction


class ClaimRejected(RuntimeError):  # noqa: N818 - closed typed claim outcome
    """A domain mutation was rejected by its durable execution fence."""


class ClaimCancelled(ClaimRejected):
    """The current generation is valid but cancellation now has precedence."""


class ClaimSuperseded(ClaimRejected):
    """The operation or Content ownership token no longer matches this claim."""


class ContentExecutionPhase(StrEnum):
    """Closed Content phases supported by guarded operation writers."""

    PARSING = "parsing"
    PROCESSING = "processing"


@dataclass(frozen=True, slots=True)
class ExecutionClaim:
    """Identity of one current-protocol queue claim."""

    job_id: int
    claim_generation: int
    claim_protocol_version: int = 2


_CURRENT_EXECUTION_CLAIM: ContextVar[ExecutionClaim | None] = ContextVar(
    "current_execution_claim",
    default=None,
)


def current_execution_claim() -> ExecutionClaim | None:
    """Return the task-local claim, if execution is inside a worker claim."""

    return _CURRENT_EXECUTION_CLAIM.get()


def claim_generation_for(job_id: int) -> int | None:
    """Return the generation only when the current claim owns ``job_id``."""

    claim = current_execution_claim()
    if claim is None or claim.job_id != job_id:
        return None
    return claim.claim_generation


@contextmanager
def bind_execution_claim(claim: ExecutionClaim) -> Iterator[None]:
    """Bind one claim for handler execution and restore prior task context."""

    token = _CURRENT_EXECUTION_CLAIM.set(claim)
    try:
        yield
    finally:
        _CURRENT_EXECUTION_CLAIM.reset(token)


def _require_current_claim() -> ExecutionClaim:
    claim = current_execution_claim()
    if claim is None:
        raise ClaimSuperseded("No execution claim is bound")
    return claim


def _validate_job_row(row: RowMapping | None, claim: ExecutionClaim) -> None:
    if (
        row is None
        or row["status"] != "in_progress"
        or int(row["claim_generation"]) != claim.claim_generation
        or claim.claim_protocol_version != 2
        or int(row["claim_protocol_version"]) != 2
    ):
        raise ClaimSuperseded(
            f"Operation {claim.job_id} generation {claim.claim_generation} is no longer current"
        )
    if bool(row["cancel_requested"]):
        raise ClaimCancelled(f"Operation {claim.job_id} was cancelled")


def _job_row(session: Session, claim: ExecutionClaim, *, locking: bool) -> RowMapping | None:
    statement = (
        text(
            """
            SELECT status, claim_generation, claim_protocol_version,
                   COALESCE((payload->>'cancel_requested')::boolean, FALSE)
                     AS cancel_requested
            FROM pgqueuer_jobs
            WHERE id = :job_id
            FOR UPDATE
            """
        )
        if locking
        else text(
            """
            SELECT status, claim_generation, claim_protocol_version,
                   COALESCE((payload->>'cancel_requested')::boolean, FALSE)
                     AS cancel_requested
            FROM pgqueuer_jobs
            WHERE id = :job_id
            """
        )
    )
    return (
        session.execute(
            statement,
            {"job_id": claim.job_id},
        )
        .mappings()
        .first()
    )


def check_execution_claim(session: Session) -> ExecutionClaim:
    """Fail closed at a non-locking cancellation and generation checkpoint."""

    claim = _require_current_claim()
    _validate_job_row(_job_row(session, claim, locking=False), claim)
    return claim


def guard_execution_claim(session: Session) -> ExecutionClaim:
    """Lock and validate the job before acquiring domain persistence locks."""

    claim = _require_current_claim()
    _validate_job_row(_job_row(session, claim, locking=True), claim)
    return claim


def _lock_and_validate_job(session: Session, claim: ExecutionClaim) -> None:
    _validate_job_row(_job_row(session, claim, locking=True), claim)


def _lock_content(session: Session, content_id: int, claim: ExecutionClaim) -> Content:
    with session.no_autoflush:
        lock_content_transaction(session, content_id)
        _lock_and_validate_job(session, claim)
        content = session.execute(
            select(Content)
            .where(Content.id == content_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
    if content is None:
        raise ClaimSuperseded(f"Content {content_id} no longer exists")
    return content


def acquire_content_execution(
    session: Session,
    content_id: int,
    phase: ContentExecutionPhase,
    *,
    allow_interrupted: bool = False,
) -> Content:
    """Acquire initial or same-operation renewed ownership for one phase."""

    claim = _require_current_claim()
    content = _lock_content(session, content_id, claim)
    predecessor = (
        ContentStatus.PENDING if phase is ContentExecutionPhase.PARSING else ContentStatus.PARSED
    )
    phase_status = (
        ContentStatus.PARSING
        if phase is ContentExecutionPhase.PARSING
        else ContentStatus.PROCESSING
    )
    owner_is_empty = all(
        value is None
        for value in (
            content.status_operation_id,
            content.status_claim_generation,
            content.status_operation_phase,
            content.status_owner_version,
        )
    )
    initial = content.status is predecessor and owner_is_empty
    renewal = (
        (
            content.status is ContentStatus.FAILED
            or (allow_interrupted and content.status is phase_status)
        )
        and content.status_operation_id == claim.job_id
        and content.status_operation_phase == phase.value
        and content.status_claim_generation is not None
        and content.status_claim_generation < claim.claim_generation
        and content.status_owner_version is not None
    )
    if not (initial or renewal):
        raise ClaimSuperseded(
            f"Content {content_id} cannot acquire {phase.value} ownership for "
            f"operation {claim.job_id} generation {claim.claim_generation}"
        )

    content.status = phase_status
    content.status_operation_id = claim.job_id
    content.status_claim_generation = claim.claim_generation
    content.status_operation_phase = phase.value
    content.status_owner_version = (content.status_owner_version or 0) + 1
    return content


def guard_content_execution(
    session: Session,
    content_id: int,
    phase: ContentExecutionPhase,
) -> Content:
    """Lock and return Content only while both durable ownership tokens match."""

    claim = _require_current_claim()
    content = _lock_content(session, content_id, claim)
    if (
        content.status_operation_id != claim.job_id
        or content.status_claim_generation != claim.claim_generation
        or content.status_operation_phase != phase.value
        or content.status_owner_version is None
    ):
        raise ClaimSuperseded(
            f"Content {content_id} is not owned by operation {claim.job_id} "
            f"generation {claim.claim_generation}"
        )
    return content
