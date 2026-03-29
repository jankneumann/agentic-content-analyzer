## Why

Our current chunking system treats all documents equally: split on heading boundaries into ~512-token chunks, embed them, and retrieve via hybrid BM25 + vector search. This works well for short-to-medium content (newsletters, RSS, blog posts) but falls short on long, structured documents like arXiv PDFs, technical reports, and documentation.

The core problem: **similarity is not relevance**. A question like "How did the year-over-year operating margin change?" requires finding data in two separate sections. Vector search finds the most similar chunk to the query, but cannot reason about which sections to combine. This is why traditional vector RAG scores ~50% on benchmarks like FinanceBench while reasoning-based approaches (PageIndex) achieve 98.7%.

With the upcoming `add-academic-paper-insights` change bringing arXiv papers into the pipeline, this gap will become more acute. Academic papers are 10K-80K+ tokens with deep heading hierarchies, cross-references, and appendices — exactly the content type where flat chunking fails.

We propose a hybrid model inspired by [VectifyAI's PageIndex](https://github.com/VectifyAI/PageIndex) that adds **hierarchical tree indexing and LLM-based tree search** for long structured documents, while keeping our existing flat chunk + hybrid search as the default for short content.

## What Changes

### Phase 1: Chunk Thinning (Quick Win)

- Add tree-thinning logic to `MarkdownChunkingStrategy` and `StructuredChunkingStrategy` — merge undersized PARAGRAPH/SECTION chunks (below a configurable `min_node_tokens` threshold) into adjacent chunks to reduce over-fragmentation
- TABLE and CODE chunks are exempt from thinning to preserve semantic classification
- Add `min_node_tokens` setting (default: 50) to `Settings`
- No schema changes, no new dependencies, no LLM calls

### Phase 2: Tree Index Strategy

- Add `parent_chunk_id` (nullable self-referential FK), `tree_depth` (Integer), and `is_summary` (Boolean) columns to `document_chunks` via Alembic migration. Flat chunks: `tree_depth=NULL`; tree roots: `tree_depth=0`
- Create `TreeIndexChunkingStrategy` (sync, matching existing protocol) that builds a hierarchical tree from heading structure (H1-H6) and creates placeholder summary chunks. LLM summarization runs as async post-processing in `index_content()`, parallelizing sibling nodes via `asyncio.gather()`
- Reuse existing `ChunkType.SECTION` for summary nodes — no PG enum migration needed
- Auto-select tree index strategy when content exceeds `tree_index_min_tokens` (default: 8000) AND has heading depth >= 3
- Add `ModelStep.TREE_SUMMARIZATION` to model config enum (not a Settings field) — follows existing model resolution pattern
- Flat chunks are ALWAYS created alongside tree index — tree is an additive layer, not a replacement

### Phase 3: Tree Search Retrieval

- Add tree search prompt template managed via `aca prompts` system, using compact sequential node IDs (N001, N002) mapped back to DB chunk IDs
- Implement `_tree_search()` in `HybridSearchService`: loads tree structure (summaries only, no text) for matching content, sends to LLM for reasoning-based node selection, fetches text from selected leaf nodes
- Add query routing: documents with tree indexes use tree search; others use existing BM25 + vector
- Latency safeguards: `tree_search_max_documents` (3), `tree_search_timeout_seconds` (5s), concurrent execution via `asyncio.gather()`
- Add `tree_reasoning: str | None` to `SearchResult` for LLM reasoning traces
- Merge tree search results with vector results via existing RRF fusion
- Add `ModelStep.TREE_SEARCH` to model config enum and `tree_search_enabled` setting
- Telemetry spans for tree search and summarization LLM calls via existing observability provider

## Capabilities

### Modified Capabilities

- `document-search` (Semantic Document Chunking): Add chunk thinning to `MarkdownChunkingStrategy` and `StructuredChunkingStrategy`, add `TreeIndexChunkingStrategy` to the strategy registry, add `min_node_tokens` / `tree_index_min_tokens` / `tree_index_min_heading_depth` settings, add tree column schema (`parent_chunk_id`, `tree_depth`, `is_summary`), add LLM summarization for internal tree nodes
- `document-search` (Tree Search Retrieval — new requirement): Add LLM-based tree search as an additional retrieval path alongside BM25 and vector search, with automatic routing based on document index type, compact node IDs, timeout/fallback safeguards, and `tree_reasoning` on SearchResult
- `document-search` (Tree Index Backfill — new requirement): Add `backfill-tree-index` management command for existing content

## Impact

- **Backend**: ~400 LOC new code across `chunking.py`, `search.py`, `indexing.py`, `settings.py`, `models.py`, `chunk.py`, `search.py` (models), plus Alembic migration and prompt template
- **Frontend**: No changes — tree search results appear as standard `SearchResult` records with `matching_chunks` (new optional `tree_reasoning` field is backward-compatible)
- **Dependencies**: None — uses existing `llm_router`, `tiktoken`, prompt management system
- **Database**: One Alembic migration adding 3 nullable columns to `document_chunks`
- **Cost**: Phase 1 is free. Phase 2 adds ~1 LLM call per long document during indexing (node summaries). Phase 3 adds 1-2 LLM calls per search query that hits tree-indexed content
- **Risk**: Low — all phases are additive; existing flat chunk + hybrid search continues to work unchanged. Tree features are opt-in via content length thresholds
- **Failure trade-off**: Tree summarization uses all-or-nothing rollback — if LLM fails for any node, the entire tree is deleted (flat chunks preserved). Content remains fully searchable via BM25 + vector. This avoids partial trees with missing summaries that would produce unpredictable tree search behavior.

## Design Decisions

1. **Write custom code, don't depend on PageIndex** — PageIndex uses `litellm` (we use `llm_router`), `PyPDF2` (we use Docling), has no vector search (we want to augment, not replace), and pins conflicting dependency versions. The novel algorithms are ~340 lines to reimplement.

2. **Tree index is additive, not replacing flat chunks** — Flat chunks are always created for BM25 + vector search. Tree index is a parallel structure that enables LLM-based reasoning retrieval. This ensures no regression for existing content types.

3. **Cost-aware routing** — Tree search requires LLM calls per query. Only used for documents that meet the length + structure threshold. Short content (90% of our corpus) continues to use the existing zero-LLM-cost retrieval path.

4. **Phase 1 is independently valuable** — Chunk thinning reduces fragmentation for all content types with zero additional cost. Can ship and validate before committing to Phases 2-3.

5. **Sync chunking, async summarization** — The `ChunkingStrategy` protocol is sync-only and all 5 existing strategies are synchronous. Rather than changing the protocol, tree summarization runs as async post-processing in `index_content()`, following the existing async embedding pattern. This avoids breaking changes to the chunking interface.

6. **Reuse ChunkType.SECTION for summaries** — Adding a new `SUMMARY` value to the PG-backed `ChunkType` StrEnum would require an `ALTER TYPE ... ADD VALUE` migration (a documented gotcha). Instead, summary nodes use the existing `SECTION` type, disambiguated by the `is_summary` boolean.

7. **Latency-bounded tree search** — Tree search adds LLM calls per query. Bounded by: max 3 documents per query (`tree_search_max_documents`), 5-second per-document timeout (`tree_search_timeout_seconds`), and concurrent execution. Timeouts fall back to flat search gracefully.

8. **ModelStep enum for model config** — Model selection uses the existing `ModelStep` enum → env var → DB override → YAML default resolution pattern (not Settings fields), keeping consistency with all other pipeline model configurations.
