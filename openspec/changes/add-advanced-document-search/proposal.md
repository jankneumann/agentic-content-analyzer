# Change: Add Advanced Document Search with Hybrid BM25 + Vector Search

## Why

The current search implementation is limited to simple ILIKE pattern matching on newsletter titles only, missing:
- Full-text search across document content (raw_text, summaries, themes)
- Semantic/conceptual search that finds related content even without exact keyword matches
- Relevance ranking beyond simple substring matching
- Combined search strategies that leverage both lexical precision and semantic understanding

Users need to efficiently discover relevant content across thousands of ingested newsletters, uploaded documents, and YouTube transcripts using natural language queries.

## What Changes

- **Add pg_search extension** for BM25 full-text search with relevance ranking
- **Add pgvector extension** for storing and querying document embeddings
- **Implement hybrid search** combining BM25 lexical search with vector similarity search
- **Add Reciprocal Rank Fusion (RRF)** to combine and rerank results from multiple search methods
- **Create embedding pipeline** to generate and store document embeddings at ingestion time
- **Add search API endpoints** for unified search across all document types
- **Add search configuration** for model selection, weighting, and filtering

## Impact

- **Affected specs**: New capability (document-search)
- **Affected code**:
  - `src/storage/` - New search module with BM25 and vector search
  - `src/models/` - New embedding column for newsletters/documents
  - `src/api/` - New search endpoints
  - `src/config/` - Search configuration settings
  - `alembic/versions/` - Migration for pgvector, pg_search setup
- **Dependencies**:
  - pg_search extension (ParadeDB)
  - pgvector extension
  - Embedding model integration (OpenAI or local)
- **Breaking changes**: None (additive feature)
