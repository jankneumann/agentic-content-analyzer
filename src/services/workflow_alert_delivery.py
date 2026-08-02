"""Recoverable, bounded persistence operations for workflow-alert delivery.

Claims are committed before callers perform external I/O. Completion writes are
fenced by the exact lease timestamp so a stale worker cannot overwrite a lease
that another worker recovered after expiry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import Select, and_, delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import Session

from src.contracts.workflow_alert_models import WorkflowAlertEnvelopeV1
from src.models.workflow_alert import (
    WorkflowAlertDelivery,
    WorkflowAlertDeliveryStatus,
    WorkflowTerminalClassificationStatus,
    WorkflowTerminalEvent,
)


@dataclass(frozen=True, slots=True)
class DeliveryRetryPolicy:
    """Finite retry and age ceilings supplied by validated settings."""

    max_attempts: int
    base_backoff_seconds: int
    max_backoff_seconds: int
    max_retry_after_seconds: int
    max_age_seconds: int

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 20:
            raise ValueError("max_attempts is outside the supported range")
        if not 1 <= self.base_backoff_seconds <= self.max_backoff_seconds <= 86_400:
            raise ValueError("backoff settings are outside the supported range")
        if not 1 <= self.max_retry_after_seconds <= 86_400:
            raise ValueError("max_retry_after_seconds is outside the supported range")
        if not 60 <= self.max_age_seconds <= 604_800:
            raise ValueError("max_age_seconds is outside the supported range")


@dataclass(frozen=True, slots=True)
class ClaimedWorkflowAlertDelivery:
    """Immutable lease token and safe body returned by a committed claim."""

    delivery_id: UUID
    event_id: UUID
    sink_name: str
    attempt_count: int
    lease_expires_at: datetime
    created_at: datetime
    envelope: WorkflowAlertEnvelopeV1


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def delivery_idempotency_key(claim: ClaimedWorkflowAlertDelivery) -> str:
    """Return the receiver key, stable across every attempt of one delivery."""

    return f"workflow-alert:{claim.delivery_id}"


def ensure_delivery(
    db: Session,
    *,
    event_id: UUID,
    sink_name: str,
    now: datetime,
) -> UUID:
    """Create one per-event sink delivery, or return the concurrent winner."""

    if re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", sink_name) is None:
        raise ValueError("sink_name must be a bounded closed identifier")
    delivery_id = uuid4()
    statement = (
        postgresql_insert(WorkflowAlertDelivery)
        .values(
            id=delivery_id,
            event_id=event_id,
            sink_name=sink_name,
            status=WorkflowAlertDeliveryStatus.PENDING.value,
            attempt_count=0,
            next_attempt_at=now,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(
            index_elements=[WorkflowAlertDelivery.event_id, WorkflowAlertDelivery.sink_name]
        )
        .returning(WorkflowAlertDelivery.id)
    )
    try:
        persisted_id = db.execute(statement).scalar_one_or_none()
        if persisted_id is None:
            persisted_id = db.execute(
                select(WorkflowAlertDelivery.id).where(
                    WorkflowAlertDelivery.event_id == event_id,
                    WorkflowAlertDelivery.sink_name == sink_name,
                )
            ).scalar_one()
        db.commit()
    except Exception:
        db.rollback()
        raise
    return cast(UUID, persisted_id)


def build_due_delivery_query(*, now: datetime, batch_size: int) -> Select[tuple[Any, Any]]:
    """Build the ordered PostgreSQL claim query with expired-lease recovery."""

    bounded_size = max(1, min(int(batch_size), 500))
    due_state = or_(
        WorkflowAlertDelivery.status == WorkflowAlertDeliveryStatus.PENDING.value,
        and_(
            WorkflowAlertDelivery.status == WorkflowAlertDeliveryStatus.LEASED.value,
            WorkflowAlertDelivery.lease_expires_at <= now,
        ),
    )
    return (
        select(WorkflowAlertDelivery, WorkflowTerminalEvent)
        .join(WorkflowTerminalEvent, WorkflowTerminalEvent.id == WorkflowAlertDelivery.event_id)
        .where(
            due_state,
            WorkflowAlertDelivery.next_attempt_at <= now,
            WorkflowTerminalEvent.classification_status
            == WorkflowTerminalClassificationStatus.READY.value,
            WorkflowTerminalEvent.envelope.is_not(None),
        )
        .order_by(WorkflowAlertDelivery.next_attempt_at, WorkflowAlertDelivery.id)
        .limit(bounded_size)
        .with_for_update(of=WorkflowAlertDelivery, skip_locked=True)
    )


def claim_due_deliveries(
    db: Session,
    *,
    now: datetime,
    lease_seconds: int,
    batch_size: int,
    policy: DeliveryRetryPolicy,
) -> list[ClaimedWorkflowAlertDelivery]:
    """Claim and commit a bounded batch before any caller performs HTTP I/O."""

    if not 10 <= lease_seconds <= 900:
        raise ValueError("lease_seconds is outside the supported range")
    claimed: list[ClaimedWorkflowAlertDelivery] = []
    try:
        rows = db.execute(build_due_delivery_query(now=now, batch_size=batch_size)).all()
        lease_expires_at = now + timedelta(seconds=lease_seconds)
        for delivery, event in rows:
            try:
                envelope = WorkflowAlertEnvelopeV1.model_validate(event.envelope)
            except ValidationError:
                delivery.status = WorkflowAlertDeliveryStatus.PERMANENT_FAILURE.value
                delivery.attempt_count = int(delivery.attempt_count or 0) + 1
                delivery.lease_expires_at = None
                delivery.delivered_at = None
                delivery.last_error_code = "invalid_envelope"
                delivery.updated_at = now
                continue
            deadline = _aware(delivery.created_at) + timedelta(seconds=policy.max_age_seconds)
            if int(delivery.attempt_count or 0) >= policy.max_attempts or now >= deadline:
                delivery.status = WorkflowAlertDeliveryStatus.EXHAUSTED.value
                delivery.lease_expires_at = None
                delivery.last_error_code = "retry_budget_exhausted"
                delivery.updated_at = now
                continue
            delivery.status = WorkflowAlertDeliveryStatus.LEASED.value
            delivery.attempt_count = int(delivery.attempt_count or 0) + 1
            delivery.lease_expires_at = lease_expires_at
            delivery.last_error_code = None
            delivery.updated_at = now
            claimed.append(
                ClaimedWorkflowAlertDelivery(
                    delivery_id=delivery.id,
                    event_id=delivery.event_id,
                    sink_name=delivery.sink_name,
                    attempt_count=delivery.attempt_count,
                    lease_expires_at=lease_expires_at,
                    created_at=_aware(delivery.created_at),
                    envelope=envelope,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return claimed


def calculate_retry_delay(
    *,
    attempt_count: int,
    retry_after_seconds: int | None,
    policy: DeliveryRetryPolicy,
) -> int:
    """Calculate a finite exponential delay with a bounded receiver hint."""

    exponent = max(0, min(int(attempt_count) - 1, 30))
    exponential = min(
        policy.base_backoff_seconds * (2**exponent),
        policy.max_backoff_seconds,
    )
    if retry_after_seconds is None:
        return exponential
    receiver_delay = max(0, min(int(retry_after_seconds), policy.max_retry_after_seconds))
    return max(exponential, receiver_delay)


def should_exhaust_delivery(
    *,
    attempt_count: int,
    created_at: datetime,
    now: datetime,
    retry_delay_seconds: int,
    policy: DeliveryRetryPolicy,
) -> bool:
    """Return whether attempts or the absolute delivery lifetime is exhausted."""

    deadline = _aware(created_at) + timedelta(seconds=policy.max_age_seconds)
    return (
        attempt_count >= policy.max_attempts
        or now >= deadline
        or (now + timedelta(seconds=max(0, retry_delay_seconds)) > deadline)
    )


def mark_delivery_succeeded(
    db: Session,
    *,
    claim: ClaimedWorkflowAlertDelivery,
    now: datetime,
) -> bool:
    """Persist success only if the caller still owns the exact committed lease."""

    statement = (
        update(WorkflowAlertDelivery)
        .where(
            WorkflowAlertDelivery.id == claim.delivery_id,
            WorkflowAlertDelivery.status == WorkflowAlertDeliveryStatus.LEASED.value,
            WorkflowAlertDelivery.lease_expires_at == claim.lease_expires_at,
            WorkflowAlertDelivery.lease_expires_at > now,
        )
        .values(
            status=WorkflowAlertDeliveryStatus.DELIVERED.value,
            lease_expires_at=None,
            delivered_at=now,
            last_error_code=None,
            updated_at=now,
        )
    )
    try:
        matched = db.execute(statement).rowcount == 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return matched


def record_delivery_failure(
    db: Session,
    *,
    claim: ClaimedWorkflowAlertDelivery,
    now: datetime,
    error_code: str,
    retryable: bool,
    retry_after_seconds: int | None,
    policy: DeliveryRetryPolicy,
) -> str | None:
    """Persist one safe failure result, fenced by the caller's exact lease."""

    if re.fullmatch(r"[a-z][a-z0-9_.-]{0,79}", error_code) is None:
        raise ValueError("error_code must be a bounded closed code")
    delay = calculate_retry_delay(
        attempt_count=claim.attempt_count,
        retry_after_seconds=retry_after_seconds,
        policy=policy,
    )
    if not retryable:
        status = WorkflowAlertDeliveryStatus.PERMANENT_FAILURE.value
        next_attempt_at = now
    elif should_exhaust_delivery(
        attempt_count=claim.attempt_count,
        created_at=claim.created_at,
        now=now,
        retry_delay_seconds=delay,
        policy=policy,
    ):
        status = WorkflowAlertDeliveryStatus.EXHAUSTED.value
        next_attempt_at = now
    else:
        status = WorkflowAlertDeliveryStatus.PENDING.value
        next_attempt_at = now + timedelta(seconds=delay)

    statement = (
        update(WorkflowAlertDelivery)
        .where(
            WorkflowAlertDelivery.id == claim.delivery_id,
            WorkflowAlertDelivery.status == WorkflowAlertDeliveryStatus.LEASED.value,
            WorkflowAlertDelivery.lease_expires_at == claim.lease_expires_at,
            WorkflowAlertDelivery.lease_expires_at > now,
        )
        .values(
            status=status,
            next_attempt_at=next_attempt_at,
            lease_expires_at=None,
            delivered_at=None,
            last_error_code=error_code,
            updated_at=now,
        )
    )
    try:
        matched = db.execute(statement).rowcount == 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return status if matched else None


def cleanup_terminal_deliveries(
    db: Session,
    *,
    now: datetime,
    retention_days: int,
    exhausted_retention_days: int,
    batch_size: int,
) -> int:
    """Delete a bounded terminal-only batch; pending and leased rows are excluded."""

    if not 1 <= retention_days <= exhausted_retention_days <= 3650:
        raise ValueError("retention settings are outside the supported range")
    bounded_size = max(1, min(int(batch_size), 500))
    regular_cutoff = now - timedelta(days=retention_days)
    exhausted_cutoff = now - timedelta(days=exhausted_retention_days)
    candidate_ids = (
        select(WorkflowAlertDelivery.id)
        .where(
            or_(
                and_(
                    WorkflowAlertDelivery.status.in_(
                        (
                            WorkflowAlertDeliveryStatus.DELIVERED.value,
                            WorkflowAlertDeliveryStatus.PERMANENT_FAILURE.value,
                        )
                    ),
                    WorkflowAlertDelivery.updated_at < regular_cutoff,
                ),
                and_(
                    WorkflowAlertDelivery.status == WorkflowAlertDeliveryStatus.EXHAUSTED.value,
                    WorkflowAlertDelivery.updated_at < exhausted_cutoff,
                ),
            )
        )
        .order_by(WorkflowAlertDelivery.updated_at, WorkflowAlertDelivery.id)
        .limit(bounded_size)
    )
    try:
        result = db.execute(
            delete(WorkflowAlertDelivery).where(WorkflowAlertDelivery.id.in_(candidate_ids))
        )
        deleted = int(result.rowcount or 0)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return deleted
