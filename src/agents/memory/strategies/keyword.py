"""Keyword retrieval strategy using PostgreSQL Full-Text Search.

Uses ts_rank_cd for BM25-style ranking and to_tsvector/plainto_tsquery
for indexing and querying.
"""

import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.memory.models import MemoryEntry, MemoryFilter, MemoryType
from src.agents.memory.strategies.base import MemoryStrategy

logger = logging.getLogger(__name__)

# PostgreSQL FTS configuration (language dictionary).
FTS_CONFIG = "english"


class KeywordStrategy(MemoryStrategy):
    """Memory retrieval via PostgreSQL full-text search with ts_rank_cd."""

    def __init__(
        self,
        db_session_factory: Callable[..., AsyncSession],
    ) -> None:
        self._session_factory = db_session_factory

    async def store(self, memory: MemoryEntry) -> str:
        memory_id = memory.id or str(uuid.uuid4())
        try:
            async with self._session_factory() as session:
                await session.execute(
                    text(
                        f"""
                        INSERT INTO agent_memories
                            (id, content, memory_type, source_task_id, tags,
                             confidence, created_at, last_accessed_at, access_count,
                             content_tsv)
                        VALUES
                            (:id, :content, :memory_type, :source_task_id, :tags,
                             :confidence, :created_at, :last_accessed_at, :access_count,
                             to_tsvector('{FTS_CONFIG}', :content))
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
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("KeywordStrategy.store failed for memory %s", memory_id)
            raise
        return memory_id

    async def recall(
        self,
        query: str,
        limit: int = 10,
        filters: MemoryFilter | None = None,
    ) -> list[MemoryEntry]:
        where_clauses: list[str] = [
            f"content_tsv @@ plainto_tsquery('{FTS_CONFIG}', :query)"
        ]
        params: dict = {
            "query": query,
            "limit": limit,
            "now": datetime.now(timezone.utc),
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

        where_sql = " AND ".join(where_clauses)

        sql = text(
            f"""
            SELECT
                id, content, memory_type, source_task_id, tags,
                confidence, created_at, last_accessed_at, access_count,
                ts_rank_cd(content_tsv, plainto_tsquery('{FTS_CONFIG}', :query)) AS rank
            FROM agent_memories
            WHERE {where_sql}
            ORDER BY rank DESC
            LIMIT :limit
            """
        )

        async with self._session_factory() as session:
            result = await session.execute(sql, params)
            rows = result.fetchall()

        entries: list[MemoryEntry] = []
        for row in rows:
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
                    score=float(row.rank),
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
                return result.rowcount > 0  # type: ignore[union-attr]
        except Exception:
            logger.exception("KeywordStrategy.forget failed for %s", memory_id)
            return False

    async def health_check(self) -> bool:
        try:
            async with self._session_factory() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("KeywordStrategy health check failed")
            return False
