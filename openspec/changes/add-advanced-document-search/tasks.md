# Tasks: Advanced Document Search Implementation

## 1. Database Infrastructure

- [ ] 1.1 Add pg_search and pgvector extensions to Docker Compose PostgreSQL
- [ ] 1.2 Create Alembic migration to enable extensions (`CREATE EXTENSION IF NOT EXISTS pg_search; CREATE EXTENSION IF NOT EXISTS vector;`)
- [ ] 1.3 Create `document_chunks` table with:
  - `id` (Integer, PK)
  - `source_type` (String) - "newsletter", "document", "summary", "digest"
  - `source_id` (Integer) - FK to source table
  - `content` (Text) - Chunk text content
  - `chunk_index` (Integer) - Order within document
  - `section_path` (String, nullable) - Heading hierarchy
  - `heading_text` (String, nullable) - Nearest heading
  - `chunk_type` (String) - "paragraph", "table", "code", "quote", "transcript"
  - `page_number` (Integer, nullable) - For PDFs
  - `start_char`, `end_char` (Integer, nullable) - Character offsets
  - `timestamp_start`, `timestamp_end` (Float, nullable) - For YouTube
  - `deep_link_url` (String, nullable) - Direct link to chunk
  - `embedding` (Vector(1536)) - pgvector column
  - `created_at` (DateTime)
- [ ] 1.4 Create indexes on document_chunks:
  - Composite index on (source_type, source_id)
  - HNSW index on embedding column
  - Index on chunk_type
- [ ] 1.5 Create BM25 index on newsletters (title, raw_text, sender, publication)
- [ ] 1.6 Create BM25 index on documents (filename, markdown_content)
- [ ] 1.7 Create BM25 index on document_chunks (content)
- [ ] 1.8 Update Docker Compose to use paradedb/paradedb image or install extensions

## 2. Configuration

- [ ] 2.1 Add search configuration to `src/config/settings.py`:
  - `EMBEDDING_MODEL` (default: text-embedding-3-small)
  - `EMBEDDING_PROVIDER` (openai, local)
  - `EMBEDDING_DIMENSIONS` (1536 for OpenAI)
  - `CHUNK_SIZE_TOKENS` (default: 512)
  - `CHUNK_OVERLAP_TOKENS` (default: 64)
  - `SEARCH_BM25_WEIGHT` (default: 0.5)
  - `SEARCH_VECTOR_WEIGHT` (default: 0.5)
  - `SEARCH_RRF_K` (default: 60)
  - `SEARCH_DEFAULT_LIMIT` (default: 20)
  - `SEARCH_MAX_LIMIT` (default: 100)
- [ ] 2.2 Add embedding model to model registry if needed
- [ ] 2.3 Document configuration in `docs/MODEL_CONFIGURATION.md`

## 3. Chunking Service

- [ ] 3.1 Create `src/models/chunk.py` with DocumentChunk SQLAlchemy model
- [ ] 3.2 Create `src/services/chunking.py` with ChunkingService class
- [ ] 3.3 Implement base chunking interface with `chunk_document(content: DocumentContent) -> list[DocumentChunk]`
- [ ] 3.4 Implement `_chunk_structured_document()` for DoclingParser output:
  - Parse markdown heading hierarchy
  - Split on H1/H2/H3 boundaries
  - Extract tables as separate chunks with caption context
  - Track page numbers from metadata
  - Handle paragraph splitting for oversized sections
- [ ] 3.5 Implement `_chunk_youtube_transcript()` for YouTubeParser output:
  - Parse timestamped paragraphs from markdown
  - Preserve 30-second window groupings
  - Extract timestamp metadata (start, end)
  - Generate deep-link URLs with timestamp parameter
- [ ] 3.6 Implement `_chunk_markdown()` for MarkItDownParser output:
  - Split on heading boundaries
  - Track section path (e.g., "# Intro > ## Setup")
  - Keep code blocks together
  - Handle list structures
- [ ] 3.7 Implement `_chunk_newsletter_html()` for raw HTML content:
  - Parse semantic HTML elements (article, section, h1-h6, blockquote)
  - Fall back to paragraph splitting
- [ ] 3.8 Implement `_chunk_summary()` for newsletter summaries:
  - Split on section markers ([EXECUTIVE_SUMMARY], [KEY_THEMES], etc.)
  - Preserve theme tags
- [ ] 3.9 Add chunk size validation and splitting for oversized chunks
- [ ] 3.10 Add chunk overlap logic for context continuity
- [ ] 3.11 Write unit tests for each chunking strategy
- [ ] 3.12 Write integration tests with real parser output

## 4. Embedding Service

- [ ] 4.1 Create `src/services/embedding.py` with EmbeddingService class
- [ ] 4.2 Implement OpenAI embedding generation (text-embedding-3-small)
- [ ] 4.3 Add text preprocessing (normalization, whitespace cleanup)
- [ ] 4.4 Add batch embedding support for efficiency (up to 2048 texts per request)
- [ ] 4.5 Add retry logic with exponential backoff for rate limits
- [ ] 4.6 Implement `embed_chunks(chunks: list[DocumentChunk]) -> list[DocumentChunk]`
- [ ] 4.7 Add token counting to validate chunk sizes before embedding
- [ ] 4.8 Write unit tests for embedding service

## 5. Search Service

- [ ] 5.1 Create `src/services/search.py` with SearchService class
- [ ] 5.2 Implement BM25 document search using pg_search `@@@` operator
- [ ] 5.3 Implement chunk-level vector similarity search using pgvector `<=>` operator
- [ ] 5.4 Implement hybrid search with RRF combination:
  - BM25 on documents → document rankings
  - Vector on chunks → chunk rankings (aggregated to documents)
  - RRF fusion of document rankings
- [ ] 5.5 Add search filtering (source, date range, publication, status)
- [ ] 5.6 Add result highlighting with chunk context
- [ ] 5.7 Add pagination support (offset, limit)
- [ ] 5.8 Implement document aggregation from chunk results:
  - Group chunks by source document
  - Return top N matching chunks per document
  - Calculate document score from chunk scores
- [ ] 5.9 Add deep-link generation for YouTube chunk results
- [ ] 5.10 Write unit tests for search service
- [ ] 5.11 Write integration tests with real database

## 6. Search Models

- [ ] 6.1 Create Pydantic models in `src/models/search.py`:
  - `SearchQuery` (query, type, weights, filters, limit, offset, include_chunks)
  - `SearchFilter` (sources, date_from, date_to, publications, statuses, chunk_types)
  - `ChunkResult` (chunk_id, content, section, score, highlight, deep_link, chunk_type)
  - `SearchResult` (id, type, title, score, scores, matching_chunks, metadata)
  - `SearchResponse` (results, total, query_time_ms)
- [ ] 6.2 Add SearchType enum (bm25, vector, hybrid)
- [ ] 6.3 Add ChunkType enum (paragraph, table, code, quote, transcript)

## 7. API Endpoints

- [ ] 7.1 Create `src/api/search_routes.py` with search router
- [ ] 7.2 Implement `GET /api/v1/search` for simple queries
- [ ] 7.3 Implement `POST /api/v1/search` for complex queries with filters
- [ ] 7.4 Implement `GET /api/v1/search/chunks/{chunk_id}` for chunk details
- [ ] 7.5 Add query validation and error handling
- [ ] 7.6 Add request/response logging
- [ ] 7.7 Register router in `src/api/app.py`
- [ ] 7.8 Write API tests

## 8. Ingestion Integration

- [ ] 8.1 Update `src/ingestion/files.py` to chunk and embed on ingest:
  - Call ChunkingService after parsing
  - Call EmbeddingService on chunks
  - Store chunks in document_chunks table
- [ ] 8.2 Update `src/ingestion/youtube.py` to chunk and embed transcripts
- [ ] 8.3 Update `src/ingestion/gmail.py` to chunk and embed newsletters
- [ ] 8.4 Update `src/ingestion/substack.py` to chunk and embed RSS content
- [ ] 8.5 Update summarizer to chunk and embed summaries
- [ ] 8.6 Add chunking/embedding as optional (feature flag `ENABLE_SEARCH_INDEXING`)
- [ ] 8.7 Add error handling for chunking/embedding failures (non-blocking)

## 9. Backfill Migration

- [ ] 9.1 Create management command `python -m src.scripts.backfill_chunks`
- [ ] 9.2 Implement batch processing:
  - Fetch documents without chunks
  - Re-parse with appropriate parser
  - Chunk and embed
  - Store chunks
- [ ] 9.3 Add rate limiting to avoid API throttling (embeddings)
- [ ] 9.4 Add resume capability (track last processed source_type + source_id)
- [ ] 9.5 Add progress reporting (processed/total, chunks created, time remaining)
- [ ] 9.6 Add dry-run mode for testing
- [ ] 9.7 Add parallel processing option (multiple workers)
- [ ] 9.8 Document backfill process in CLAUDE.md

## 10. Documentation

- [ ] 10.1 Update `docs/ARCHITECTURE.md` with search architecture and chunking strategy
- [ ] 10.2 Add search API documentation with examples
- [ ] 10.3 Update CLAUDE.md with search-related commands
- [ ] 10.4 Document chunking strategies by parser type
- [ ] 10.5 Add search troubleshooting guide

## 11. Testing & Validation

- [ ] 11.1 Run full test suite
- [ ] 11.2 Test chunking with each parser type:
  - DoclingParser (PDF with tables, sections)
  - YouTubeParser (transcript with timestamps)
  - MarkItDownParser (DOCX, PPTX)
- [ ] 11.3 Test search with sample queries
- [ ] 11.4 Verify BM25 relevance scoring
- [ ] 11.5 Verify vector similarity scoring on chunks
- [ ] 11.6 Verify hybrid RRF combination
- [ ] 11.7 Test chunk-to-document aggregation
- [ ] 11.8 Test deep-linking for YouTube chunks
- [ ] 11.9 Performance testing with realistic data volume
- [ ] 11.10 Test edge cases (empty results, special characters, long queries, oversized tables)
