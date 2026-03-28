## Why

Our current chunking system treats all documents equally: split on heading boundaries into ~512-token chunks, embed them, and retrieve via hybrid BM25 + vector search. This works well for short-to-medium content (newsletters, RSS, blog posts) but falls short on long, structured documents like arXiv PDFs, technical reports, and documentation.

The core problem: **similarity is not relevance**. A question like "How did the year-over-year operating margin change?" requires finding data in two separate sections. Vector search finds the most similar chunk to the query, but cannot reason about which sections to combine. This is why traditional vector RAG scores ~50% on benchmarks like FinanceBench while reasoning-based approaches (PageIndex) achieve 98.7%.

With the upcoming `add-academic-paper-insights` change bringing arXiv papers into the pipeline, this gap will become more acute. Academic papers are 10K-80K+ tokens with deep heading hierarchies, cross-references, and appendices — exactly the content type where flat chunking fails.

We propose a hybrid model inspired by [VectifyAI's PageIndex](https://github.com/VectifyAI/PageIndex) that adds **hierarchical tree indexing and LLM-based tree search** for long structured documents, while keeping our existing flat chunk + hybrid search as the default for short content.

## What Changes

### Phase 1: Chunk Thinning (Quick Win)

- Add tree-thinning logic to `MarkdownChunkingStrategy` and `StructuredChunkingStrategy` — merge undersized chunks (below a configurable `min_node_tokens` threshold) upward into adjacent/parent chunks to reduce over-fragmentation
- Add `min_node_tokens` setting (default: 50) to `Settings`
- No schema changes, no new dependencies, no LLM calls

### Phase 2: Tree Index Strategy

- Add `parent_chunk_id` (nullable self-referential FK), `tree_depth` (Integer), and `is_summary` (Boolean) columns to `document_chunks` via Alembic migration
- Create `TreeIndexChunkingStrategy` that builds a hierarchical tree from heading structure (H1-H6), calls LLM to generate node summaries for internal nodes, and stores tree relationships via `parent_chunk_id`
- Auto-select tree index strategy when content exceeds `tree_index_min_tokens` (default: 8000) AND has heading depth >= 3
- Add `MODEL_TREE_SUMMARIZATION` model config for node summary LLM calls
- Flat chunks are ALWAYS created alongside tree index — tree is an additive layer, not a replacement

### Phase 3: Tree Search Retrieval

- Add tree search prompt template managed via `aca prompts` system
- Implement `_tree_search()` in `HybridSearchService`: loads tree structure (summaries only, no text) for matching content, sends to LLM for reasoning-based node selection, fetches text from selected leaf nodes
- Add query routing: documents with tree indexes use tree search; others use existing BM25 + vector
- Merge tree search results with vector results via existing RRF fusion
- Add `MODEL_TREE_SEARCH` model config and `tree_search_enabled` setting

## Capabilities

### New Capabilities

- `tree-index-chunking`: Hierarchical tree index construction for long structured documents, with LLM-generated node summaries and parent-child chunk relationships
- `tree-search-retrieval`: LLM reasoning-based retrieval that navigates document tree structure to find relevant sections, complementing existing hybrid BM25 + vector search

### Modified Capabilities

- `document-search`: Add tree search as an additional retrieval path alongside BM25 and vector search, with automatic routing based on document index type
- `document-search` (Semantic Document Chunking): Add `TreeIndexChunkingStrategy` to the strategy registry, add chunk thinning to existing strategies, add `min_node_tokens` / `tree_index_min_tokens` settings
- `content-ingestion`: Extend `index_content()` to build tree indexes for qualifying documents during ingestion

## Impact

- **Backend**: ~340 LOC new code across `chunking.py`, `search.py`, `indexing.py`, `settings.py`, `chunk.py`, plus Alembic migration and prompt template
- **Frontend**: No changes — tree search results appear as standard `SearchResult` records with `matching_chunks`
- **Dependencies**: None — uses existing `llm_router`, `tiktoken`, prompt management system
- **Database**: One Alembic migration adding 3 nullable columns to `document_chunks`
- **Cost**: Phase 1 is free. Phase 2 adds ~1 LLM call per long document during indexing (node summaries). Phase 3 adds 1-2 LLM calls per search query that hits tree-indexed content
- **Risk**: Low — all phases are additive; existing flat chunk + hybrid search continues to work unchanged. Tree features are opt-in via content length thresholds

## Design Decisions

1. **Write custom code, don't depend on PageIndex** — PageIndex uses `litellm` (we use `llm_router`), `PyPDF2` (we use Docling), has no vector search (we want to augment, not replace), and pins conflicting dependency versions. The novel algorithms are ~340 lines to reimplement.

2. **Tree index is additive, not replacing flat chunks** — Flat chunks are always created for BM25 + vector search. Tree index is a parallel structure that enables LLM-based reasoning retrieval. This ensures no regression for existing content types.

3. **Cost-aware routing** — Tree search requires LLM calls per query. Only used for documents that meet the length + structure threshold. Short content (90% of our corpus) continues to use the existing zero-LLM-cost retrieval path.

4. **Phase 1 is independently valuable** — Chunk thinning reduces fragmentation for all content types with zero additional cost. Can ship and validate before committing to Phases 2-3.
