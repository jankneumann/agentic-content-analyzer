"""Gemini batch-execution persistence models.

Two tables back the deferred-completion batch pipeline (Approach A):

- ``BatchJob``     — one submitted (or pending-submission) Gemini batch job.
- ``BatchRequest`` — one deferred LLM request, keyed by ``request_key`` and
  pointing at the row it reconciles back to via ``target_table``/``target_id``.

``target_id`` is a stringified primary key (Content uses integer ids), kept
generic so future non-Content steps can reuse the same table.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)

from src.models.base import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


class BatchJob(Base):
    """A Gemini Batch API job grouping many deferred requests."""

    __tablename__ = "batch_jobs"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    provider = Column(String(20), nullable=False)  # 'google_ai'
    provider_job_name = Column(Text, nullable=True)  # batches/123...; NULL until submitted
    model_id = Column(String(64), nullable=False)  # logical id, e.g. gemini-3.1-flash-lite
    model_step = Column(String(40), nullable=False)
    # pending|running|succeeded|failed|expired|cancelled
    state = Column(String(24), nullable=False)
    request_count = Column(Integer, nullable=False, default=0)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    __table_args__ = (Index("ix_batch_jobs_open", "state"),)


class BatchRequest(Base):
    """A single deferred LLM request awaiting batch reconciliation."""

    __tablename__ = "batch_requests"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    request_key = Column(String(64), nullable=False, unique=True)  # echoed in the JSONL line
    batch_job_id = Column(
        String(36), ForeignKey("batch_jobs.id"), nullable=True, index=True
    )  # NULL until flushed into a job
    model_step = Column(String(40), nullable=False)
    model_id = Column(String(64), nullable=False)
    target_table = Column(String(40), nullable=False)  # 'contents'
    target_id = Column(String(64), nullable=False)  # stringified PK of the row to reconcile
    request_payload = Column(JSON, nullable=False)  # serialized GenerateContentRequest
    # pending|submitted|succeeded|failed|fallback
    status = Column(String(20), nullable=False)
    result_text = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Flush worker scans pending requests by (step, model); keep it cheap.
        Index("ix_batch_requests_pending", "model_step", "model_id", "created_at"),
    )
