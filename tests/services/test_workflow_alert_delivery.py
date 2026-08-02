"""Unit coverage for bounded workflow-alert delivery state transitions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from src.services.workflow_alert_delivery import (
    ClaimedWorkflowAlertDelivery,
    DeliveryRetryPolicy,
    build_due_delivery_query,
    calculate_retry_delay,
    delivery_idempotency_key,
    should_exhaust_delivery,
)


def test_due_delivery_query_uses_skip_locked_and_recovers_expired_leases() -> None:
    now = datetime(2026, 8, 1, 12, tzinfo=UTC)

    compiled = str(
        build_due_delivery_query(now=now, batch_size=25).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "FOR UPDATE OF workflow_alert_deliveries SKIP LOCKED" in compiled
    assert "workflow_alert_deliveries.status = 'pending'" in compiled
    assert "workflow_alert_deliveries.status = 'leased'" in compiled
    assert "workflow_alert_deliveries.lease_expires_at <=" in compiled
    assert "workflow_alert_deliveries.next_attempt_at <=" in compiled
    assert "LIMIT 25" in compiled


def test_retry_schedule_is_exponential_and_all_inputs_are_bounded() -> None:
    policy = DeliveryRetryPolicy(
        max_attempts=5,
        base_backoff_seconds=30,
        max_backoff_seconds=120,
        max_retry_after_seconds=90,
        max_age_seconds=600,
    )

    assert calculate_retry_delay(attempt_count=1, retry_after_seconds=None, policy=policy) == 30
    assert calculate_retry_delay(attempt_count=3, retry_after_seconds=None, policy=policy) == 120
    assert calculate_retry_delay(attempt_count=20, retry_after_seconds=None, policy=policy) == 120
    assert calculate_retry_delay(attempt_count=1, retry_after_seconds=80, policy=policy) == 80
    assert calculate_retry_delay(attempt_count=1, retry_after_seconds=9_999, policy=policy) == 90
    assert calculate_retry_delay(attempt_count=1, retry_after_seconds=-10, policy=policy) == 30


def test_retry_ceiling_checks_attempts_age_and_scheduled_time() -> None:
    created_at = datetime(2026, 8, 1, 12, tzinfo=UTC)
    policy = DeliveryRetryPolicy(
        max_attempts=3,
        base_backoff_seconds=30,
        max_backoff_seconds=120,
        max_retry_after_seconds=90,
        max_age_seconds=300,
    )

    assert should_exhaust_delivery(
        attempt_count=3,
        created_at=created_at,
        now=created_at + timedelta(seconds=10),
        retry_delay_seconds=30,
        policy=policy,
    )
    assert should_exhaust_delivery(
        attempt_count=1,
        created_at=created_at,
        now=created_at + timedelta(seconds=300),
        retry_delay_seconds=30,
        policy=policy,
    )
    assert should_exhaust_delivery(
        attempt_count=1,
        created_at=created_at,
        now=created_at + timedelta(seconds=290),
        retry_delay_seconds=30,
        policy=policy,
    )
    assert not should_exhaust_delivery(
        attempt_count=1,
        created_at=created_at,
        now=created_at + timedelta(seconds=100),
        retry_delay_seconds=30,
        policy=policy,
    )


def test_idempotency_key_is_stable_across_recovered_attempts() -> None:
    event_id = uuid4()
    delivery_id = uuid4()
    first = ClaimedWorkflowAlertDelivery(
        delivery_id=delivery_id,
        event_id=event_id,
        sink_name="webhook",
        attempt_count=1,
        lease_expires_at=datetime(2026, 8, 1, 12, 1, tzinfo=UTC),
        created_at=datetime(2026, 8, 1, 12, tzinfo=UTC),
        envelope={},
    )
    recovered = ClaimedWorkflowAlertDelivery(
        delivery_id=delivery_id,
        event_id=event_id,
        sink_name="webhook",
        attempt_count=2,
        lease_expires_at=datetime(2026, 8, 1, 12, 3, tzinfo=UTC),
        created_at=first.created_at,
        envelope={},
    )

    assert delivery_idempotency_key(first) == delivery_idempotency_key(recovered)
    assert str(delivery_id) in delivery_idempotency_key(first)
    assert "attempt" not in delivery_idempotency_key(first)
