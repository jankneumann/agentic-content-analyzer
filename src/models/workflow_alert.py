"""Persistence models for terminal workflow evidence and alert delivery."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import JSON

from src.models.base import Base

_JSON = JSONB().with_variant(JSON(), "sqlite")


class WorkflowTerminalSourceKind(StrEnum):
    OPERATION = "operation"
    RECONCILIATION_ACTION = "reconciliation_action"
    RECONCILIATION_FAILURE = "reconciliation_failure"


class WorkflowTerminalClassificationStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    TELEMETRY_ONLY = "telemetry_only"
    REJECTED = "rejected"


class WorkflowAlertDeliveryStatus(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    DELIVERED = "delivered"
    PERMANENT_FAILURE = "permanent_failure"
    EXHAUSTED = "exhausted"


class WorkflowTerminalEvent(Base):
    """Durable minimal intent captured with its authoritative terminal write."""

    __tablename__ = "workflow_terminal_events"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    event_key = Column(String(160), nullable=False, unique=True)
    source_kind = Column(String(40), nullable=False)
    operation_id = Column(BigInteger, nullable=True)
    claim_generation = Column(BigInteger, nullable=True)
    terminal_status = Column(String(20), nullable=True)
    reconciliation_action_id = Column(BigInteger, nullable=True)
    reconciliation_run_id = Column(UUID(as_uuid=True), nullable=True)
    reconciliation_content_id = Column(BigInteger, nullable=True)
    classification_status = Column(
        String(20),
        nullable=False,
        default=WorkflowTerminalClassificationStatus.PENDING.value,
        server_default=WorkflowTerminalClassificationStatus.PENDING.value,
    )
    envelope = Column(_JSON, nullable=True)
    telemetry_emitted_at = Column(DateTime(timezone=True), nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('operation','reconciliation_action','reconciliation_failure')",
            name="ck_workflow_terminal_events_source_kind",
        ),
        CheckConstraint(
            "(source_kind = 'operation' AND event_key ~ "
            "'^operation:[1-9][0-9]*:claim:[0-9]+:status:(completed|failed|cancelled)$') "
            "OR (source_kind = 'reconciliation_action' AND event_key ~ "
            "'^reconciliation-action:[1-9][0-9]*$') "
            "OR (source_kind = 'reconciliation_failure' AND event_key ~ "
            "'^reconciliation-failure:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
            "[0-9a-f]{4}-[0-9a-f]{12}:content:[1-9][0-9]*:reason:apply_failed$')",
            name="ck_workflow_terminal_events_event_key",
        ),
        CheckConstraint(
            "terminal_status IS NULL OR terminal_status IN ('completed','failed','cancelled')",
            name="ck_workflow_terminal_events_terminal_status",
        ),
        CheckConstraint(
            "classification_status IN ('pending','ready','telemetry_only','rejected')",
            name="ck_workflow_terminal_events_classification_status",
        ),
        CheckConstraint(
            "operation_id IS NULL OR operation_id > 0",
            name="ck_workflow_terminal_events_operation_id",
        ),
        CheckConstraint(
            "claim_generation IS NULL OR claim_generation >= 0",
            name="ck_workflow_terminal_events_claim_generation",
        ),
        CheckConstraint(
            "reconciliation_action_id IS NULL OR reconciliation_action_id > 0",
            name="ck_workflow_terminal_events_reconciliation_action_id",
        ),
        CheckConstraint(
            "reconciliation_content_id IS NULL OR reconciliation_content_id > 0",
            name="ck_workflow_terminal_events_reconciliation_content_id",
        ),
        CheckConstraint(
            "envelope IS NULL OR jsonb_typeof(envelope) = 'object'",
            name="ck_workflow_terminal_events_envelope_object",
        ),
        CheckConstraint(
            "(source_kind = 'operation' AND operation_id IS NOT NULL "
            "AND claim_generation IS NOT NULL AND terminal_status IS NOT NULL "
            "AND reconciliation_action_id IS NULL AND reconciliation_run_id IS NULL "
            "AND reconciliation_content_id IS NULL) OR "
            "(source_kind = 'reconciliation_action' AND operation_id IS NULL "
            "AND claim_generation IS NULL AND terminal_status IS NULL "
            "AND reconciliation_action_id IS NOT NULL AND reconciliation_run_id IS NOT NULL "
            "AND reconciliation_content_id IS NOT NULL) OR "
            "(source_kind = 'reconciliation_failure' AND operation_id IS NULL "
            "AND claim_generation IS NULL AND terminal_status IS NULL "
            "AND reconciliation_action_id IS NULL AND reconciliation_run_id IS NOT NULL "
            "AND reconciliation_content_id IS NOT NULL)",
            name="ck_workflow_terminal_events_source_shape",
        ),
        Index(
            "ix_workflow_terminal_events_classification_due",
            "created_at",
            "id",
            postgresql_where=text("classification_status = 'pending'"),
        ),
        Index(
            "ix_workflow_terminal_events_retention",
            "created_at",
            "id",
            postgresql_where=text("classification_status IN ('ready','telemetry_only','rejected')"),
        ),
    )


class WorkflowAlertDelivery(Base):
    """Recoverable per-sink delivery state for one terminal event."""

    __tablename__ = "workflow_alert_deliveries"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "workflow_terminal_events.id",
            name="fk_workflow_alert_deliveries_event",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    sink_name = Column(String(64), nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default=WorkflowAlertDeliveryStatus.PENDING.value,
        server_default=WorkflowAlertDeliveryStatus.PENDING.value,
    )
    attempt_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    next_attempt_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    last_error_code = Column(String(80), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("event_id", "sink_name", name="uq_workflow_alert_deliveries_event_sink"),
        CheckConstraint(
            "sink_name ~ '^[a-z][a-z0-9_-]{0,63}$'",
            name="ck_workflow_alert_deliveries_sink_name",
        ),
        CheckConstraint(
            "status IN ('pending','leased','delivered','permanent_failure','exhausted')",
            name="ck_workflow_alert_deliveries_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_workflow_alert_deliveries_attempt_count"),
        CheckConstraint(
            "last_error_code IS NULL OR last_error_code ~ '^[a-z][a-z0-9_.-]{0,79}$'",
            name="ck_workflow_alert_deliveries_last_error_code",
        ),
        Index(
            "ix_workflow_alert_deliveries_due",
            "next_attempt_at",
            "id",
            postgresql_where=text("status IN ('pending','leased')"),
        ),
        Index(
            "ix_workflow_alert_deliveries_retention",
            "updated_at",
            "id",
            postgresql_where=text("status IN ('delivered','permanent_failure','exhausted')"),
        ),
    )
