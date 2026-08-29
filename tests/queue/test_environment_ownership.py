"""Claim-time environment fencing for mutation workers."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.queue.execution_claim import (
    ClaimSuperseded,
    ExecutionClaim,
    bind_execution_claim,
    guard_execution_claim,
)

AUTHORITY = "c" * 64


def _job(session: Session) -> int:
    return int(
        session.scalar(
            text(
                "INSERT INTO pgqueuer_jobs "
                "(entrypoint, payload, status, claim_generation, claim_protocol_version) "
                "VALUES ('ingestion.execute', CAST(:payload AS jsonb), 'in_progress', 2, 2) "
                "RETURNING id"
            ),
            {"payload": json.dumps({"cancel_requested": False})},
        )
    )


def _ownership(session: Session, *, active_environment: str, epoch: int) -> None:
    session.execute(
        text(
            """
            INSERT INTO environment_ownership (
                singleton, authority_fingerprint, active_environment,
                epoch, updated_at, updated_by
            ) VALUES (TRUE, :authority, :environment, :epoch, :updated_at, 'test.claim')
            """
        ),
        {
            "authority": AUTHORITY,
            "environment": active_environment,
            "epoch": epoch,
            "updated_at": datetime.now(UTC),
        },
    )


def _claim(job_id: int, *, environment: str = "gx10", epoch: int = 9) -> ExecutionClaim:
    return ExecutionClaim(
        job_id=job_id,
        claim_generation=2,
        environment=environment,
        authority_fingerprint=AUTHORITY,
        ownership_epoch=epoch,
    )


def test_claim_time_fence_accepts_only_the_single_recorded_owner(db_session: Session) -> None:
    job_id = _job(db_session)
    _ownership(db_session, active_environment="gx10", epoch=9)

    with bind_execution_claim(_claim(job_id)):
        assert guard_execution_claim(db_session).job_id == job_id


def test_claim_time_fence_rejects_passive_environment(db_session: Session) -> None:
    job_id = _job(db_session)
    _ownership(db_session, active_environment="railway", epoch=9)

    with bind_execution_claim(_claim(job_id)):
        with pytest.raises(ClaimSuperseded, match="environment.passive"):
            guard_execution_claim(db_session)


def test_claim_time_fence_rejects_epoch_changed_after_claim(db_session: Session) -> None:
    job_id = _job(db_session)
    _ownership(db_session, active_environment="gx10", epoch=10)

    with bind_execution_claim(_claim(job_id, epoch=9)):
        with pytest.raises(ClaimSuperseded, match="epoch.stale"):
            guard_execution_claim(db_session)


def test_partial_ownership_identity_never_falls_back_to_legacy_claim(
    db_session: Session,
) -> None:
    job_id = _job(db_session)
    with bind_execution_claim(
        ExecutionClaim(job_id=job_id, claim_generation=2, environment="gx10")
    ):
        with pytest.raises(ClaimSuperseded, match="identity.incomplete"):
            guard_execution_claim(db_session)

