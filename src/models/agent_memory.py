"""Agent memory model for persistent memory entries.

Stores memory entries created during agentic analysis, supporting
vector (pgvector), keyword (FTS), and graph (Graphiti) retrieval strategies.
"""

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from src.models.base import Base


class MemoryType(StrEnum):
    """Types of agent memory entries."""

    OBSERVATION = "observation"
    INSIGHT = "insight"
    TASK_RESULT = "task_result"
    PREFERENCE = "preference"
    META_LEARNING = "meta_learning"


class AgentMemory(Base):
    """A persistent memory entry for agent recall.

    Supports multiple retrieval strategies:
    - Vector: via the 'embedding' column (raw SQL, not ORM-mapped due to pgvector)
    - Keyword: via PostgreSQL FTS on 'content'
    - Graph: via Graphiti entity/relationship storage
    """

    __tablename__ = "agent_memories"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    memory_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    # Note: embedding column is raw SQL only (pgvector), not ORM-mapped
    # See CLAUDE.md gotcha: "pgvector not in ORM"
    tags = Column(JSONB, default=list)
    source_task_id = Column(PGUUID(as_uuid=True), ForeignKey("agent_tasks.id"), nullable=True)
    confidence = Column(Float, default=1.0)
    access_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_accessed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_agent_memories_type", "memory_type"),
        Index("ix_agent_memories_source_task", "source_task_id"),
        Index("ix_agent_memories_created_at", "created_at"),
    )
