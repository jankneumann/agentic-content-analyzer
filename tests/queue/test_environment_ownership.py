"""Claim-time environment fencing for mutation workers."""

from __future__ import annotations

import hashlib
import json
import os
import socket
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from src.queue.execution_claim import (
    ClaimSuperseded,
    ExecutionClaim,
    bind_execution_claim,
    guard_execution_claim,
)
from src.services.environment_ownership import database_authority_fingerprint

PRIMARY_ENDPOINT = "postgresql://owner@shared-queue:5432/newsletters"
_PRIMARY_URL = make_url(PRIMARY_ENDPOINT)
AUTHORITY = hashlib.sha256(
    f"{_PRIMARY_URL.host}:{_PRIMARY_URL.port or 5432}/{_PRIMARY_URL.database}".encode()
).hexdigest()


def _postgres_available() -> bool:
    if os.getenv("TEST_DATABASE_URL"):
        return True
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=0.1):
            return True
    except OSError:
        return False


requires_live_postgres = pytest.mark.skipif(
    not _postgres_available(), reason="live PostgreSQL acceptance unavailable"
)


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


def _ownership(session: Session, *, active_environment: str, epoch: int) -> str:
    authority = database_authority_fingerprint(session)
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
            "authority": authority,
            "environment": active_environment,
            "epoch": epoch,
            "updated_at": datetime.now(UTC),
        },
    )
    return authority


def _claim(
    job_id: int,
    *,
    environment: str = "gx10",
    authority: str = AUTHORITY,
    epoch: int = 9,
) -> ExecutionClaim:
    return ExecutionClaim(
        job_id=job_id,
        claim_generation=2,
        environment=environment,
        authority_fingerprint=authority,
        ownership_epoch=epoch,
    )


@requires_live_postgres
def test_claim_time_fence_accepts_only_the_single_recorded_owner(db_session: Session) -> None:
    job_id = _job(db_session)
    authority = _ownership(db_session, active_environment="gx10", epoch=9)

    with bind_execution_claim(_claim(job_id, authority=authority)):
        assert guard_execution_claim(db_session).job_id == job_id


@requires_live_postgres
def test_claim_time_fence_rejects_passive_environment(db_session: Session) -> None:
    job_id = _job(db_session)
    authority = _ownership(db_session, active_environment="railway", epoch=9)

    with bind_execution_claim(_claim(job_id, authority=authority)):
        with pytest.raises(ClaimSuperseded, match="environment.passive"):
            guard_execution_claim(db_session)


@requires_live_postgres
def test_claim_time_fence_rejects_epoch_changed_after_claim(db_session: Session) -> None:
    job_id = _job(db_session)
    authority = _ownership(db_session, active_environment="gx10", epoch=10)

    with bind_execution_claim(_claim(job_id, authority=authority, epoch=9)):
        with pytest.raises(ClaimSuperseded, match="epoch.stale"):
            guard_execution_claim(db_session)


@requires_live_postgres
def test_partial_ownership_identity_never_falls_back_to_legacy_claim(
    db_session: Session,
) -> None:
    job_id = _job(db_session)
    with bind_execution_claim(
        ExecutionClaim(job_id=job_id, claim_generation=2, environment="gx10")
    ):
        with pytest.raises(ClaimSuperseded, match="identity.incomplete"):
            guard_execution_claim(db_session)


class _QueueResult:
    def __init__(self, *, owner: dict[str, object], job: dict[str, object]) -> None:
        self.owner = owner
        self.job = job

    def mappings(self) -> _QueueResult:
        return self

    def one_or_none(self) -> dict[str, object]:
        return self.owner

    def first(self) -> dict[str, object]:
        return self.job


class _QueueSession:
    def __init__(self, *, active_environment: str = "gx10", epoch: int = 9) -> None:
        self.owner = {
            "authority_fingerprint": AUTHORITY,
            "active_environment": active_environment,
            "epoch": epoch,
        }
        self.job = {
            "status": "in_progress",
            "claim_generation": 2,
            "claim_protocol_version": 2,
            "cancel_requested": False,
        }
        self.statements: list[str] = []

    def execute(self, statement: object, *_args: object, **_kwargs: object) -> _QueueResult:
        self.statements.append(str(statement))
        return _QueueResult(owner=self.owner, job=self.job)

    def get_bind(self) -> SimpleNamespace:
        return SimpleNamespace(url=make_url(PRIMARY_ENDPOINT))


def test_unit_claim_fence_accepts_owner_and_rejects_passive_stale_or_partial(monkeypatch) -> None:
    active = _QueueSession()
    with bind_execution_claim(_claim(42)):
        assert guard_execution_claim(active).job_id == 42  # type: ignore[arg-type]
    assert "FOR SHARE" in active.statements[0]

    passive = _QueueSession(active_environment="railway")
    with bind_execution_claim(_claim(42)):
        with pytest.raises(ClaimSuperseded, match="environment.passive"):
            guard_execution_claim(passive)  # type: ignore[arg-type]

    stale = _QueueSession(epoch=10)
    with bind_execution_claim(_claim(42, epoch=9)):
        with pytest.raises(ClaimSuperseded, match="epoch.stale"):
            guard_execution_claim(stale)  # type: ignore[arg-type]

    with bind_execution_claim(ExecutionClaim(job_id=42, claim_generation=2, environment="gx10")):
        with pytest.raises(ClaimSuperseded, match="identity.incomplete"):
            guard_execution_claim(_QueueSession())  # type: ignore[arg-type]

    monkeypatch.setattr(
        "src.queue.execution_claim.get_settings",
        lambda: SimpleNamespace(gx10_runtime_enabled=True),
    )
    with bind_execution_claim(ExecutionClaim(job_id=42, claim_generation=2)):
        with pytest.raises(ClaimSuperseded, match="identity.incomplete"):
            guard_execution_claim(_QueueSession())  # type: ignore[arg-type]
