"""Hybrid search service combining BM25 keyword search with vector semantic search.

Uses Reciprocal Rank Fusion (RRF) to merge rankings from both methods,
with optional cross-encoder reranking for quality improvement.

The service aggregates chunk-level results to document-level, returning
content records with their best-matching chunks.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
import time
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.models.search import (
    ChunkResult,
    SearchMeta,
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchScores,
    SearchType,
)
from src.services.embedding import EmbeddingProvider, get_embedding_provider
from src.services.reranking import RerankProvider, get_rerank_provider
from src.services.search_strategy import BM25SearchStrategy, get_bm25_strategy

logger = logging.getLogger(__name__)


class HybridSearchService:
    """Combines BM25 keyword search and vector semantic search using RRF.

    Architecture:
        1. BM25 search → keyword relevance ranking (chunk IDs + scores)
        2. Vector search → semantic similarity ranking (chunk IDs + scores)
        3. RRF fusion → combined ranking using weighted reciprocal ranks
        4. Optional reranking → cross-encoder rescoring of top candidates
        5. Document aggregation → group chunks by content_id, best score wins
        6. Enrichment → join with Content table for titles, dates, sources
    """

    def __init__(
        self,
        session: Session,
        bm25_strategy: BM25SearchStrategy | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        rerank_provider: RerankProvider | None = None,
    ) -> None:
        self._session = session
        self._bm25 = bm25_strategy or get_bm25_strategy(session)
        self._embedder = embedding_provider or get_embedding_provider()
        self._reranker = rerank_provider  # None = use factory (respects enabled setting)
        self._reranker_resolved = rerank_provider is not None

    def _get_reranker(self) -> RerankProvider | None:
        """Lazy-resolve reranker from factory if not explicitly provided."""
        if not self._reranker_resolved:
            self._reranker = get_rerank_provider()
            self._reranker_resolved = True
        return self._reranker

    async def search(self, query: SearchQuery) -> SearchResponse:
        """Execute hybrid search and return aggregated document results.

        Args:
            query: Search query with type, filters, weights, pagination.

        Returns:
            SearchResponse with results, total count, and execution metadata.
        """
        settings = get_settings()
        start_time = time.monotonic()

        bm25_weight = query.bm25_weight or settings.search_bm25_weight
        vector_weight = query.vector_weight or settings.search_vector_weight
        rrf_k = settings.search_rrf_k

        # Pre-filter: get content_ids matching filters (if any)
        content_ids = self._resolve_content_filter(query)

        # Fetch more candidates than needed for fusion quality
        search_limit = min((query.limit + query.offset) * 5, settings.search_max_limit * 5)

        # Execute search based on type
        # BM25 strategies use synchronous DB calls, so we run them in a thread
        # to avoid blocking the async event loop.
        if query.type == SearchType.BM25:
            bm25_results = await asyncio.to_thread(
                self._bm25.search, query.query, search_limit, content_ids
            )
            vector_results: list[tuple[int, float]] = []
        elif query.type == SearchType.VECTOR:
            bm25_results = []
            vector_results = await self._vector_search(
                query.query, limit=search_limit, content_ids=content_ids
            )
        else:
            # Hybrid: run both in parallel
            bm25_results, vector_results = await asyncio.gather(
                asyncio.to_thread(self._bm25.search, query.query, search_limit, content_ids),
                self._vector_search(query.query, limit=search_limit, content_ids=content_ids),
            )

        # Build raw score maps: chunk_id -> score
        bm25_scores: dict[int, float] = {cid: score for cid, score in bm25_results}
        vector_scores: dict[int, float] = {cid: score for cid, score in vector_results}

        # Merge all candidate chunk IDs
        all_chunk_ids = set(bm25_scores.keys()) | set(vector_scores.keys())
        if not all_chunk_ids:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return SearchResponse(
                results=[],
                total=0,
                meta=self._build_meta(elapsed_ms),
            )

        # Calculate RRF scores
        rrf_scores = self._calculate_rrf(
            bm25_scores,
            vector_scores,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
            k=rrf_k,
        )

        # Optional reranking
        rerank_scores: dict[int, float] = {}
        reranker = self._get_reranker()
        if reranker and rrf_scores:
            rerank_scores = await self._rerank_chunks(
                reranker,
                query.query,
                rrf_scores,
            )
            # Use rerank scores as final ordering
            final_scores = rerank_scores
        else:
            final_scores = rrf_scores

        # Aggregate to document level (includes pagination)
        results, total = self._aggregate_to_documents(
            final_scores,
            bm25_scores,
            vector_scores,
            rrf_scores,
            rerank_scores,
            query=query,
        )

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        return SearchResponse(
            results=results,
            total=total,
            meta=self._build_meta(elapsed_ms),
        )

    async def _vector_search(
        self,
        query: str,
        limit: int = 100,
        content_ids: list[int] | None = None,
    ) -> list[tuple[int, float]]:
        """Search chunks by embedding cosine similarity."""
        try:
            query_embedding = await self._embedder.embed(query, is_query=True)
        except Exception:
            logger.warning(
                "Vector embedding failed at query time, returning empty results",
                exc_info=True,
            )
            return []

        # Normalize to list[float] for pgvector str() compatibility
        vec = list(query_embedding) if not isinstance(query_embedding, list) else query_embedding

        # Build SQL for vector similarity search
        if content_ids:
            stmt = text("""
                SELECT dc.id, 1 - (dc.embedding <=> CAST(:query_vec AS vector)) as similarity
                FROM document_chunks dc
                WHERE dc.embedding IS NOT NULL
                  AND dc.content_id = ANY(:content_ids)
                ORDER BY dc.embedding <=> CAST(:query_vec AS vector)
                LIMIT :limit
            """)
            result = self._session.execute(
                stmt,
                {
                    "query_vec": str(vec),
                    "limit": limit,
                    "content_ids": content_ids,
                },
            )
        else:
            stmt = text("""
                SELECT dc.id, 1 - (dc.embedding <=> CAST(:query_vec AS vector)) as similarity
                FROM document_chunks dc
                WHERE dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> CAST(:query_vec AS vector)
                LIMIT :limit
            """)
            result = self._session.execute(
                stmt,
                {"query_vec": str(vec), "limit": limit},
            )

        return [(row.id, row.similarity) for row in result]

    def _resolve_content_filter(self, query: SearchQuery) -> list[int] | None:
        """Pre-filter content IDs based on search filters.

        Returns None if no filters are applied (search all content).
        Returns empty list if filters match nothing (short-circuit to empty results).
        """
        if not query.filters:
            return None

        f = query.filters
        has_filter = (
            f.source_types
            or f.date_from
            or f.date_to
            or f.publications
            or f.statuses
            or f.chunk_types
        )
        if not has_filter:
            return None

        # Build dynamic WHERE clause
        conditions: list[str] = []
        params: dict = {}

        if f.source_types:
            conditions.append("c.source_type::text = ANY(:source_types)")
            params["source_types"] = f.source_types
        if f.date_from:
            conditions.append("c.published_date >= :date_from")
            params["date_from"] = f.date_from
        if f.date_to:
            conditions.append("c.published_date <= :date_to")
            params["date_to"] = f.date_to
        if f.publications:
            conditions.append("c.publication = ANY(:publications)")
            params["publications"] = f.publications
        if f.statuses:
            conditions.append("c.status::text = ANY(:statuses)")
            params["statuses"] = f.statuses

        # chunk_types filter is applied directly on chunks, not via content pre-filter
        # But we still need content_ids for the BM25/vector queries
        if f.chunk_types and not conditions:
            # Only chunk_type filter — need to get content_ids from chunks
            chunk_stmt = text("""
                SELECT DISTINCT content_id FROM document_chunks
                WHERE chunk_type = ANY(:chunk_types)
            """)
            result = self._session.execute(chunk_stmt, {"chunk_types": f.chunk_types})
            return [row.content_id for row in result]

        if not conditions:
            return None

        # conditions contains only hardcoded column comparisons — safe to join
        where = " AND ".join(conditions)
        if f.chunk_types:
            # Join through chunks to also apply chunk_type filter
            stmt = text(
                f"SELECT DISTINCT c.id FROM contents c"  # noqa: S608
                f" JOIN document_chunks dc ON dc.content_id = c.id"
                f" WHERE {where} AND dc.chunk_type = ANY(:chunk_types)"
            )
            params["chunk_types"] = f.chunk_types
        else:
            stmt = text(f"SELECT c.id FROM contents c WHERE {where}")  # noqa: S608

        result = self._session.execute(stmt, params)
        return [row.id for row in result]

    def _calculate_rrf(
        self,
        bm25_scores: dict[int, float],
        vector_scores: dict[int, float],
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5,
        k: int = 60,
    ) -> dict[int, float]:
        """Calculate Reciprocal Rank Fusion scores.

        RRF formula: score = Σ(weight_i / (k + rank_i))

        Ranks are 1-indexed (best result = rank 1).
        """
        # Build rank maps (sorted by score descending, 1-indexed)
        bm25_ranked = sorted(bm25_scores.items(), key=lambda x: x[1], reverse=True)
        vector_ranked = sorted(vector_scores.items(), key=lambda x: x[1], reverse=True)

        bm25_rank = {chunk_id: rank + 1 for rank, (chunk_id, _) in enumerate(bm25_ranked)}
        vector_rank = {chunk_id: rank + 1 for rank, (chunk_id, _) in enumerate(vector_ranked)}

        # Calculate RRF for each chunk
        all_ids = set(bm25_rank.keys()) | set(vector_rank.keys())
        rrf: dict[int, float] = {}

        for chunk_id in all_ids:
            score = 0.0
            if chunk_id in bm25_rank:
                score += bm25_weight / (k + bm25_rank[chunk_id])
            if chunk_id in vector_rank:
                score += vector_weight / (k + vector_rank[chunk_id])
            rrf[chunk_id] = score

        return rrf

    async def _rerank_chunks(
        self,
        reranker: RerankProvider,
        query: str,
        rrf_scores: dict[int, float],
    ) -> dict[int, float]:
        """Rerank top candidates using cross-encoder or LLM."""
        settings = get_settings()
        top_k = settings.search_rerank_top_k

        # Take top-K by RRF score for reranking
        sorted_chunks = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        candidates = sorted_chunks[:top_k]
        candidate_ids = [cid for cid, _ in candidates]

        if not candidate_ids:
            return {}

        # Fetch chunk texts for reranking
        stmt = text("""
            SELECT id, chunk_text FROM document_chunks
            WHERE id = ANY(:ids)
        """)
        result = self._session.execute(stmt, {"ids": candidate_ids})
        chunk_texts = {row.id: row.chunk_text for row in result}

        # Preserve order matching candidate_ids
        documents = [chunk_texts.get(cid, "") for cid in candidate_ids]

        try:
            reranked = await reranker.rerank(query, documents, top_k=top_k)
            # Map back to chunk IDs with rerank scores
            return {
                candidate_ids[idx]: score for idx, score in reranked if idx < len(candidate_ids)
            }
        except Exception:
            logger.warning("Reranking failed, falling back to RRF scores", exc_info=True)
            return dict(candidates)

    def _aggregate_to_documents(
        self,
        final_scores: dict[int, float],
        bm25_scores: dict[int, float],
        vector_scores: dict[int, float],
        rrf_scores: dict[int, float],
        rerank_scores: dict[int, float],
        query: SearchQuery,
    ) -> tuple[list[SearchResult], int]:
        """Group chunk results by content_id and enrich with content metadata.

        Optimized to fetch heavy metadata only for the final page of documents.

        Returns:
            Tuple of (list of SearchResult, total document count)
        """
        if not final_scores:
            return [], 0

        chunk_ids = list(final_scores.keys())

        # 1. Fetch lightweight mapping of chunk_id -> content_id for ALL candidates
        # This allows us to aggregate scores and group by document without loading heavy data
        stmt = text("SELECT id, content_id FROM document_chunks WHERE id = ANY(:chunk_ids)")
        mapping_rows = self._session.execute(stmt, {"chunk_ids": chunk_ids}).fetchall()

        # 2. Group chunk scores by content_id
        content_chunk_scores: dict[int, list[tuple[int, float]]] = defaultdict(list)
        for row in mapping_rows:
            chunk_id = row.id
            content_id = row.content_id
            score = final_scores.get(chunk_id, 0.0)
            content_chunk_scores[content_id].append((chunk_id, score))

        # 3. Calculate document scores (max chunk score) and sort documents
        # Structure: (content_id, doc_score, top_chunks)
        document_candidates: list[tuple[int, float, list[tuple[int, float]]]] = []

        for content_id, chunks in content_chunk_scores.items():
            # Sort chunks by score descending
            chunks.sort(key=lambda x: x[1], reverse=True)
            best_score = chunks[0][1] if chunks else 0.0

            # Keep top 3 chunks for snippets
            top_chunks = chunks[:3]
            document_candidates.append((content_id, best_score, top_chunks))

        # Sort documents by score descending
        document_candidates.sort(key=lambda x: (-x[1], x[0]))

        total = len(document_candidates)

        # 4. Apply pagination to get the slice of documents to return
        paginated_docs = document_candidates[query.offset : query.offset + query.limit]

        if not paginated_docs:
            return [], total

        # 5. Fetch full metadata ONLY for the chunks we need to display
        # Collect chunk IDs from the top chunks of the selected documents
        chunks_to_fetch = [
            chunk_id
            for _, _, top_chunks in paginated_docs
            for chunk_id, _ in top_chunks
        ]

        stmt = text("""
            SELECT
                dc.id as chunk_id,
                dc.content_id,
                substr(dc.chunk_text, 1, 500) as chunk_text,
                dc.section_path,
                dc.heading_text,
                dc.chunk_type,
                dc.deep_link_url,
                c.title,
                c.source_type,
                c.publication,
                c.published_date
            FROM document_chunks dc
            JOIN contents c ON c.id = dc.content_id
            WHERE dc.id = ANY(:chunk_ids)
        """)
        result = self._session.execute(stmt, {"chunk_ids": chunks_to_fetch})
        rows = list(result)

        # Extract query terms for highlighting
        query_terms = _extract_query_terms(query.query)

        # Group fetched chunk data by content_id
        content_chunks: dict[int, list] = defaultdict(list)
        content_meta: dict[int, dict] = {}

        for row in rows:
            cid = row.content_id
            chunk_id = row.chunk_id

            if cid not in content_meta:
                content_meta[cid] = {
                    "title": row.title,
                    "source_type": row.source_type,
                    "publication": row.publication,
                    "published_date": row.published_date,
                }

            # Build chunk result
            highlight = _generate_highlight(
                row.chunk_text,
                query_terms,
                query.type,
            )

            chunk_result = ChunkResult(
                chunk_id=chunk_id,
                content=row.chunk_text,  # Already truncated by DB
                section=row.section_path or row.heading_text,
                score=final_scores.get(chunk_id, 0.0),
                highlight=highlight,
                deep_link=row.deep_link_url,
                chunk_type=row.chunk_type,
            )

            content_chunks[cid].append(chunk_result)

        # Build document-level results
        results: list[SearchResult] = []

        # Iterate over paginated_docs to preserve order
        for content_id, best_score, _ in paginated_docs:
            if content_id not in content_meta:
                continue

            meta = content_meta[content_id]
            chunks = content_chunks.get(content_id, [])

            # Sort chunks by final score descending (re-sort the fetched objects)
            chunks.sort(key=lambda c: c.score, reverse=True)

            # Collect per-method scores from the best chunk (first one)
            best_chunk_id = chunks[0].chunk_id if chunks else None
            scores = SearchScores(
                bm25=bm25_scores.get(best_chunk_id) if best_chunk_id else None,
                vector=vector_scores.get(best_chunk_id) if best_chunk_id else None,
                rrf=rrf_scores.get(best_chunk_id) if best_chunk_id else None,
                rerank=rerank_scores.get(best_chunk_id) if best_chunk_id else None,
            )

            results.append(
                SearchResult(
                    id=content_id,
                    title=meta["title"],
                    score=best_score,
                    scores=scores,
                    source=meta["source_type"],
                    publication=meta["publication"],
                    published_date=meta["published_date"],
                    matching_chunks=chunks,  # Already limited to top 3 during fetch selection
                )
            )

        return results, total

    def _build_meta(self, elapsed_ms: int) -> SearchMeta:
        """Build search execution metadata."""
        settings = get_settings()
        reranker = self._get_reranker()

        return SearchMeta(
            bm25_strategy=self._bm25.name,
            embedding_provider=self._embedder.name,
            embedding_model=settings.embedding_model,
            rerank_provider=reranker.name if reranker else None,
            rerank_model=settings.search_rerank_model if reranker else None,
            query_time_ms=elapsed_ms,
            backend=settings.database_provider,
        )


# --- Highlight helpers ---


def _extract_query_terms(query: str) -> list[str]:
    """Extract individual terms from query for highlighting."""
    # Split on whitespace and punctuation, keep alphanumeric tokens
    terms = re.findall(r"\w+", query.lower())
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for t in terms:
        if t not in seen and len(t) > 1:  # Skip single-char terms
            seen.add(t)
            unique.append(t)
    return unique


def _generate_highlight(
    chunk_text: str,
    query_terms: list[str],
    search_type: SearchType,
) -> str:
    """Generate highlighted snippet with <mark> tags around matching terms.

    For BM25/hybrid: wraps literal query term matches in <mark> tags.
    For vector-only with no literal matches: returns first 200 chars (no marks).
    """
    # Use first 500 chars for highlight context
    snippet = chunk_text[:500]

    # HTML-escape the snippet first
    escaped = html.escape(snippet)

    # Try to find and mark query terms (case-insensitive)
    marked = escaped
    found_any = False
    for term in query_terms:
        # Use word boundary matching for cleaner highlights
        pattern = re.compile(rf"(\b{re.escape(html.escape(term))}\w*)", re.IGNORECASE)
        replacement = r"<mark>\1</mark>"
        new_marked, count = pattern.subn(replacement, marked)
        if count > 0:
            found_any = True
            marked = new_marked

    if found_any:
        return marked[:600]  # Allow extra space for <mark> tags

    # Vector-only with no literal matches: plain snippet
    if search_type == SearchType.VECTOR:
        return escaped[:200]

    # BM25/hybrid but no literal match (stemming match, etc.)
    return escaped[:200]
