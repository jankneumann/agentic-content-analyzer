"""Hybrid search service combining BM25 keyword search with vector semantic search.

Uses Reciprocal Rank Fusion (RRF) to merge rankings from both methods,
with optional cross-encoder reranking for quality improvement.

The service aggregates chunk-level results to document-level, returning
content records with their best-matching chunks.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import re
import time
from collections import defaultdict

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.models.chunk import DocumentChunk
from src.models.content import Content
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
            vector_results: list[tuple[int, float, int]] = []
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
        # And track chunk -> content mapping
        bm25_scores: dict[int, float] = {}
        vector_scores: dict[int, float] = {}
        chunk_content_map: dict[int, int] = {}

        for cid, score, content_id in bm25_results:
            bm25_scores[cid] = score
            chunk_content_map[cid] = content_id

        for cid, score, content_id in vector_results:
            vector_scores[cid] = score
            chunk_content_map[cid] = content_id

        # Early return if no candidates at all
        if not bm25_scores and not vector_scores:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return SearchResponse(
                results=[],
                total=0,
                meta=self._build_meta(elapsed_ms),
            )

        # Tree search: identify tree-indexed content and run LLM search
        tree_scores: dict[int, float] = {}
        tree_reasoning_map: dict[int, str] = {}  # content_id → reasoning
        tree_weight = settings.search_tree_weight

        if settings.tree_search_enabled and chunk_content_map:
            tree_content_ids = self._find_tree_indexed_content(
                list(set(chunk_content_map.values()))
            )
            if tree_content_ids:
                # Pre-rank by existing BM25/vector scores
                content_prescores: dict[int, float] = {}
                for cid, score in bm25_scores.items():
                    content_id = chunk_content_map.get(cid)
                    if content_id in tree_content_ids:
                        content_prescores[content_id] = max(
                            content_prescores.get(content_id, 0.0), score
                        )
                for cid, score in vector_scores.items():
                    content_id = chunk_content_map.get(cid)
                    if content_id in tree_content_ids:
                        content_prescores[content_id] = max(
                            content_prescores.get(content_id, 0.0), score
                        )

                # Select top-N for tree search
                sorted_tree = sorted(content_prescores.items(), key=lambda x: x[1], reverse=True)
                top_tree_ids = [cid for cid, _ in sorted_tree[: settings.tree_search_max_documents]]

                try:
                    tree_results = await self._tree_search(query.query, top_tree_ids)
                    for chunk_id, content_id, score, reasoning in tree_results:
                        tree_scores[chunk_id] = score
                        chunk_content_map[chunk_id] = content_id
                        if reasoning:
                            tree_reasoning_map[content_id] = reasoning
                except Exception:
                    logger.warning(
                        "Tree search failed, falling back to flat search",
                        exc_info=True,
                    )

        # Calculate RRF scores (BM25 + vector + tree)
        rrf_scores = self._calculate_rrf_multi(
            [bm25_scores, vector_scores, tree_scores],
            weights=[bm25_weight, vector_weight, tree_weight if tree_scores else 0.0],
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

        # Aggregate scores to document level in memory first
        # This avoids fetching content for chunks that won't be displayed (pagination optimization)
        doc_scores: dict[int, float] = {}
        doc_chunks: dict[int, list[int]] = defaultdict(list)

        for chunk_id, score in final_scores.items():
            if chunk_id in chunk_content_map:
                cid = chunk_content_map[chunk_id]
                # Document score is max of its chunk scores
                doc_scores[cid] = max(doc_scores.get(cid, 0.0), score)
                doc_chunks[cid].append(chunk_id)

        # Sort documents by score descending, tie-break by ID
        sorted_docs = sorted(doc_scores.items(), key=lambda x: (-x[1], x[0]))
        total = len(sorted_docs)

        # Apply pagination to DOCUMENTS, not chunks
        paginated_docs = sorted_docs[query.offset : query.offset + query.limit]

        # Identify chunks to fetch (top 3 per document for the paginated docs)
        chunks_to_fetch: dict[int, float] = {}
        for cid, _ in paginated_docs:
            # Get chunks for this doc, sort by score descending
            chunks = doc_chunks[cid]
            chunks.sort(key=lambda cid: final_scores[cid], reverse=True)
            # Take top 3
            for chunk_id in chunks[:3]:
                chunks_to_fetch[chunk_id] = final_scores[chunk_id]

        # Aggregate only the needed chunks
        results = self._aggregate_to_documents(
            chunks_to_fetch,
            bm25_scores,
            vector_scores,
            rrf_scores,
            rerank_scores,
            query=query,
            tree_reasoning_map=tree_reasoning_map,
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
    ) -> list[tuple[int, float, int]]:
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
                SELECT dc.id, 1 - (dc.embedding <=> CAST(:query_vec AS vector)) as similarity, dc.content_id
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
                SELECT dc.id, 1 - (dc.embedding <=> CAST(:query_vec AS vector)) as similarity, dc.content_id
                FROM document_chunks dc
                WHERE dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> CAST(:query_vec AS vector)
                LIMIT :limit
            """)
            result = self._session.execute(
                stmt,
                {"query_vec": str(vec), "limit": limit},
            )

        return [(row.id, row.similarity, row.content_id) for row in result]

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

        # Build query using SQLAlchemy Core/ORM to enable index usage (avoiding text casts)
        stmt = select(Content.id)

        # Apply filters on Content
        if f.source_types:
            stmt = stmt.where(Content.source_type.in_(f.source_types))

        if f.date_from:
            stmt = stmt.where(Content.published_date >= f.date_from)

        if f.date_to:
            stmt = stmt.where(Content.published_date <= f.date_to)

        if f.publications:
            stmt = stmt.where(Content.publication.in_(f.publications))

        if f.statuses:
            stmt = stmt.where(Content.status.in_(f.statuses))

        # Apply chunk type filter
        if f.chunk_types:
            # Join with DocumentChunk
            stmt = stmt.join(DocumentChunk).where(DocumentChunk.chunk_type.in_(f.chunk_types))
            stmt = stmt.distinct()

        result = self._session.execute(stmt)
        return [row[0] for row in result]

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
        tree_reasoning_map: dict[int, str] | None = None,
    ) -> list[SearchResult]:
        """Group chunk results by content_id and enrich with content metadata.

        Args:
            final_scores: Dict of chunk_id -> score for the specific chunks to be returned.
                         This should be pre-filtered for pagination (e.g. top 3 chunks
                         for the top 20 documents).
            bm25_scores: Full map of BM25 scores (for all candidates)
            vector_scores: Full map of vector scores
            rrf_scores: Full map of RRF scores
            rerank_scores: Full map of rerank scores
            query: The original search query
        """
        if not final_scores:
            return []

        chunk_ids = list(final_scores.keys())

        # Fetch chunk data + content metadata in one query
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
        result = self._session.execute(stmt, {"chunk_ids": chunk_ids})
        rows = list(result)

        # Extract query terms for highlighting
        query_terms = _extract_query_terms(query.query)

        # Group chunks by content_id
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

        for content_id, chunks in content_chunks.items():
            meta = content_meta[content_id]

            # Sort chunks by final score descending
            chunks.sort(key=lambda c: c.score, reverse=True)

            # Document score = best chunk score
            best_score = chunks[0].score if chunks else 0.0

            # Collect per-method scores from the best chunk
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
                    matching_chunks=chunks[:3],  # Top 3 chunks per document
                    tree_reasoning=(
                        tree_reasoning_map.get(content_id) if tree_reasoning_map else None
                    ),
                )
            )

        # Sort results by document score descending, tiebreak by content_id
        results.sort(key=lambda r: (-r.score, r.id))

        return results

    def _find_tree_indexed_content(self, content_ids: list[int]) -> set[int]:
        """Find which content_ids have tree index chunks."""
        if not content_ids:
            return set()
        result = self._session.execute(
            text("""
                SELECT DISTINCT content_id
                FROM document_chunks
                WHERE content_id = ANY(:ids) AND tree_depth IS NOT NULL
            """),
            {"ids": content_ids},
        )
        return {row.content_id for row in result}

    async def _tree_search(
        self,
        query: str,
        content_ids: list[int],
    ) -> list[tuple[int, int, float, str | None]]:
        """Run LLM-based tree search for qualifying documents.

        Returns: list of (chunk_id, content_id, score, reasoning) tuples.
        """
        settings = get_settings()
        results: list[tuple[int, int, float, str | None]] = []

        async def _search_single(content_id: int) -> list[tuple[int, int, float, str | None]]:
            try:
                return await asyncio.wait_for(
                    self._tree_search_single(query, content_id),
                    timeout=settings.tree_search_timeout_seconds,
                )
            except TimeoutError:
                logger.warning(f"Tree search timed out for content {content_id}")
                return []
            except Exception:
                logger.warning(
                    f"Tree search failed for content {content_id}",
                    exc_info=True,
                )
                return []

        # Run tree search concurrently (bounded by tree_search_max_documents)
        all_results = await asyncio.gather(*[_search_single(cid) for cid in content_ids])
        for result_list in all_results:
            results.extend(result_list)

        return results

    async def _tree_search_single(
        self,
        query: str,
        content_id: int,
    ) -> list[tuple[int, int, float, str | None]]:
        """Run tree search for a single document."""
        settings = get_settings()

        # Load tree structure
        tree_json, id_mapping = self._load_tree_structure(content_id)
        if not tree_json or not id_mapping:
            return []

        # Call LLM
        from src.config.models import ModelStep, get_model_config
        from src.services.llm_router import LLMRouter

        model_config = get_model_config()
        model = model_config.get_model_for_step(ModelStep.TREE_SEARCH)
        router = LLMRouter(model_config)

        prompt = (
            f"Question: {query}\n\n"
            f"Document tree structure:\n{tree_json}\n\n"
            'Reply as JSON: {"thinking": "your reasoning", "node_list": ["N001", "N002"]}'
        )

        llm_response = await router.generate(
            model=model,
            system_prompt=(
                "You are a document analysis expert. Given a tree structure, "
                "identify nodes likely to contain the answer. "
                "Respond with ONLY valid JSON."
            ),
            user_prompt=prompt,
            max_tokens=512,
            temperature=0.0,
        )
        response = llm_response.content

        if not response:
            return []

        # Parse and validate response
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            logger.warning(f"Tree search returned invalid JSON for content {content_id}")
            return []

        node_list = parsed.get("node_list", [])
        if not isinstance(node_list, list):
            logger.warning(f"Tree search node_list is not a list for content {content_id}")
            return []

        thinking = parsed.get("thinking", "")

        # Validate and resolve node IDs
        valid_node_ids: list[str] = []
        node_id_pattern = re.compile(r"^N\d{3,}$")
        for nid in node_list:
            if not isinstance(nid, str) or not node_id_pattern.match(nid):
                continue
            if nid not in id_mapping:
                continue
            valid_node_ids.append(nid)

        # Cap at max selected nodes
        valid_node_ids = valid_node_ids[: settings.tree_search_max_selected_nodes]

        if not valid_node_ids:
            return []

        # Resolve to DB chunk IDs and fetch leaf content
        selected_chunk_ids = [id_mapping[nid] for nid in valid_node_ids]

        # Get leaf chunks under selected nodes (tree chunks only)
        leaf_chunks = self._get_tree_leaves(selected_chunk_ids, content_id)

        # Score by position in node_list
        results: list[tuple[int, int, float, str | None]] = []
        for rank, chunk_id in enumerate(leaf_chunks):
            score = 1.0 / (rank + 1)
            results.append((chunk_id, content_id, score, thinking if rank == 0 else None))

        return results

    def _load_tree_structure(self, content_id: int) -> tuple[str, dict[str, int]]:
        """Load tree structure as JSON with compact IDs.

        Returns: (tree_json_string, {compact_id: db_chunk_id})
        """
        result = self._session.execute(
            text("""
                SELECT id, chunk_text, heading_text, tree_depth, parent_chunk_id, is_summary
                FROM document_chunks
                WHERE content_id = :cid AND tree_depth IS NOT NULL
                ORDER BY tree_depth, chunk_index
            """),
            {"cid": content_id},
        )
        rows = list(result)
        if not rows:
            return "", {}

        # Build id mapping and tree structure
        id_mapping: dict[str, int] = {}
        nodes: dict[int, dict] = {}

        for counter, row in enumerate(rows, start=1):
            compact_id = f"N{counter:03d}"
            id_mapping[compact_id] = row.id

            nodes[row.id] = {
                "node_id": compact_id,
                "title": row.heading_text or f"Section {compact_id}",
                "summary": row.chunk_text[:200] if row.is_summary and row.chunk_text else None,
                "depth": row.tree_depth,
                "parent_db_id": row.parent_chunk_id,
                "children": [],
            }

        # Build hierarchy
        roots: list[dict] = []
        for _db_id, node in nodes.items():
            parent_id = node.pop("parent_db_id")
            if parent_id and parent_id in nodes:
                nodes[parent_id]["children"].append(node)
            elif parent_id:
                # Orphaned node — parent not in current tree (data corruption)
                logger.warning(
                    f"Tree node {node['node_id']} references missing parent {parent_id} "
                    f"for content {content_id}, treating as root"
                )
                roots.append(node)
            else:
                roots.append(node)

        # Serialize via json.dumps (defense against injection in titles)
        def _clean_node(node: dict) -> dict:
            result = {
                "node_id": node["node_id"],
                "title": node["title"],
            }
            if node.get("summary"):
                result["summary"] = node["summary"]
            if node["children"]:
                result["children"] = [_clean_node(c) for c in node["children"]]
            return result

        clean_roots = [_clean_node(r) for r in roots]
        tree_json = json.dumps(clean_roots, indent=2)

        return tree_json, id_mapping

    def _get_tree_leaves(self, selected_chunk_ids: list[int], content_id: int) -> list[int]:
        """Get leaf chunk IDs under selected tree nodes."""
        if not selected_chunk_ids:
            return []

        # Get selected chunks and their descendants (tree chunks only)
        result = self._session.execute(
            text("""
                WITH RECURSIVE tree AS (
                    SELECT id, parent_chunk_id
                    FROM document_chunks
                    WHERE id = ANY(:ids) AND tree_depth IS NOT NULL
                    UNION ALL
                    SELECT dc.id, dc.parent_chunk_id
                    FROM document_chunks dc
                    JOIN tree t ON dc.parent_chunk_id = t.id
                    WHERE dc.tree_depth IS NOT NULL
                )
                SELECT DISTINCT t.id
                FROM tree t
                JOIN document_chunks dc ON dc.id = t.id
                WHERE dc.is_summary = false AND dc.content_id = :cid
            """),
            {"ids": selected_chunk_ids, "cid": content_id},
        )
        return [row.id for row in result]

    def _calculate_rrf_multi(
        self,
        score_maps: list[dict[int, float]],
        weights: list[float],
        k: int = 60,
    ) -> dict[int, float]:
        """Calculate RRF across multiple score sources.

        Generalizes _calculate_rrf to support N sources (BM25 + vector + tree).
        """
        # Build rank maps
        rank_maps: list[dict[int, int]] = []
        for scores in score_maps:
            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            rank_maps.append({cid: rank + 1 for rank, (cid, _) in enumerate(ranked)})

        # Collect all chunk IDs
        all_ids: set[int] = set()
        for scores in score_maps:
            all_ids |= set(scores.keys())

        # Calculate RRF
        rrf: dict[int, float] = {}
        for chunk_id in all_ids:
            score = 0.0
            for rank_map, weight in zip(rank_maps, weights, strict=True):
                if chunk_id in rank_map and weight > 0:
                    score += weight / (k + rank_map[chunk_id])
            rrf[chunk_id] = score

        return rrf

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
