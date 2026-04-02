"""Abstract base class for memory retrieval strategies.

Each strategy wraps a specific backend (pgvector, PostgreSQL FTS, Graphiti)
and provides store/recall/forget operations through a uniform interface.
"""

from abc import ABC, abstractmethod

from src.agents.memory.models import MemoryEntry, MemoryFilter


class MemoryStrategy(ABC):
    """Interface for memory storage/retrieval strategies."""

    @abstractmethod
    async def store(self, memory: MemoryEntry) -> str:
        """Store a memory entry, return its ID."""

    @abstractmethod
    async def recall(
        self,
        query: str,
        limit: int = 10,
        filters: MemoryFilter | None = None,
    ) -> list[MemoryEntry]:
        """Recall memories relevant to a query.

        Returns entries sorted by relevance (highest score first).
        Each entry's `score` field is set by the strategy.
        """

    @abstractmethod
    async def forget(self, memory_id: str) -> bool:
        """Remove a memory entry. Returns True if found and removed."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the strategy's backend is available.

        Used by MemoryProvider for graceful degradation.
        Returns True if the backend is responsive.
        """
