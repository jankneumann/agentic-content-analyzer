"""Job-only execution fencing for ingestion adapters."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.queue.execution_claim import (
    ClaimCancelled,
    ClaimSuperseded,
    ExecutionClaim,
    bind_execution_claim,
    check_execution_claim,
    guard_execution_claim,
)


def _job(session: Session, *, cancelled: bool = False) -> int:
    return int(
        session.scalar(
            text(
                "INSERT INTO pgqueuer_jobs "
                "(entrypoint, payload, status, claim_generation, claim_protocol_version) "
                "VALUES ('ingestion.execute', CAST(:payload AS jsonb), 'in_progress', 2, 2) "
                "RETURNING id"
            ),
            {"payload": json.dumps({"cancel_requested": cancelled})},
        )
    )


def test_non_locking_checkpoint_and_locking_guard_accept_current_generation(
    db_session: Session,
) -> None:
    job_id = _job(db_session)
    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=2)):
        assert check_execution_claim(db_session).job_id == job_id
        assert guard_execution_claim(db_session).claim_generation == 2


@pytest.mark.parametrize("locking", [False, True])
def test_job_checkpoint_rejects_cancellation(db_session: Session, locking: bool) -> None:
    job_id = _job(db_session, cancelled=True)
    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=2)):
        with pytest.raises(ClaimCancelled):
            (guard_execution_claim if locking else check_execution_claim)(db_session)


def test_job_checkpoint_rejects_missing_and_mismatched_claims(db_session: Session) -> None:
    with pytest.raises(ClaimSuperseded):
        check_execution_claim(db_session)

    job_id = _job(db_session)
    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        with pytest.raises(ClaimSuperseded):
            guard_execution_claim(db_session)
