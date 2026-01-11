# Tasks: Advanced Document Search Implementation

## 1. Database Infrastructure

- [ ] 1.1 Add pg_search and pgvector extensions to Docker Compose PostgreSQL
- [ ] 1.2 Create Alembic migration to enable extensions (`CREATE EXTENSION IF NOT EXISTS pg_search; CREATE EXTENSION IF NOT EXISTS vector;`)
- [ ] 1.3 Add `embedding` column (vector type) to newsletters table
- [ ] 1.4 Add `embedding` column to documents table
- [ ] 1.5 Add `embedding` column to newsletter_summaries table
- [ ] 1.6 Create BM25 index on newsletters (title, raw_text, sender, publication)
- [ ] 1.7 Create BM25 index on documents (filename, markdown_content)
- [ ] 1.8 Create BM25 index on newsletter_summaries (executive_summary)
- [ ] 1.9 Create HNSW vector indexes on embedding columns
- [ ] 1.10 Update Docker Compose to use paradedb/paradedb image or install extensions

## 2. Configuration

- [ ] 2.1 Add search configuration to `src/config/settings.py`:
  - `EMBEDDING_MODEL` (default: text-embedding-3-small)
  - `EMBEDDING_PROVIDER` (openai, local)
  - `EMBEDDING_DIMENSIONS` (1536 for OpenAI)
  - `SEARCH_BM25_WEIGHT` (default: 0.5)
  - `SEARCH_VECTOR_WEIGHT` (default: 0.5)
  - `SEARCH_RRF_K` (default: 60)
  - `SEARCH_DEFAULT_LIMIT` (default: 20)
  - `SEARCH_MAX_LIMIT` (default: 100)
- [ ] 2.2 Add embedding model to model registry if needed
- [ ] 2.3 Document configuration in `docs/MODEL_CONFIGURATION.md`

## 3. Embedding Service

- [ ] 3.1 Create `src/services/embedding.py` with EmbeddingService class
- [ ] 3.2 Implement OpenAI embedding generation (text-embedding-3-small)
- [ ] 3.3 Add text preprocessing (truncation, normalization)
- [ ] 3.4 Add batch embedding support for efficiency
- [ ] 3.5 Add retry logic and error handling
- [ ] 3.6 Add caching for repeated texts (optional)
- [ ] 3.7 Write unit tests for embedding service

## 4. Search Service

- [ ] 4.1 Create `src/services/search.py` with SearchService class
- [ ] 4.2 Implement BM25 search using pg_search `@@@` operator
- [ ] 4.3 Implement vector similarity search using pgvector `<=>` operator
- [ ] 4.4 Implement hybrid search with RRF combination
- [ ] 4.5 Add search filtering (source, date range, publication, status)
- [ ] 4.6 Add result highlighting/snippet generation
- [ ] 4.7 Add pagination support (offset, limit)
- [ ] 4.8 Add search across multiple tables (newsletters, summaries, documents)
- [ ] 4.9 Write unit tests for search service
- [ ] 4.10 Write integration tests with real database

## 5. Search Models

- [ ] 5.1 Create Pydantic models in `src/models/search.py`:
  - `SearchQuery` (query, type, weights, filters, limit, offset)
  - `SearchFilter` (sources, date_from, date_to, publications, statuses)
  - `SearchResult` (id, type, title, snippet, score, scores, metadata)
  - `SearchResponse` (results, total, query_time_ms)
- [ ] 5.2 Add SearchType enum (bm25, vector, hybrid)

## 6. API Endpoints

- [ ] 6.1 Create `src/api/search_routes.py` with search router
- [ ] 6.2 Implement `GET /api/v1/search` for simple queries
- [ ] 6.3 Implement `POST /api/v1/search` for complex queries
- [ ] 6.4 Add query validation and error handling
- [ ] 6.5 Add request/response logging
- [ ] 6.6 Register router in `src/api/app.py`
- [ ] 6.7 Write API tests

## 7. Ingestion Integration

- [ ] 7.1 Update `src/ingestion/gmail.py` to generate embeddings on ingest
- [ ] 7.2 Update `src/ingestion/substack.py` to generate embeddings on ingest
- [ ] 7.3 Update `src/ingestion/files.py` to generate embeddings on ingest
- [ ] 7.4 Update `src/ingestion/youtube.py` to generate embeddings on ingest
- [ ] 7.5 Update summarizer to generate embeddings for summaries
- [ ] 7.6 Add embedding generation as optional (feature flag)

## 8. Backfill Migration

- [ ] 8.1 Create management command `python -m src.scripts.backfill_embeddings`
- [ ] 8.2 Implement batch processing with progress tracking
- [ ] 8.3 Add rate limiting to avoid API throttling
- [ ] 8.4 Add resume capability (track last processed ID)
- [ ] 8.5 Add dry-run mode for testing
- [ ] 8.6 Document backfill process in CLAUDE.md

## 9. Documentation

- [ ] 9.1 Update `docs/ARCHITECTURE.md` with search architecture
- [ ] 9.2 Add search API documentation
- [ ] 9.3 Update CLAUDE.md with search-related commands
- [ ] 9.4 Add search troubleshooting guide

## 10. Testing & Validation

- [ ] 10.1 Run full test suite
- [ ] 10.2 Test search with sample queries
- [ ] 10.3 Verify BM25 relevance scoring
- [ ] 10.4 Verify vector similarity scoring
- [ ] 10.5 Verify hybrid RRF combination
- [ ] 10.6 Performance testing with realistic data volume
- [ ] 10.7 Test edge cases (empty results, special characters, long queries)
