# Tasks: Cross-Backend Hybrid Search with RRF

## 1. Database Schema

- [ ] 1.1 Create migration for `search_vector` TSVECTOR column on `document_chunks`
- [ ] 1.2 Create GIN index on `search_vector` column
- [ ] 1.3 Create trigger function for automatic `search_vector` updates
- [ ] 1.4 Create trigger on `document_chunks` table
- [ ] 1.5 Add backfill query for existing chunks
- [ ] 1.6 Test migration on all three backends (local, Supabase, Neon)

## 2. BM25 Strategy Abstraction

- [ ] 2.1 Define `BM25SearchStrategy` protocol in `src/services/search.py`
- [ ] 2.2 Implement `PostgresNativeFTSStrategy` using `tsvector`/`ts_rank_cd`
- [ ] 2.3 Implement `ParadeDBBM25Strategy` using pg_search `@@@` operator
- [ ] 2.4 Create `get_bm25_strategy()` factory in `src/services/search_factory.py`
- [ ] 2.5 Add `_check_pg_search_available()` helper function
- [ ] 2.6 Add `SEARCH_BM25_STRATEGY` setting to `src/config/settings.py`
- [ ] 2.7 Write unit tests for both strategies
- [ ] 2.8 Write integration tests for strategy auto-detection

## 3. Embedding Provider Abstraction

- [ ] 3.1 Define `EmbeddingProvider` protocol in `src/services/embedding.py`
- [ ] 3.2 Implement `OpenAIEmbeddingProvider` (text-embedding-3-small/large)
- [ ] 3.3 Implement `VoyageEmbeddingProvider` (voyage-3/voyage-3-lite)
- [ ] 3.4 Implement `CohereEmbeddingProvider` (embed-english-v3.0)
- [ ] 3.5 Implement `LocalEmbeddingProvider` (sentence-transformers)
- [ ] 3.6 Create `get_embedding_provider()` factory function
- [ ] 3.7 Add embedding configuration to `src/config/settings.py`:
  - `EMBEDDING_PROVIDER`
  - `EMBEDDING_MODEL`
  - `EMBEDDING_DIMENSIONS`
- [ ] 3.8 Add optional dependencies to `pyproject.toml`:
  - `sentence-transformers` (optional)
  - `voyageai` (optional)
  - `cohere` (optional)
- [ ] 3.9 Write unit tests for each provider (mocked API calls)
- [ ] 3.10 Write integration test for provider factory

## 4. Hybrid Search Service Updates

- [ ] 4.1 Update `HybridSearchService.__init__()` to accept injected strategies
- [ ] 4.2 Update `HybridSearchService.search()` to use injected BM25 strategy
- [ ] 4.3 Update `_vector_search()` to use injected embedding provider
- [ ] 4.4 Add strategy/provider metadata to `SearchResult` response
- [ ] 4.5 Write unit tests with mock strategies
- [ ] 4.6 Write integration tests for full hybrid search flow

## 5. API Endpoint Updates

- [ ] 5.1 Update `/api/v1/search` to use strategy factories
- [ ] 5.2 Add `backend_info` to search response metadata (strategy used, provider used)
- [ ] 5.3 Update OpenAPI schema with new response fields
- [ ] 5.4 Write API tests for search endpoint

## 6. Configuration and Documentation

- [ ] 6.1 Update `.env.example` with new configuration options
- [ ] 6.2 Update `docs/SETUP.md` with embedding provider setup
- [ ] 6.3 Create `docs/SEARCH.md` with:
  - Backend compatibility matrix
  - Embedding provider comparison (cost, quality, dimensions)
  - Configuration examples per deployment target
- [ ] 6.4 Update `CLAUDE.md` with search configuration patterns

## 7. Testing Across Backends

- [ ] 7.1 Create test fixtures for each backend type
- [ ] 7.2 Test native FTS strategy on Neon
- [ ] 7.3 Test pg_search strategy on Supabase
- [ ] 7.4 Test hybrid search RRF fusion with both strategies
- [ ] 7.5 Performance benchmark: native FTS vs pg_search quality comparison
