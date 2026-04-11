"""Graph-based memory strategy using a Graphiti-compatible client.

Stores memories as episodes in a knowledge graph and retrieves them
via semantic search over graph entities and relationships.

Works with any graph backend (Neo4j, FalkorDB) via the GraphitiClient
abstraction — the client is constructed externally using the appropriate
GraphDBProvider and passed in as a dependency.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from src.agents.memory.models import MemoryEntry, MemoryFilter, MemoryType
from src.agents.memory.strategies.base import MemoryStrategy

logger = logging.getLogger(__name__)


class GraphStrategy(MemoryStrategy):
    """Memory retrieval via a Graphiti-compatible knowledge graph client.

    The graph_client is typed loosely (Any) to avoid import coupling.
    It is expected to expose:
        - add_episode(episode_id, content, metadata) -> None
        - search(query, num_results, filters) -> list[dict]
        - delete_episode(episode_id) -> bool
        - status() -> dict  (or similar connectivity check)

    The client is backend-agnostic — it should be created via
    ``await GraphitiClient.create()`` which uses the configured
    GraphDBProvider (Neo4j or FalkorDB) internally.
    """

    def __init__(self, graph_client: Any) -> None:
        self._client = graph_client

    async def store(self, memory: MemoryEntry) -> str:
        memory_id = memory.id or str(uuid.uuid4())
        try:
            metadata = {
                "memory_type": memory.memory_type.value,
                "source_task_id": memory.source_task_id,
                "tags": memory.tags,
                "confidence": memory.confidence,
                "created_at": memory.created_at.isoformat(),
                "access_count": memory.access_count,
            }
            await self._client.add_episode(
                episode_id=memory_id,
                content=memory.content,
                metadata=metadata,
            )
        except Exception:
            logger.exception("GraphStrategy.store failed for memory %s", memory_id)
            raise
        return memory_id

    async def recall(
        self,
        query: str,
        limit: int = 10,
        filters: MemoryFilter | None = None,
    ) -> list[MemoryEntry]:
        try:
            search_filters: dict[str, Any] = {}
            if filters:
                if filters.memory_types:
                    search_filters["memory_types"] = [mt.value for mt in filters.memory_types]
                if filters.tags:
                    search_filters["tags"] = filters.tags
                if filters.min_confidence is not None:
                    search_filters["min_confidence"] = filters.min_confidence
                if filters.source_task_id:
                    search_filters["source_task_id"] = filters.source_task_id
                if filters.since:
                    search_filters["since"] = filters.since.isoformat()

            results = await self._client.search(
                query=query,
                num_results=limit,
                filters=search_filters if search_filters else None,
            )

            entries: list[MemoryEntry] = []
            for item in results:
                metadata = item.get("metadata", {})
                score = float(item.get("score", 0.0))
                entries.append(
                    MemoryEntry(
                        id=str(item.get("episode_id", "")),
                        content=item.get("content", ""),
                        memory_type=MemoryType(
                            metadata.get("memory_type", MemoryType.OBSERVATION.value)
                        ),
                        source_task_id=metadata.get("source_task_id"),
                        tags=metadata.get("tags", []),
                        confidence=float(metadata.get("confidence", 1.0)),
                        created_at=metadata.get("created_at") or datetime.now(UTC),
                        access_count=int(metadata.get("access_count", 0)),
                        score=score,
                    )
                )
            return entries

        except Exception:
            logger.exception("GraphStrategy.recall failed for query: %s", query[:80])
            return []

    async def forget(self, memory_id: str) -> bool:
        try:
            result = await self._client.delete_episode(episode_id=memory_id)
            return bool(result)
        except Exception:
            logger.exception("GraphStrategy.forget failed for %s", memory_id)
            return False

    async def health_check(self) -> bool:
        try:
            await self._client.status()
            return True
        except Exception:
            logger.exception("GraphStrategy health check failed")
            return False
