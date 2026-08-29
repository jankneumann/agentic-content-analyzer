"""Environment-ownership fence contracts for GX-10/Railway coexistence."""

from __future__ import annotations

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

