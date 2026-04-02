"""Memory entry and filter models for the memory provider.

These Pydantic models define the interface between the memory provider
and its consumers. They are distinct from the ORM AgentMemory model —
MemoryEntry is the domain model, AgentMemory is the persistence model.

MemoryType is imported from the ORM module to ensure a single source of truth.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from src.models.agent_memory import MemoryType  # Single source of truth


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
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_accessed: datetime = Field(default_factory=lambda: datetime.now(UTC))
    access_count: int = 0
    score: float = 0.0  # Set by retrieval strategies during recall


class MemoryFilter(BaseModel):
    """Filters for memory recall queries."""

    memory_types: list[MemoryType] | None = None
    tags: list[str] | None = None
    min_confidence: float | None = None
    source_task_id: str | None = None
    since: datetime | None = None
