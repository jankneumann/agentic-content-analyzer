"""Durable persistence for provider batch jobs and requests.

Phase 0 deliberately targets only integer ``Content`` rows.  Keeping the
foreign key typed prevents the generic-target ambiguity that existed in the
original proposal, while nullable ``content_id`` preserves request history if
the content row is deleted.
"""

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
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from src.models.base import Base


class BatchJobState(StrEnum):
    """Local lifecycle for one provider batch job."""

    SUBMITTING = "submitting"
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class BatchRequestStatus(StrEnum):
    """Local lifecycle for one request contained in a batch job."""

    PENDING = "pending"
    CLAIMED = "claimed"
    SUBMITTED = "submitted"
    SUCCEEDED = "succeeded"
    FALLBACK = "fallback"
    FAILED = "failed"


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


_JSON = JSONB(astext_type=Text()).with_variant(JSON(), "sqlite")
_JOB_STATES = ", ".join(f"'{state.value}'" for state in BatchJobState)
_REQUEST_STATUSES = ", ".join(f"'{status.value}'" for status in BatchRequestStatus)
_OPEN_JOB_STATES = "'submitting', 'pending', 'running'"
_ACTIVE_REQUEST_STATUSES = "'pending', 'claimed', 'submitted', 'fallback'"


class BatchJob(Base):
    """A Gemini Batch API job grouping deferred requests."""

    __tablename__ = "batch_jobs"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    provider = Column(String(20), nullable=False)
    provider_job_name = Column(Text, nullable=True)
    model_id = Column(String(64), nullable=False)
    model_step = Column(String(40), nullable=False)
    state = Column(String(24), nullable=False)
    request_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        onupdate=_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        CheckConstraint(f"state IN ({_JOB_STATES})", name="ck_batch_jobs_state"),
        CheckConstraint("provider = 'google_ai'", name="ck_batch_jobs_provider"),
        Index(
            "ix_batch_jobs_open",
            "state",
            postgresql_where=text(f"state IN ({_OPEN_JOB_STATES})"),
            sqlite_where=text(f"state IN ({_OPEN_JOB_STATES})"),
        ),
        Index(
            "uq_batch_jobs_provider_job_name",
            "provider_job_name",
            unique=True,
            postgresql_where=text("provider_job_name IS NOT NULL"),
            sqlite_where=text("provider_job_name IS NOT NULL"),
        ),
    )


class BatchRequest(Base):
    """A single deferred LLM request awaiting reconciliation."""

    __tablename__ = "batch_requests"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    # ``<model_step>:<BIGINT content_id>:<32-char UUID>`` can exceed 64 chars.
    request_key = Column(String(128), nullable=False, unique=True)
    batch_job_id = Column(
        String(36), ForeignKey("batch_jobs.id", ondelete="SET NULL"), nullable=True
    )
    model_step = Column(String(40), nullable=False)
    model_id = Column(String(64), nullable=False)
    content_id = Column(BigInteger, ForeignKey("contents.id", ondelete="SET NULL"), nullable=True)
    request_payload = Column(_JSON, nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default=BatchRequestStatus.PENDING.value,
        server_default=BatchRequestStatus.PENDING.value,
    )
    result_text = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    fallback_attempts = Column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        onupdate=_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(f"status IN ({_REQUEST_STATUSES})", name="ck_batch_requests_status"),
        CheckConstraint("fallback_attempts >= 0", name="ck_batch_requests_fallback_attempts"),
        Index("ix_batch_requests_job", "batch_job_id"),
        Index(
            "ix_batch_requests_pending",
            "model_step",
            "model_id",
            "created_at",
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
        Index(
            "uq_batch_requests_active_target",
            "model_step",
            "content_id",
            unique=True,
            postgresql_where=text(
                f"content_id IS NOT NULL AND status IN ({_ACTIVE_REQUEST_STATUSES})"
            ),
            sqlite_where=text(f"content_id IS NOT NULL AND status IN ({_ACTIVE_REQUEST_STATUSES})"),
        ),
    )
