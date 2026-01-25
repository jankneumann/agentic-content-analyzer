# Change: Add Cross-Backend Hybrid Search with Reciprocal Rank Fusion

## Prerequisites

- **add-advanced-document-search**: This proposal builds upon the document search proposal, adding cross-backend compatibility for the BM25 component.
- **add-neon-provider**: This proposal addresses the backend compatibility gap where Neon lacks pg_search support.

## Why

The `add-advanced-document-search` proposal specifies pg_search (ParadeDB) for BM25 full-text search. However, pg_search is **not available on Neon**, one of our three supported database backends:

| Extension | Local PostgreSQL | Supabase | Neon |
|-----------|------------------|----------|------|
| **pgvector** | Install manually | Built-in | Built-in |
| **pg_search (ParadeDB)** | Install manually | Available | **Not available** |
| **PostgreSQL Native FTS** | Built-in | Built-in | Built-in |

This creates a portability problem: code written for pg_search won't work on Neon deployments.

Additionally, the embedding model selection should be configurable to allow:
- Cost optimization (cheaper models for development)
- Privacy requirements (local models for sensitive data)
- Quality tuning (better models for production)

## What Changes

### Cross-Backend BM25 Strategy

- **NEW**: `BM25SearchStrategy` protocol in `src/services/search.py` for pluggable BM25 implementations
- **NEW**: `PostgresNativeFTSStrategy` using `tsvector`/`ts_rank_cd` (works on all backends)
- **NEW**: `ParadeDBBM25Strategy` using pg_search `@@@` operator (higher quality where available)
- **NEW**: `get_bm25_strategy()` factory in `src/services/search_factory.py` that auto-detects backend
- **MODIFIED**: `HybridSearchService` to accept injected BM25 strategy
- **MODIFIED**: `DocumentChunk` model to add `search_vector` TSVECTOR column for native FTS
- **NEW**: Database trigger for automatic `search_vector` updates on chunk insert/update
- **NEW**: GIN index on `search_vector` column for fast native FTS queries

### Pluggable Embedding Providers

- **NEW**: `EmbeddingProvider` protocol in `src/services/embedding.py` for pluggable embeddings
- **NEW**: `OpenAIEmbeddingProvider` using text-embedding-3-small/large
- **NEW**: `VoyageEmbeddingProvider` using voyage-3/voyage-3-lite (optimized for RAG)
- **NEW**: `CohereEmbeddingProvider` using embed-english-v3.0
- **NEW**: `LocalEmbeddingProvider` using sentence-transformers (all-MiniLM-L6-v2, etc.)
- **NEW**: `get_embedding_provider()` factory with configuration-based selection
- **NEW**: Environment variables for embedding configuration:
  - `EMBEDDING_PROVIDER`: openai | voyage | cohere | local
  - `EMBEDDING_MODEL`: Model name within provider
  - `EMBEDDING_DIMENSIONS`: Vector dimensions (auto-detected or override)
- **MODIFIED**: `DocumentChunk.embedding` column to support variable dimensions via settings

## Impact

- **Affected specs**: `document-search` (modifies BM25 and embedding requirements)
- **Affected code**:
  - `src/services/search.py` - Add BM25 strategy protocol and implementations
  - `src/services/embedding.py` - Add embedding provider protocol and implementations
  - `src/services/search_factory.py` - New factory for backend and provider detection
  - `src/models/chunk.py` - Add `search_vector` column, configurable embedding dimensions
  - `src/config/settings.py` - Add embedding provider configuration
  - `alembic/versions/` - Migration for TSVECTOR column, trigger, and GIN index
  - `src/storage/providers/` - Add capability detection method
- **Dependencies**:
  - `sentence-transformers` (optional, for local embeddings)
  - `voyageai` (optional, for Voyage AI embeddings)
  - `cohere` (optional, for Cohere embeddings)
- **Breaking changes**: None (additive, maintains existing API)

## Related Proposals

- **add-advanced-document-search**: Parent proposal defining hybrid search architecture
- **add-neon-provider**: Provides Neon backend support this proposal relies on
- **add-supabase-cloud-database**: Established the provider abstraction pattern we extend

## Non-Goals

- Replacing pg_search entirely (it provides better BM25 quality where available)
- Adding non-PostgreSQL search backends (Elasticsearch, etc.)
- Changing the RRF fusion algorithm
- Fine-tuning or training custom embedding models
