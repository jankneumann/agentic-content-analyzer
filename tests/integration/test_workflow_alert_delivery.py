"""PostgreSQL integration coverage for leased workflow-alert delivery."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.orm import sessionmaker

from src.contracts.workflow_alert_models import WorkflowAlertEnvelopeV1
from src.models.workflow_alert import (
    WorkflowAlertDelivery,
    WorkflowAlertDeliveryStatus,
    WorkflowTerminalClassificationStatus,
    WorkflowTerminalEvent,
)
from src.services.workflow_alert_delivery import (
    DeliveryRetryPolicy,
    claim_due_deliveries,
    cleanup_terminal_deliveries,
    ensure_delivery,
    mark_delivery_succeeded,
    record_delivery_failure,
)

pytestmark = pytest.mark.integration


def _policy(*, max_attempts: int = 5) -> DeliveryRetryPolicy:
    return DeliveryRetryPolicy(
        max_attempts=max_attempts,
        base_backoff_seconds=10,
        max_backoff_seconds=60,
        max_retry_after_seconds=30,
        max_age_seconds=604_800,
    )


def _valid_envelope(
    *,
    event_id,
    operation_id: int,
    generation: int,
    now: datetime,
) -> dict:
    return WorkflowAlertEnvelopeV1(
        event_id=event_id,
        event_key=f"operation:{operation_id}:claim:{generation}:status:failed",
        occurred_at=now,
        severity="error",
        outcome="failed",
        source_kind="operation",
        workflow_type="ingestion.execute",
        operation_id=str(operation_id),
        attempt=generation + 1,
        diagnostic_url=f"https://ops.example.com/api/v1/operations/{operation_id}",
        resource_refs=[],
        source_keys=[],
        counts={"items_failed": 1},
        codes=["operation_failed"],
    ).model_dump(mode="json")


def _insert_ready_delivery(
    session,
    *,
    now: datetime,
    envelope: dict | None = None,
) -> WorkflowAlertDelivery:
    event_id = uuid4()
    operation_id = event_id.int % 9_000_000_000 + 1
    generation = int(now.timestamp())
    event = WorkflowTerminalEvent(
        id=event_id,
        event_key=f"operation:{operation_id}:claim:{generation}:status:failed",
        source_kind="operation",
        operation_id=operation_id,
        claim_generation=generation,
        terminal_status="failed",
        classification_status=WorkflowTerminalClassificationStatus.READY.value,
        envelope=(
            envelope
            if envelope is not None
            else _valid_envelope(
                event_id=event_id,
                operation_id=operation_id,
                generation=generation,
                now=now,
            )
        ),
        occurred_at=now,
    )
    delivery = WorkflowAlertDelivery(
        id=uuid4(),
        event_id=event.id,
        sink_name="webhook",
        next_attempt_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(event)
    session.flush()
    session.add(delivery)
    session.commit()
    return delivery


def test_corrupt_persisted_envelope_is_closed_without_becoming_dispatchable(test_engine) -> None:
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    now = datetime.now(UTC).replace(microsecond=0)
    with factory() as seed:
        delivery = _insert_ready_delivery(
            seed,
            now=now,
            envelope={"schema_version": 0, "unsafe_manual_field": "must-not-dispatch"},
        )
        valid_delivery = _insert_ready_delivery(seed, now=now)

    try:
        with factory() as db:
            claims = claim_due_deliveries(
                db,
                now=now,
                lease_seconds=20,
                batch_size=2,
                policy=_policy(),
            )
            assert [claim.delivery_id for claim in claims] == [valid_delivery.id]
            assert isinstance(claims[0].envelope, WorkflowAlertEnvelopeV1)
            persisted = db.get(WorkflowAlertDelivery, delivery.id)
            assert persisted is not None
            assert persisted.status == WorkflowAlertDeliveryStatus.PERMANENT_FAILURE.value
            assert persisted.attempt_count == 1
            assert persisted.lease_expires_at is None
            assert persisted.last_error_code == "invalid_envelope"
    finally:
        with factory() as cleanup:
            cleanup.execute(
                delete(WorkflowAlertDelivery).where(
                    WorkflowAlertDelivery.id.in_([delivery.id, valid_delivery.id])
                )
            )
            cleanup.execute(
                delete(WorkflowTerminalEvent).where(
                    WorkflowTerminalEvent.id.in_([delivery.event_id, valid_delivery.event_id])
                )
            )
            cleanup.commit()


def test_claim_is_committed_before_external_work_and_recovered_lease_is_unique(test_engine) -> None:
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    now = datetime.now(UTC).replace(microsecond=0)
    with factory() as seed:
        delivery = _insert_ready_delivery(seed, now=now)

    try:
        with factory() as first_db:
            first = claim_due_deliveries(
                first_db,
                now=now,
                lease_seconds=20,
                batch_size=1,
                policy=_policy(),
            )
        assert len(first) == 1
        assert first[0].attempt_count == 1

        with factory() as competing_db:
            assert (
                claim_due_deliveries(
                    competing_db,
                    now=now + timedelta(seconds=19),
                    lease_seconds=20,
                    batch_size=1,
                    policy=_policy(),
                )
                == []
            )
            recovered = claim_due_deliveries(
                competing_db,
                now=now + timedelta(seconds=20),
                lease_seconds=20,
                batch_size=1,
                policy=_policy(),
            )
        assert len(recovered) == 1
        assert recovered[0].delivery_id == first[0].delivery_id
        assert recovered[0].attempt_count == 2

        # The stale worker cannot overwrite the recovered lease outcome.
        with factory() as stale_db:
            assert not mark_delivery_succeeded(
                stale_db,
                claim=first[0],
                now=now + timedelta(seconds=21),
            )
        with factory() as winner_db:
            assert mark_delivery_succeeded(
                winner_db,
                claim=recovered[0],
                now=now + timedelta(seconds=21),
            )
    finally:
        with factory() as cleanup:
            cleanup.execute(
                delete(WorkflowAlertDelivery).where(WorkflowAlertDelivery.id == delivery.id)
            )
            cleanup.execute(
                delete(WorkflowTerminalEvent).where(WorkflowTerminalEvent.id == delivery.event_id)
            )
            cleanup.commit()


def test_results_after_logical_lease_expiry_are_discarded_and_recovered(test_engine) -> None:
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    now = datetime.now(UTC).replace(microsecond=0)
    policy = _policy()
    with factory() as seed:
        success_delivery = _insert_ready_delivery(seed, now=now)
        failure_delivery = _insert_ready_delivery(seed, now=now)

    deliveries = (success_delivery, failure_delivery)
    try:
        with factory() as claiming_db:
            claims = {
                claim.delivery_id: claim
                for claim in claim_due_deliveries(
                    claiming_db,
                    now=now,
                    lease_seconds=20,
                    batch_size=2,
                    policy=policy,
                )
            }
        assert set(claims) == {delivery.id for delivery in deliveries}

        expired_at = now + timedelta(seconds=20)
        with factory() as expired_db:
            assert not mark_delivery_succeeded(
                expired_db,
                claim=claims[success_delivery.id],
                now=expired_at,
            )
            assert (
                record_delivery_failure(
                    expired_db,
                    claim=claims[failure_delivery.id],
                    now=expired_at,
                    error_code="timeout",
                    retryable=True,
                    retry_after_seconds=None,
                    policy=policy,
                )
                is None
            )
            states = dict(
                expired_db.execute(
                    select(WorkflowAlertDelivery.id, WorkflowAlertDelivery.status).where(
                        WorkflowAlertDelivery.id.in_([delivery.id for delivery in deliveries])
                    )
                ).all()
            )
            assert set(states.values()) == {WorkflowAlertDeliveryStatus.LEASED.value}

        with factory() as recovery_db:
            recovered = claim_due_deliveries(
                recovery_db,
                now=expired_at,
                lease_seconds=20,
                batch_size=2,
                policy=policy,
            )
        assert {claim.delivery_id for claim in recovered} == {
            delivery.id for delivery in deliveries
        }
        assert {claim.attempt_count for claim in recovered} == {2}
    finally:
        with factory() as cleanup:
            cleanup.execute(
                delete(WorkflowAlertDelivery).where(
                    WorkflowAlertDelivery.id.in_([delivery.id for delivery in deliveries])
                )
            )
            cleanup.execute(
                delete(WorkflowTerminalEvent).where(
                    WorkflowTerminalEvent.id.in_([delivery.event_id for delivery in deliveries])
                )
            )
            cleanup.commit()


def test_retry_exhaustion_and_retention_never_delete_pending_or_leased(test_engine) -> None:
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    now = datetime.now(UTC).replace(microsecond=0)
    policy = _policy(max_attempts=1)
    ids: list = []
    event_ids: list = []
    old_terminal_ids: list = []
    try:
        with factory() as db:
            delivery = _insert_ready_delivery(db, now=now)
            ids.append(delivery.id)
            event_ids.append(delivery.event_id)
            claim = claim_due_deliveries(
                db,
                now=now,
                lease_seconds=20,
                batch_size=1,
                policy=policy,
            )[0]
            assert (
                record_delivery_failure(
                    db,
                    claim=claim,
                    now=now,
                    error_code="http_5xx",
                    retryable=True,
                    retry_after_seconds=None,
                    policy=policy,
                )
                == WorkflowAlertDeliveryStatus.EXHAUSTED.value
            )
            old_terminal_ids.append(delivery.id)

            for status in ("pending", "leased", "delivered", "permanent_failure"):
                row = _insert_ready_delivery(db, now=now - timedelta(days=100))
                row.status = status
                row.attempt_count = 1 if status != "pending" else 0
                row.lease_expires_at = now + timedelta(hours=1) if status == "leased" else None
                row.delivered_at = now - timedelta(days=100) if status == "delivered" else None
                row.last_error_code = "http_4xx" if status == "permanent_failure" else None
                row.updated_at = now - timedelta(days=100)
                db.commit()
                ids.append(row.id)
                event_ids.append(row.event_id)
                if status in {"delivered", "permanent_failure"}:
                    old_terminal_ids.append(row.id)

            db.execute(
                update(WorkflowAlertDelivery)
                .where(WorkflowAlertDelivery.id.in_(old_terminal_ids))
                .values(updated_at=now - timedelta(days=100))
            )
            db.commit()

            deleted = cleanup_terminal_deliveries(
                db,
                now=now,
                retention_days=30,
                exhausted_retention_days=90,
                batch_size=100,
            )
            assert deleted == 3
            remaining = dict(
                db.execute(
                    select(WorkflowAlertDelivery.id, WorkflowAlertDelivery.status).where(
                        WorkflowAlertDelivery.id.in_(ids)
                    )
                ).all()
            )
            assert set(remaining.values()) == {"pending", "leased"}
    finally:
        with factory() as cleanup:
            cleanup.execute(delete(WorkflowAlertDelivery).where(WorkflowAlertDelivery.id.in_(ids)))
            cleanup.execute(
                delete(WorkflowTerminalEvent).where(WorkflowTerminalEvent.id.in_(event_ids))
            )
            cleanup.commit()


def test_ensure_delivery_is_idempotent_for_one_event_and_sink(test_engine) -> None:
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    now = datetime.now(UTC).replace(microsecond=0)
    with factory() as db:
        seeded = _insert_ready_delivery(db, now=now)
        db.execute(delete(WorkflowAlertDelivery).where(WorkflowAlertDelivery.id == seeded.id))
        db.commit()
        try:
            first_id = ensure_delivery(db, event_id=seeded.event_id, sink_name="webhook", now=now)
            second_id = ensure_delivery(db, event_id=seeded.event_id, sink_name="webhook", now=now)
            assert first_id == second_id
            assert (
                db.scalar(
                    select(WorkflowAlertDelivery).where(
                        WorkflowAlertDelivery.event_id == seeded.event_id,
                        WorkflowAlertDelivery.sink_name == "webhook",
                    )
                )
                is not None
            )
        finally:
            db.execute(
                delete(WorkflowAlertDelivery).where(
                    WorkflowAlertDelivery.event_id == seeded.event_id
                )
            )
            db.execute(
                delete(WorkflowTerminalEvent).where(WorkflowTerminalEvent.id == seeded.event_id)
            )
            db.commit()
