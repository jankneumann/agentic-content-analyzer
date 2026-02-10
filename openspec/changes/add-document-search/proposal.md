# Change: Add Document Search with Hybrid BM25 + Vector Search

## Prerequisites

- **refactor-unified-content-model**: This proposal assumes the unified Content model with markdown-first storage is implemented. The chunking service operates on `Content.markdown_content` rather than separate Newsletter/Document tables.

## Why

The current search implementation is limited to simple ILIKE pattern matching on content titles only, missing:
- Full-text search across document content (markdown, summaries, themes)
- Semantic/conceptual search that finds related content even without exact keyword matches
- Relevance ranking beyond simple substring matching
- Combined search strategies that leverage both lexical precision and semantic understanding

Users need to efficiently discover relevant content across thousands of ingested newsletters, uploaded documents, and YouTube transcripts using natural language queries.

Additionally, the system supports multiple PostgreSQL backends (local, Supabase, Neon) with different extension availability — pg_search (ParadeDB) is unavailable on Neon, requiring a portable BM25 abstraction. Embedding model selection should also be configurable to support cost optimization, privacy requirements, and quality tuning across deployment environments.

Search endpoints are designed to be consumed by both human-facing UIs (CLI and web) and programmatic agents. Response schemas include metadata sufficient for agent reasoning about result quality and strategy selection.

## What Changes

### Core Search Infrastructure

- **Create `document_chunks` table** to store chunks with structural metadata (section paths, page numbers, timestamps, deep-links)
- **Implement semantic chunking** leveraging existing parser infrastructure (DoclingParser, YouTubeParser, MarkItDownParser) to split documents into meaningful units
- **Implement hybrid search** combining BM25 document search with chunk-level vector similarity search
- **Add Reciprocal Rank Fusion (RRF)** to combine and rerank results from multiple search methods
- **Add optional cross-encoder reranking** using SLM/fast-LLM or dedicated cross-encoder models after RRF for improved final result quality
- **Create chunking service** with parser-aware strategies for PDFs, YouTube transcripts, markdown, and HTML
- **Support per-source chunking configuration** via `sources.d/` YAML files (chunk size, overlap, and strategy overrides cascading through existing defaults hierarchy)
- **Define chunk lifecycle rules** (rechunk/re-embed on content updates; delete chunks on content removal)
- **Add search API endpoints** for unified search with chunk-level highlighting and navigation

### Cross-Backend BM25 Strategy

- **Add `BM25SearchStrategy` protocol** for pluggable BM25 implementations
- **Implement `ParadeDBBM25Strategy`** using pg_search `@@@` operator (higher quality, local + Supabase)
- **Implement `PostgresNativeFTSStrategy`** using `tsvector`/`ts_rank_cd` (works on all backends)
- **Add backend auto-detection factory** that selects the best available strategy
- **Add TSVECTOR column, trigger, and GIN index** for native FTS support

### Pluggable Embedding Pipeline

- **Add `EmbeddingProvider` protocol** for pluggable embedding providers
- **Implement 4 providers**: OpenAI, Voyage AI, Cohere, Local (sentence-transformers)
- **Add embedding provider factory** with configuration-based selection
- **Support variable vector dimensions** based on provider/model selection
- **Create embedding pipeline** to generate and store chunk embeddings at ingestion time

### Integration and Backfill

- **Integrate chunking/embedding into ingestion pipeline** (non-blocking, feature-flagged)
- **Add backfill command** for existing documents with batch processing, rate limiting, and resume
- **Add search configuration** for model selection, chunk sizing, weighting, and filtering

## Impact

- **Affected specs**: New capability (document-search)
- **Affected code**:
  - `src/services/chunking.py` — New chunking service with parser-aware strategies
  - `src/services/embedding.py` — Embedding provider protocol, implementations, and factory
  - `src/services/search.py` — BM25 strategy protocol, implementations, hybrid search with RRF
  - `src/services/search_factory.py` — Backend detection and strategy/provider factories
  - `src/services/reranking.py` — Reranking provider protocol, implementations, and factory
  - `src/services/indexing.py` — Shared `index_content()` helper for ingest-time chunking/embedding
  - `src/models/chunk.py` — DocumentChunk SQLAlchemy model
  - `src/models/search.py` — Search request/response Pydantic models
  - `src/api/search_routes.py` — New search endpoints
  - `src/config/settings.py` — Search, chunking, and embedding configuration
  - `src/config/sources.py` — Per-source chunking override fields in SourceDefaults
  - `alembic/versions/` — Migration for document_chunks, pgvector extension, TSVECTOR trigger
  - `src/ingestion/` — Integration of chunking/embedding at ingest time
  - `src/scripts/backfill_chunks.py` — Backfill management command
- **Dependencies**:
  - pgvector extension (available on all backends)
  - pg_search extension (optional, ParadeDB — local + Supabase only)
  - OpenAI API (default embedding provider)
  - `sentence-transformers` (optional, for local embeddings and local cross-encoder)
  - `voyageai` (optional, for Voyage AI embeddings)
  - `cohere` (optional, for Cohere embeddings and Cohere Rerank)
  - `jina` (optional, for Jina Rerank)
- **Breaking changes**: None (additive feature)

## Non-Goals

- Replacing pg_search entirely (it provides better BM25 quality where available)
- Adding non-PostgreSQL search backends (Elasticsearch, Typesense)
- Real-time search (within milliseconds of ingestion) — slight delay acceptable
- Federated search across Neo4j knowledge graph (separate capability)
- Query suggestions/autocomplete (future enhancement)
- Search analytics and query logging (future enhancement)
- Multi-language search (English-only initially)
- Fine-tuning or training custom embedding models
- Internal MCP tool exposure (agents consume the REST API directly)
