"""Vector similarity strategy using pgvector.

Uses raw SQL via sqlalchemy text() since pgvector embedding columns
are not mapped through the ORM (see CLAUDE.md gotchas).
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.memory.models import MemoryEntry, MemoryFilter, MemoryType
from src.agents.memory.strategies.base import MemoryStrategy

logger = logging.getLogger(__name__)

# How much to weight recency vs. raw cosine similarity.
# Final score = cosine_sim * (1 - RECENCY_WEIGHT) + recency_factor * RECENCY_WEIGHT
RECENCY_WEIGHT = 0.15
# Half-life for recency decay in days.
RECENCY_HALF_LIFE_DAYS = 7.0


class VectorStrategy(MemoryStrategy):
    """Memory retrieval via pgvector cosine similarity with recency boosting."""

    def __init__(
        self,
        db_session_factory: Callable[..., AsyncSession],
        embed_fn: Callable[[str], Awaitable[list[float]]],
    ) -> None:
        self._session_factory = db_session_factory
        self._embed_fn = embed_fn

    async def store(self, memory: MemoryEntry) -> str:
        memory_id = memory.id or str(uuid.uuid4())
        try:
            embedding = await self._embed_fn(memory.content)
            async with self._session_factory() as session:
                await session.execute(
                    text(
                        """
                        INSERT INTO agent_memories
                            (id, content, memory_type, source_task_id, tags,
                             confidence, created_at, last_accessed_at, access_count, embedding)
                        VALUES
                            (:id, :content, :memory_type, :source_task_id, :tags,
                             :confidence, :created_at, :last_accessed_at, :access_count, :embedding)
                        """
                    ),
                    {
                        "id": memory_id,
                        "content": memory.content,
                        "memory_type": memory.memory_type.value,
                        "source_task_id": memory.source_task_id,
                        "tags": memory.tags,
                        "confidence": memory.confidence,
                        "created_at": memory.created_at,
                        "last_accessed_at": memory.last_accessed,
                        "access_count": memory.access_count,
                        "embedding": str(embedding),
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("VectorStrategy.store failed for memory %s", memory_id)
            raise
        return memory_id

    async def recall(
        self,
        query: str,
        limit: int = 10,
        filters: MemoryFilter | None = None,
    ) -> list[MemoryEntry]:
        query_embedding = await self._embed_fn(query)

        # Build dynamic WHERE clauses from filters.
        where_clauses: list[str] = []
        params: dict = {
            "embedding": str(query_embedding),
            "limit": limit,
            "recency_weight": RECENCY_WEIGHT,
            "half_life_days": RECENCY_HALF_LIFE_DAYS,
            "now": datetime.now(UTC),
        }

        if filters:
            if filters.memory_types:
                where_clauses.append("memory_type = ANY(:memory_types)")
                params["memory_types"] = [mt.value for mt in filters.memory_types]
            if filters.tags:
                where_clauses.append("tags && :tags")
                params["tags"] = filters.tags
            if filters.min_confidence is not None:
                where_clauses.append("confidence >= :min_confidence")
                params["min_confidence"] = filters.min_confidence
            if filters.source_task_id:
                where_clauses.append("source_task_id = :source_task_id")
                params["source_task_id"] = filters.source_task_id
            if filters.since:
                where_clauses.append("created_at >= :since")
                params["since"] = filters.since

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        sql = text(
            f"""
            SELECT
                id, content, memory_type, source_task_id, tags,
                confidence, created_at, last_accessed_at, access_count,
                1 - (embedding <=> CAST(:embedding AS vector)) AS cosine_sim,
                EXP(-0.693 * EXTRACT(EPOCH FROM (:now - created_at)) / 86400.0 / :half_life_days)
                    AS recency_factor
            FROM agent_memories
            {where_sql}
            ORDER BY
                (1 - :recency_weight) * (1 - (embedding <=> CAST(:embedding AS vector)))
                + :recency_weight * EXP(-0.693 * EXTRACT(EPOCH FROM (:now - created_at)) / 86400.0 / :half_life_days)
                DESC
            LIMIT :limit
            """
        )

        async with self._session_factory() as session:
            result = await session.execute(sql, params)
            rows = result.fetchall()

            # Update access_count and last_accessed_at for recalled memories
            # (spec: agentic-analysis.9)
            if rows:
                recalled_ids = [str(row.id) for row in rows]
                await session.execute(
                    text(
                        """
                        UPDATE agent_memories
                        SET access_count = access_count + 1,
                            last_accessed_at = :now
                        WHERE id = ANY(:ids)
                        """
                    ),
                    {"ids": recalled_ids, "now": params["now"]},
                )
                await session.commit()

        entries: list[MemoryEntry] = []
        for row in rows:
            combined_score = (1 - RECENCY_WEIGHT) * float(row.cosine_sim) + RECENCY_WEIGHT * float(
                row.recency_factor
            )
            entries.append(
                MemoryEntry(
                    id=str(row.id),
                    content=row.content,
                    memory_type=MemoryType(row.memory_type),
                    source_task_id=row.source_task_id,
                    tags=row.tags or [],
                    confidence=float(row.confidence),
                    created_at=row.created_at,
                    last_accessed=row.last_accessed_at,
                    access_count=row.access_count,
                    score=combined_score,
                )
            )
        return entries

    async def forget(self, memory_id: str) -> bool:
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    text("DELETE FROM agent_memories WHERE id = :id"),
                    {"id": memory_id},
                )
                await session.commit()
                return (result.rowcount or 0) > 0  # type: ignore[attr-defined]
        except Exception:
            logger.exception("VectorStrategy.forget failed for %s", memory_id)
            return False

    async def health_check(self) -> bool:
        try:
            async with self._session_factory() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("VectorStrategy health check failed")
            return False
