"""Environment-ownership fence contracts for GX-10/Railway coexistence."""

from __future__ import annotations

import os
import socket
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.services.environment_ownership import (
    EnvironmentOwnershipUnavailable,
    OwnershipFenceRejected,
    OwnershipIdentity,
    evaluate_environment_ownership,
    require_mutation_ownership,
)
from src.tasks.scheduler import require_scheduler_ownership

AUTHORITY = "a" * 64


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
OTHER_AUTHORITY = "b" * 64


def _ownership(
    session: Session,
    *,
    authority: str = AUTHORITY,
    active_environment: str = "railway",
    epoch: int = 7,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO environment_ownership (
                singleton, authority_fingerprint, active_environment,
                epoch, updated_at, updated_by
            ) VALUES (TRUE, :authority, :active_environment, :epoch, :updated_at, :updated_by)
            """
        ),
        {
            "authority": authority,
            "active_environment": active_environment,
            "epoch": epoch,
            "updated_at": datetime.now(UTC),
            "updated_by": "test.environment-ownership",
        },
    )


@requires_live_postgres
def test_gx10_starts_passive_against_the_shared_railway_authority(
    db_session: Session,
) -> None:
    _ownership(db_session)

    status = evaluate_environment_ownership(
        db_session,
        OwnershipIdentity("gx10", AUTHORITY, expected_epoch=7),
    )

    assert status.mode == "passive"
    assert status.active_environment == "railway"
    assert status.authority_matches is True
    assert status.epoch == "7"
    assert status.passive_reasons == ["environment.passive"]
    assert status.authority_fingerprint_prefix == AUTHORITY[:12]
    assert AUTHORITY not in status.model_dump_json()


@requires_live_postgres
def test_mismatched_shared_authority_refuses_independent_database_activation(
    db_session: Session,
) -> None:
    _ownership(db_session)

    status = evaluate_environment_ownership(
        db_session,
        OwnershipIdentity("gx10", OTHER_AUTHORITY, expected_epoch=7),
        dry_run_target="gx10",
    )

    assert status.mode == "conflict"
    assert status.authority_matches is False
    assert status.passive_reasons == ["authority.mismatch", "environment.passive"]
    assert status.dry_run is not None
    assert status.dry_run.allowed is False
    assert status.dry_run.next_epoch is None
    assert status.dry_run.checks == ["shared_authority.mismatch"]


@requires_live_postgres
def test_cutover_and_rollback_dry_run_freezes_the_required_order(
    db_session: Session,
) -> None:
    _ownership(db_session)

    status = evaluate_environment_ownership(
        db_session,
        OwnershipIdentity("gx10", AUTHORITY, expected_epoch=7),
        dry_run_target="gx10",
    )

    assert status.dry_run is not None
    assert status.dry_run.allowed is True
    assert status.dry_run.next_epoch == "8"
    assert status.dry_run.checks == [
        "shared_authority.match",
        "current_owner.fence_first",
        "passive_target.verify_second",
        "target_mutations.enable_last",
    ]


@requires_live_postgres
def test_scheduler_gate_requires_exact_owner_authority_and_epoch(db_session: Session) -> None:
    _ownership(db_session, active_environment="gx10", epoch=8)
    current = OwnershipIdentity("gx10", AUTHORITY, expected_epoch=8)

    assert require_scheduler_ownership(db_session, current).epoch == 8

    with pytest.raises(OwnershipFenceRejected, match="epoch.stale"):
        require_scheduler_ownership(
            db_session,
            OwnershipIdentity("gx10", AUTHORITY, expected_epoch=7),
        )


def test_network_partition_fails_the_mutation_gate_closed() -> None:
    class PartitionedSession:
        def execute(self, *_args: object, **_kwargs: object) -> None:
            raise OperationalError("SELECT", {}, ConnectionError("partitioned"))

    with pytest.raises(EnvironmentOwnershipUnavailable, match="unavailable"):
        require_mutation_ownership(
            PartitionedSession(),  # type: ignore[arg-type]
            OwnershipIdentity("gx10", AUTHORITY, expected_epoch=7),
        )


class _OwnershipResult:
    def __init__(self, row: dict[str, object]) -> None:
        self._row = row

    def mappings(self) -> _OwnershipResult:
        return self

    def one_or_none(self) -> dict[str, object]:
        return self._row


class _OwnershipSession:
    def __init__(
        self,
        *,
        authority: str = AUTHORITY,
        active_environment: str = "railway",
        epoch: int = 7,
    ) -> None:
        self.row = {
            "authority_fingerprint": authority,
            "active_environment": active_environment,
            "epoch": epoch,
        }
        self.statements: list[str] = []

    def execute(self, statement: object, *_args: object, **_kwargs: object) -> _OwnershipResult:
        self.statements.append(str(statement))
        return _OwnershipResult(self.row)


def test_unit_ownership_policy_covers_passive_conflict_cutover_and_atomic_lock() -> None:
    passive_session = _OwnershipSession()
    passive = evaluate_environment_ownership(
        passive_session,  # type: ignore[arg-type]
        OwnershipIdentity("gx10", AUTHORITY, expected_epoch=7),
    )
    assert passive.mode == "passive"
    assert passive.passive_reasons == ["environment.passive"]
    assert AUTHORITY not in passive.model_dump_json()

    conflict = evaluate_environment_ownership(
        passive_session,  # type: ignore[arg-type]
        OwnershipIdentity("gx10", OTHER_AUTHORITY, expected_epoch=7),
        dry_run_target="gx10",
    )
    assert conflict.mode == "conflict"
    assert conflict.dry_run is not None
    assert conflict.dry_run.checks == ["shared_authority.mismatch"]

    cutover = evaluate_environment_ownership(
        passive_session,  # type: ignore[arg-type]
        OwnershipIdentity("gx10", AUTHORITY, expected_epoch=7),
        dry_run_target="gx10",
    )
    assert cutover.dry_run is not None
    assert cutover.dry_run.next_epoch == "8"
    assert cutover.dry_run.checks == [
        "shared_authority.match",
        "current_owner.fence_first",
        "passive_target.verify_second",
        "target_mutations.enable_last",
    ]

    active_session = _OwnershipSession(active_environment="gx10", epoch=8)
    record = require_scheduler_ownership(
        active_session,  # type: ignore[arg-type]
        OwnershipIdentity("gx10", AUTHORITY, expected_epoch=8),
    )
    assert record.epoch == 8
    assert "FOR SHARE" in active_session.statements[-1]

    with pytest.raises(OwnershipFenceRejected, match="epoch.stale"):
        require_scheduler_ownership(
            active_session,  # type: ignore[arg-type]
            OwnershipIdentity("gx10", AUTHORITY, expected_epoch=7),
        )
