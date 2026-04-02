"""Agent task model for conductor-managed tasks.

Tracks the lifecycle of agentic tasks from submission through planning,
delegation, monitoring, and completion. Supports both user-initiated
and schedule-triggered tasks.

Enum Migration Strategy:
    New PG enums (agent_task_status, agent_task_source, insight_type,
    memory_type, risk_level) are created via CREATE TYPE in the Alembic
    migration. When extending these enums later, use:
        ALTER TYPE <enum_name> ADD VALUE '<new_value>';
    This must be in its own migration (cannot be inside a transaction
    on PostgreSQL < 12). See CLAUDE.md gotchas.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from src.models.base import Base


class AgentTaskStatus(StrEnum):
    """Task lifecycle states.

    State machine:
        received → planning → delegating → monitoring → synthesizing → completed
                                              ↓
                                          blocked (awaiting approval)
                                              ↓
                                          delegating (resume on approval)
    Any state can transition to 'failed'.
    """

    RECEIVED = "received"
    PLANNING = "planning"
    DELEGATING = "delegating"
    MONITORING = "monitoring"
    SYNTHESIZING = "synthesizing"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentTaskSource(StrEnum):
    """How the task was initiated."""

    USER = "user"
    SCHEDULE = "schedule"
    CONDUCTOR = "conductor"


class AgentTask(Base):
    """A conductor-managed agentic task.

    Tracks the full lifecycle of a task including planning, delegation
    to specialists, and result synthesis.
    """

    __tablename__ = "agent_tasks"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    task_type = Column(String, nullable=False)  # research, analysis, synthesis, ingestion
    source = Column(String, nullable=False, default=AgentTaskSource.USER)
    prompt = Column(Text, nullable=False)
    plan = Column(JSONB, nullable=True)
    status = Column(String, nullable=False, default=AgentTaskStatus.RECEIVED)
    result = Column(JSONB, nullable=True)
    parent_task_id = Column(PGUUID(as_uuid=True), ForeignKey("agent_tasks.id"), nullable=True)
    specialist_type = Column(String, nullable=True)
    persona_name = Column(String, nullable=False, default="default")
    persona_config = Column(JSONB, nullable=True)  # Full snapshot for reproducibility
    cost_total = Column(Float, nullable=True)
    tokens_total = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sub_tasks = relationship("AgentTask", backref="parent_task", remote_side="AgentTask.id")
    insights = relationship("AgentInsight", back_populates="task")
    approval_requests = relationship("ApprovalRequest", back_populates="task")

    __table_args__ = (
        Index("ix_agent_tasks_status", "status"),
        Index("ix_agent_tasks_source", "source"),
        Index("ix_agent_tasks_persona", "persona_name"),
        Index("ix_agent_tasks_created_at", "created_at"),
    )
