"""BM25 search strategy abstraction for cross-backend compatibility.

Provides a BM25SearchStrategy protocol with two implementations:
- ParadeDBBM25Strategy: Uses pg_search extension (true BM25 ranking)
- PostgresNativeFTSStrategy: Uses PostgreSQL native FTS (universal fallback)

The factory auto-detects pg_search availability at runtime.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


@runtime_checkable
class BM25SearchStrategy(Protocol):
    """Protocol for BM25/keyword search implementations."""

    @property
    def name(self) -> str: ...

    def search(
        self,
        query: str,
        limit: int = 100,
        content_ids: list[int] | None = None,
    ) -> list[tuple[int, float, int]]:
        """Search chunks by keyword relevance.

        Args:
            query: Search query text
            limit: Maximum results to return
            content_ids: Optional filter to specific content IDs

        Returns:
            List of (chunk_id, score, content_id) tuples, sorted by score descending.
        """
        ...


class ParadeDBBM25Strategy:
    """Uses pg_search extension for true BM25 ranking.

    ParadeDB provides Okapi BM25 with proper IDF/TF scoring,
    significantly higher quality than native FTS for keyword search.
    Available on Supabase, Neon (AWS), and local with extension installed.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def name(self) -> str:
        return "paradedb_bm25"

    def search(
        self,
        query: str,
        limit: int = 100,
        content_ids: list[int] | None = None,
    ) -> list[tuple[int, float, int]]:
        if not query.strip():
            return []

        if content_ids:
            stmt = text("""
                SELECT id, paradedb.score(id) as score, content_id
                FROM document_chunks
                WHERE chunk_text @@@ :query
                  AND content_id = ANY(:content_ids)
                ORDER BY score DESC
                LIMIT :limit
            """)
            result = self._session.execute(
                stmt,
                {"query": query, "limit": limit, "content_ids": content_ids},
            )
        else:
            stmt = text("""
                SELECT id, paradedb.score(id) as score, content_id
                FROM document_chunks
                WHERE chunk_text @@@ :query
                ORDER BY score DESC
                LIMIT :limit
            """)
            result = self._session.execute(
                stmt,
                {"query": query, "limit": limit},
            )

        return [(row.id, row.score, row.content_id) for row in result]


class PostgresNativeFTSStrategy:
    """Uses PostgreSQL native full-text search with ts_rank_cd.

    Works on all PostgreSQL installations without extensions.
    Uses the TSVECTOR column populated by the database trigger
    and the GIN index for fast lookups.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def name(self) -> str:
        return "postgres_native_fts"

    def search(
        self,
        query: str,
        limit: int = 100,
        content_ids: list[int] | None = None,
    ) -> list[tuple[int, float, int]]:
        if not query.strip():
            return []

        if content_ids:
            stmt = text("""
                SELECT id, ts_rank_cd(search_vector, plainto_tsquery('english', :query)) as rank, content_id
                FROM document_chunks
                WHERE search_vector @@ plainto_tsquery('english', :query)
                  AND content_id = ANY(:content_ids)
                ORDER BY rank DESC
                LIMIT :limit
            """)
            result = self._session.execute(
                stmt,
                {"query": query, "limit": limit, "content_ids": content_ids},
            )
        else:
            stmt = text("""
                SELECT id, ts_rank_cd(search_vector, plainto_tsquery('english', :query)) as rank, content_id
                FROM document_chunks
                WHERE search_vector @@ plainto_tsquery('english', :query)
                ORDER BY rank DESC
                LIMIT :limit
            """)
            result = self._session.execute(
                stmt,
                {"query": query, "limit": limit},
            )

        return [(row.id, row.rank, row.content_id) for row in result]


def _check_pg_search_available(session: Session) -> bool:
    """Check if pg_search extension is installed in the database."""
    try:
        result = session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'pg_search'"))
        return result.fetchone() is not None
    except Exception:
        logger.debug(
            "pg_search availability check failed, falling back to native FTS", exc_info=True
        )
        return False


def get_bm25_strategy(session: Session) -> BM25SearchStrategy:
    """Factory: select the best available BM25 strategy.

    Selection order:
    1. Explicit override via SEARCH_BM25_STRATEGY setting
    2. pg_search if available (ParadeDB BM25)
    3. PostgreSQL native FTS (fallback, works everywhere)

    Args:
        session: SQLAlchemy database session

    Returns:
        Configured BM25SearchStrategy instance
    """
    settings = get_settings()
    override = settings.search_bm25_strategy.lower()

    if override == "paradedb":
        logger.info("BM25 strategy: ParadeDB (explicit override)")
        return ParadeDBBM25Strategy(session)
    elif override == "native":
        logger.info("BM25 strategy: PostgreSQL Native FTS (explicit override)")
        return PostgresNativeFTSStrategy(session)

    # Auto-detect
    if _check_pg_search_available(session):
        logger.info("BM25 strategy: ParadeDB (auto-detected pg_search)")
        return ParadeDBBM25Strategy(session)

    logger.info("BM25 strategy: PostgreSQL Native FTS (pg_search not available)")
    return PostgresNativeFTSStrategy(session)
