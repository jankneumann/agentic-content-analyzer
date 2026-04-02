"""Memory entry and filter models for the memory provider.

These Pydantic models define the interface between the memory provider
and its consumers. They are distinct from the ORM AgentMemory model —
MemoryEntry is the domain model, AgentMemory is the persistence model.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MemoryType(StrEnum):
    """Types of agent memory entries."""

    OBSERVATION = "observation"
    INSIGHT = "insight"
    TASK_RESULT = "task_result"
    PREFERENCE = "preference"
    META_LEARNING = "meta_learning"


class MemoryEntry(BaseModel):
    """A memory entry for agent recall.

    This is the domain model used by strategies and the provider.
    It maps to/from the AgentMemory ORM model for persistence.
    """

    id: str = ""
    content: str
    memory_type: MemoryType
    source_task_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    access_count: int = 0
    score: float = 0.0  # Set by retrieval strategies during recall


class MemoryFilter(BaseModel):
    """Filters for memory recall queries."""

    memory_types: list[MemoryType] | None = None
    tags: list[str] | None = None
    min_confidence: float | None = None
    source_task_id: str | None = None
    since: datetime | None = None
