"""Task-local ownership fence for the queue claim currently being executed."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


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
