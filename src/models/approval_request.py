"""Approval request model for risk-tiered action control.

Tracks approval requests created when agents attempt HIGH or CRITICAL
risk actions. Supports the full approval lifecycle: pending → approved/denied/expired.
"""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import relationship

from src.models.base import Base


class RiskLevel(StrEnum):
    """Risk levels for agent actions.

    Controls whether actions are auto-approved, logged, or require human approval.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(StrEnum):
    """Approval request lifecycle states."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class ApprovalRequest(Base):
    """An approval request for a high-risk agent action."""

    __tablename__ = "approval_requests"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    task_id = Column(PGUUID(as_uuid=True), ForeignKey("agent_tasks.id"), nullable=False)
    action = Column(String, nullable=False)
    risk_level = Column(String, nullable=False)
    context = Column(JSONB, nullable=False)
    status = Column(String, nullable=False, default=ApprovalStatus.PENDING)
    decision_reason = Column(Text, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # Relationships
    task = relationship("AgentTask", back_populates="approval_requests")

    __table_args__ = (
        Index("ix_approval_requests_status", "status"),
        Index("ix_approval_requests_task", "task_id"),
    )
