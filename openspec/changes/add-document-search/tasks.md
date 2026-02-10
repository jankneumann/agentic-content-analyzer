# Tasks: Document Search Implementation

## Dependency Graph

```
A (Schema) ──┐
              ├──► C (Models) ──┬──► D (Chunking) ──┬──► G (Search Service) ──► H (API) ──► K (Docs)
B (Config) ──┘                  ├──► E (Embedding) ──┤                    │
                                ├──► F (BM25)  ──────┘                    │
                                └──► I (Reranking) ──────────────────────┘
                                                                          │
                                                      J (Ingestion) ◄─── D, E, G
                                                      L (Backfill)  ◄─── D, E
                                                      M (Lifecycle) ◄─── A, J
```

**Parallel width**: A+B (2) → C (1) → D+E+F+I (4) → G+L (2) → H+J (2, J sequential internally) → M (1) → K (1)

**Note on J**: Tasks J.2-J.6 modify separate ingestion files but share a common pattern via J.1. These MUST run sequentially (one agent) after G completes to avoid merge conflicts and ensure the shared `index_content()` helper is stable.

---

## A. Database Schema
> No dependencies. Files: `alembic/versions/`, `docker-compose.yml`

- [ ] A.1 Create Alembic migration to enable pgvector extension (`CREATE EXTENSION IF NOT EXISTS vector`)
- [ ] A.2 Create `document_chunks` table migration with:
  - `id` (Integer, PK, autoincrement)
  - `content_id` (Integer, FK to contents.id, NOT NULL, ON DELETE CASCADE)
  - `chunk_text` (Text, NOT NULL)
  - `chunk_index` (Integer, NOT NULL)
  - `section_path` (String, nullable)
  - `heading_text` (String, nullable)
  - `chunk_type` (String, NOT NULL) — "paragraph", "table", "code", "quote", "transcript"
  - `page_number` (Integer, nullable)
  - `start_char` (Integer, nullable)
  - `end_char` (Integer, nullable)
  - `timestamp_start` (Float, nullable)
  - `timestamp_end` (Float, nullable)
  - `deep_link_url` (String, nullable)
  - `embedding` (Vector, nullable) — dimensions from settings
  - `search_vector` (TSVECTOR, nullable)
  - `created_at` (DateTime, NOT NULL, server_default=now())
- [ ] A.3 Create indexes in the same migration:
  - Index on `content_id`
  - HNSW index on `embedding` column (`vector_cosine_ops`)
  - GIN index on `search_vector` column
  - Index on `chunk_type`
- [ ] A.4 Create TSVECTOR trigger function and trigger in migration:
  - `document_chunks_search_vector_update()` function
  - `BEFORE INSERT OR UPDATE OF chunk_text` trigger
- [ ] A.5 Conditionally create BM25 index if pg_search is available:
  - Check `pg_extension` table for pg_search
  - If available: `CREATE INDEX ... USING bm25 (chunk_text) WITH (key_field='id')`
  - If not: skip (native FTS via GIN index suffices)
- [ ] A.6 Test migration on local PostgreSQL (with and without pg_search)

## B. Configuration
> No dependencies. Files: `src/config/settings.py`, `src/config/sources.py`

- [ ] B.1 Add search configuration fields to `Settings`:
  - `embedding_provider: str = "openai"`
  - `embedding_model: str | None = None`
  - `embedding_dimensions: int = 1536`
  - `search_bm25_strategy: str | None = None` (auto-detect)
  - `search_rerank_enabled: bool = False`
  - `search_rerank_provider: str = "cohere"`
  - `search_rerank_model: str | None = None`
  - `search_rerank_top_k: int = 50`
  - `chunk_size_tokens: int = 512`
  - `chunk_overlap_tokens: int = 64`
  - `search_bm25_weight: float = 0.5`
  - `search_vector_weight: float = 0.5`
  - `search_rrf_k: int = 60`
  - `search_default_limit: int = 20`
  - `search_max_limit: int = 100`
  - `enable_search_indexing: bool = True`
- [ ] B.2 Add optional API key fields:
  - `voyage_api_key: str | None = None`
  - `cohere_api_key: str | None = None`
  - `jina_api_key: str | None = None`
- [ ] B.3 Add per-source chunking fields to `SourceDefaults` in `src/config/sources.py`:
  - `chunk_size_tokens: int | None = None` — override global default
  - `chunk_overlap_tokens: int | None = None` — override global default
  - `chunking_strategy: str | None = None` — force strategy (structured, youtube, markdown, section)
  - These cascade via existing SourceDefaults → per-file defaults → per-entry pattern
- [ ] B.4 Wire new settings into `profiles/base.yaml` with `${VAR:-}` interpolation
- [ ] B.5 Update `.env.example` with all new configuration options

## C. Data Models
> Depends on: A (table structure). Files: `src/models/chunk.py`, `src/models/search.py`

- [ ] C.1 Create `src/models/chunk.py` with `DocumentChunk` SQLAlchemy model matching A.2 schema
- [ ] C.2 Create `src/models/search.py` with Pydantic models:
  - `SearchQuery` (query, type, weights, filters, limit, offset)
  - `SearchFilter` (sources, date_from, date_to, publications, statuses, chunk_types)
  - `ChunkResult` (chunk_id, content, section, score, highlight, deep_link, chunk_type)
  - `SearchResult` (id, type, title, score, scores, matching_chunks, metadata)
  - `SearchResponse` (results, total, meta)
  - `SearchMeta` (bm25_strategy, embedding_provider, embedding_model, rerank_provider, rerank_model, query_time_ms, backend)
- [ ] C.3 Add `SearchType` enum (bm25, vector, hybrid)
- [ ] C.4 Add `ChunkType` enum (paragraph, table, code, quote, transcript, section)
- [ ] C.5 Write unit tests for model validation

## D. Chunking Service
> Depends on: C (DocumentChunk model). Files: `src/services/chunking.py`

- [ ] D.1 Create `src/services/chunking.py` with `ChunkingService` class
- [ ] D.2 Implement `chunk_content(content: Content, source_config: SourceEntry | None = None) -> list[DocumentChunk]` router method:
  - If `source_config.chunking_strategy` is set: use that strategy (structured, youtube, markdown, section)
  - Otherwise: dispatch based on `content.parser_used` (falls back to default markdown chunking for NULL or unrecognized parser)
  - If `source_config.chunk_size_tokens` / `chunk_overlap_tokens` is set: use those values; otherwise use global `Settings` defaults
  - Returns empty list with warning for empty/NULL `markdown_content`
- [ ] D.3 Implement `_chunk_structured_document()` for DoclingParser output:
  - Parse markdown heading hierarchy
  - Split on H1-H6 boundaries
  - Extract tables as separate chunks with caption context
  - Track page numbers from metadata
  - Handle oversized sections by paragraph splitting
- [ ] D.4 Implement `_chunk_youtube_transcript()` for YouTubeParser output:
  - Parse timestamped paragraphs from markdown
  - Preserve 30-second window groupings
  - Extract timestamp metadata (start, end)
  - Generate deep-link URLs with timestamp parameter
- [ ] D.5 Implement `_chunk_markdown()` for MarkItDownParser and default content:
  - Split on heading boundaries (H1/H2/H3)
  - Track section path (e.g., "# Intro > ## Setup")
  - Keep code blocks together
  - Handle list structures
- [ ] D.6 Implement `_chunk_section_markdown()` for summaries and digests:
  - Split on `## Section` headers
  - Preserve section type as chunk metadata
- [ ] D.7 Add chunk size validation and splitting for oversized chunks (>512 tokens)
- [ ] D.8 Add chunk overlap logic for context continuity (~64 tokens)
- [ ] D.9 Write unit tests for each chunking strategy with fixture markdown (include: empty content, single-line content, content with only headings, content exceeding max chunk size)
- [ ] D.10 Write unit tests for per-source chunking overrides:
  - Source with `chunk_size_tokens: 256` produces smaller chunks than default
  - Source with `chunking_strategy: youtube` forces YouTube chunking regardless of parser_used
  - Source without overrides uses global Settings defaults
  - Cascading: per-entry > per-file defaults > global Settings
- [ ] D.11 Write integration tests with realistic markdown fixtures matching parser output formats (DoclingParser heading/table structure, YouTubeParser timestamped paragraphs, MarkItDownParser heading/code structure)

## E. Embedding Provider Abstraction
> Depends on: B (settings), C (model for dimensions). Files: `src/services/embedding.py`

- [ ] E.1 Define `EmbeddingProvider` protocol in `src/services/embedding.py`
- [ ] E.2 Implement `OpenAIEmbeddingProvider` (text-embedding-3-small/large)
- [ ] E.3 Implement `VoyageEmbeddingProvider` (voyage-3/voyage-3-lite)
- [ ] E.4 Implement `CohereEmbeddingProvider` (embed-english-v3.0, with input_type handling)
- [ ] E.5 Implement `LocalEmbeddingProvider` (sentence-transformers, asyncio.to_thread)
- [ ] E.6 Create `get_embedding_provider()` factory function
- [ ] E.7 Implement `embed_chunks(chunks: list[DocumentChunk]) -> list[DocumentChunk]` convenience method
- [ ] E.8 Add text preprocessing (normalization, whitespace cleanup)
- [ ] E.9 Add retry logic with exponential backoff for rate limits
- [ ] E.10 Add token counting to validate chunk sizes before embedding
- [ ] E.11 Add optional dependencies to `pyproject.toml` (sentence-transformers, voyageai, cohere)
- [ ] E.12 Write unit tests for each provider (mocked API calls)
- [ ] E.13 Write integration test for provider factory

## F. BM25 Strategy Abstraction
> Depends on: A (TSVECTOR column), B (settings). Files: `src/services/search.py`, `src/services/search_factory.py`

- [ ] F.1 Define `BM25SearchStrategy` protocol in `src/services/search.py`
- [ ] F.2 Implement `PostgresNativeFTSStrategy` using `tsvector`/`ts_rank_cd`
- [ ] F.3 Implement `ParadeDBBM25Strategy` using pg_search `@@@` operator
- [ ] F.4 Create `get_bm25_strategy()` factory in `src/services/search_factory.py`
- [ ] F.5 Add `_check_pg_search_available()` helper function
- [ ] F.6 Write unit tests for both strategies (mocked DB)
- [ ] F.7 Write integration tests for strategy auto-detection

## I. Reranking Provider Abstraction
> Depends on: B (settings). Files: `src/services/reranking.py`

- [ ] I.1 Define `RerankProvider` protocol in `src/services/reranking.py`
- [ ] I.2 Implement `CohereRerankProvider` using Cohere Rerank API
- [ ] I.3 Implement `JinaRerankProvider` using Jina Rerank API
- [ ] I.4 Implement `LocalCrossEncoderProvider` using sentence-transformers `CrossEncoder` (asyncio.to_thread)
- [ ] I.5 Implement `LLMRerankProvider`:
  - Uses existing LLM router (`src/services/llm_router.py`); model from `SEARCH_RERANK_MODEL` setting
  - Structured prompt: "Rate the relevance of this document excerpt to the query on a scale of 0-10. Respond with only the number.\n\nQuery: {query}\n\nDocument: {chunk_text}"
  - Parse integer score from LLM response; default to 5 on parse failure
  - Score all top-K candidates with concurrent LLM calls (asyncio.gather with concurrency limit of 10)
  - Return sorted (index, score) tuples
- [ ] I.6 Create `get_rerank_provider()` factory function (returns None if disabled)
- [ ] I.7 Add optional dependencies to `pyproject.toml` (jina)
- [ ] I.8 Write unit tests for each provider (mocked API calls)
- [ ] I.9 Write integration test for provider factory and disabled-by-default behavior

## G. Search Service
> Depends on: D (chunking), E (embedding), F (BM25), I (reranking). Files: `src/services/search.py`

- [ ] G.1 Create `HybridSearchService` class accepting injected BM25 strategy, embedding provider, and rerank provider
- [ ] G.2 Implement `search()` method with parallel BM25 + vector execution
- [ ] G.3 Implement RRF fusion logic with configurable weights and k-parameter
- [ ] G.4 Implement optional cross-encoder reranking step (after RRF, before final results)
- [ ] G.5 Implement document aggregation from chunk results (group by content_id, best chunk score)
- [ ] G.6 Add search filtering with SQL joins to `contents` table:
  - G.6a: Implement source_type filter (JOIN contents, WHERE source_type IN ...)
  - G.6b: Implement date range filter (WHERE published_date BETWEEN ...)
  - G.6c: Implement publication and status filters
  - G.6d: Implement chunk_type filter (applied directly on document_chunks)
  - G.6e: Combine all filters with AND logic; filters applied BEFORE search ranking
  - G.6f: Write unit tests for each filter type individually and combined
- [ ] G.7 Add result highlighting:
  - G.7a: For BM25 and hybrid results: extract query terms, wrap literal matches in `<mark>` tags in chunk_text (HTML-escape chunk_text first)
  - G.7b: For vector-only results where no query terms match literally: set `highlight` to first 200 chars of chunk_text (no `<mark>` tags)
  - G.7c: Write unit tests for highlight extraction (overlapping terms, HTML escaping, no-match fallback)
- [ ] G.8 Add pagination support (offset, limit)
- [ ] G.9 Add deep-link generation for YouTube chunk results
- [ ] G.10 Build `SearchMeta` response object with strategy/provider/timing info
- [ ] G.11 Write unit tests with mock strategies and providers
- [ ] G.12 Write integration tests for full hybrid search flow

## H. API Endpoints
> Depends on: G (search service), C (Pydantic models). Files: `src/api/search_routes.py`, `src/api/app.py`

- [ ] H.1 Create `src/api/search_routes.py` with search router
- [ ] H.2 Implement `GET /api/v1/search` for simple queries (q, type, limit, offset params)
- [ ] H.3 Implement `POST /api/v1/search` for complex queries (JSON body with filters, weights)
- [ ] H.4 Implement `GET /api/v1/search/chunks/{chunk_id}` for chunk detail retrieval
- [ ] H.5 Add query validation and error handling (empty query, invalid type, limit bounds)
- [ ] H.6 Add request/response logging with telemetry integration
- [ ] H.7 Register router in `src/api/app.py`
- [ ] H.8 Write API tests for all endpoints

## J. Ingestion Integration
> Depends on: D (chunking), E (embedding), G (search service must be stable). Files: `src/ingestion/`, `src/services/indexing.py`
> **IMPORTANT**: J.2-J.6 MUST run sequentially (one agent) to avoid merge conflicts across ingestion files.

- [ ] J.1 Create `src/services/indexing.py` with shared `index_content(content: Content, db: Session, source_config: SourceEntry | None = None)` helper:
  - Passes `source_config` to `ChunkingService.chunk_content()` for per-source chunking overrides
  - Looks up source config from `settings.get_sources_config()` by matching `content.source_url` if `source_config` is not provided
  - Runs chunking + embedding in a separate transaction from content ingestion
  - Gated behind `ENABLE_SEARCH_INDEXING` setting
  - Catches all exceptions: logs error with content_id, does not re-raise
  - On chunking failure: content preserved, no chunks created
  - On embedding failure: chunks created without embeddings (BM25-searchable, not vector-searchable)
- [ ] J.2 Integrate `index_content()` into file ingestion (`src/ingestion/files.py`) — call after content commit. Depends on: J.1
- [ ] J.3 Integrate into YouTube ingestion (`src/ingestion/youtube.py`) — call after content commit. Depends on: J.2
- [ ] J.4 Integrate into Gmail ingestion (`src/ingestion/gmail.py`) — call after content commit. Depends on: J.3
- [ ] J.5 Integrate into RSS ingestion (`src/ingestion/rss.py`) — call after content commit. Depends on: J.4
- [ ] J.6 Integrate into Substack ingestion (`src/ingestion/substack.py`) — call after content commit. Depends on: J.5
- [ ] J.7 Write integration tests verifying:
  - Chunks are created on successful ingest
  - Content is preserved when chunking fails (mock ChunkingService to raise)
  - Content is preserved when embedding fails (mock EmbeddingProvider to raise)
  - No chunks created when `ENABLE_SEARCH_INDEXING=false`

## L. Backfill Command
> Depends on: D (chunking), E (embedding). Files: `src/scripts/backfill_chunks.py`

- [ ] L.1 Create `src/scripts/backfill_chunks.py` management command
- [ ] L.2 Implement batch processing:
  - Fetch content records that have NO associated chunks (LEFT JOIN document_chunks WHERE chunks.id IS NULL)
  - Also identify chunks with NULL embeddings (for retry after previous embedding failures)
  - Chunk from existing `Content.markdown_content` (do NOT re-fetch raw source or re-run parsers)
  - Embed in configurable batch sizes (default: 100 chunks per batch)
  - On per-chunk embedding failure: log error, store chunk without embedding (BM25-searchable), continue batch
- [ ] L.3 Add rate limiting for embedding API calls (configurable delay between batches)
- [ ] L.4 Add resume capability (track last processed content_id, skip already-chunked content)
- [ ] L.5 Add progress reporting (processed/total, chunks created, ETA)
- [ ] L.6 Add dry-run mode
- [ ] L.7 Add CLI entry point (`aca manage backfill-chunks`)
- [ ] L.8 Write unit tests for backfill logic

## M. Chunk Lifecycle Management
> Depends on: A (CASCADE FK), J.6 (all ingestion integrations complete, `index_content()` stable). Files: `src/services/indexing.py`, `src/models/chunk.py`

- [ ] M.1 Verify `ON DELETE CASCADE` works: deleting a Content record deletes all its chunks
- [ ] M.2 Implement rechunking on content update:
  - M.2a: Add SQLAlchemy `@event.listens_for(Content, "after_update")` listener that detects changes to `markdown_content` (compare `inspect(instance).attrs.markdown_content.history`)
  - M.2b: When `markdown_content` changes and `ENABLE_SEARCH_INDEXING=true`: delete existing chunks for that content_id, then call `index_content()`
  - M.2c: When non-content fields change (status, tags): no-op (listener checks attribute history)
- [ ] M.3 Write tests:
  - M.3a: Cascade delete: delete Content → verify all chunks deleted
  - M.3b: Rechunking: update markdown_content → verify old chunks deleted + new chunks created
  - M.3c: No-op: update status → verify chunks unchanged
  - M.3d: Rechunking disabled: update markdown_content with ENABLE_SEARCH_INDEXING=false → verify chunks unchanged

## K. Documentation
> Depends on: all above. Files: `docs/`, `CLAUDE.md`

- [ ] K.1 Create `docs/SEARCH.md` with:
  - Architecture overview (BM25 strategy + embedding provider + RRF + optional reranking)
  - Backend compatibility matrix
  - Embedding provider comparison (cost, quality, dimensions)
  - Reranking provider comparison
  - Configuration examples per deployment target
  - Search API examples (GET, POST, filters)
  - Backfill instructions
  - Troubleshooting guide
- [ ] K.2 Update `docs/ARCHITECTURE.md` with search architecture and chunking strategy
- [ ] K.3 Update `CLAUDE.md` with search commands and configuration
- [ ] K.4 Update `docs/MODEL_CONFIGURATION.md` with embedding and reranking model options
