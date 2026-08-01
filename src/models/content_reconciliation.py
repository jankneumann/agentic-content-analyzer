"""Append-only evidence model for applied content reconciliation actions."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import Base

_CONTENT_STATUSES = "'pending','parsing','parsed','processing','completed','failed','filtered_out'"
_OPERATION_STATUSES = "'queued','in_progress','completed','failed','cancelled'"
_ACTIONS = (
    "'retry_operation','project_completed','project_parsed','restore_parsed',"
    "'restore_pending','cancel_restore_parsed','cancel_restore_pending'"
)
_REASONS = (
    "'summary_exists','extraction_completed','cancellation_requested','stale_operation',"
    "'failed_operation','summarization_cancelled','extraction_cancelled'"
)


class ContentReconciliationAction(Base):
    """Immutable database evidence for one applied reconciliation decision."""

    __tablename__ = "content_reconciliation_actions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), nullable=False)
    content_id = Column(BigInteger, nullable=False)
    operation_id = Column(BigInteger, nullable=False)
    claim_generation = Column(BigInteger, nullable=False)
    claim_protocol_version = Column(SmallInteger, nullable=False)
    phase = Column(String(16), nullable=False)
    content_status_before = Column(String(32), nullable=False)
    content_status_after = Column(String(32), nullable=False)
    operation_status_before = Column(String(32), nullable=False)
    operation_status_after = Column(String(32), nullable=False)
    retry_count_before = Column(Integer, nullable=False)
    retry_count_after = Column(Integer, nullable=False)
    action = Column(String(40), nullable=False)
    reason = Column(String(40), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "run_id", "content_id", name="uq_content_reconciliation_actions_run_content"
        ),
        CheckConstraint("content_id > 0", name="ck_content_reconciliation_content_id"),
        CheckConstraint("operation_id > 0", name="ck_content_reconciliation_operation_id"),
        CheckConstraint("claim_generation > 0", name="ck_content_reconciliation_claim_generation"),
        CheckConstraint(
            "claim_protocol_version >= 1",
            name="ck_content_reconciliation_claim_protocol",
        ),
        CheckConstraint(
            "phase IN ('parsing', 'processing')", name="ck_content_reconciliation_phase"
        ),
        CheckConstraint(
            f"content_status_before IN ({_CONTENT_STATUSES})",
            name="ck_content_reconciliation_content_status_before",
        ),
        CheckConstraint(
            f"content_status_after IN ({_CONTENT_STATUSES})",
            name="ck_content_reconciliation_content_status_after",
        ),
        CheckConstraint(
            f"operation_status_before IN ({_OPERATION_STATUSES})",
            name="ck_content_reconciliation_operation_status_before",
        ),
        CheckConstraint(
            f"operation_status_after IN ({_OPERATION_STATUSES})",
            name="ck_content_reconciliation_operation_status_after",
        ),
        CheckConstraint("retry_count_before >= 0", name="ck_content_reconciliation_retry_before"),
        CheckConstraint("retry_count_after >= 0", name="ck_content_reconciliation_retry_after"),
        CheckConstraint(f"action IN ({_ACTIONS})", name="ck_content_reconciliation_action"),
        CheckConstraint(f"reason IN ({_REASONS})", name="ck_content_reconciliation_reason"),
        Index("ix_content_reconciliation_actions_run", "run_id", "id"),
        Index(
            "ix_content_reconciliation_actions_content_created",
            "content_id",
            created_at.desc(),
        ),
    )
