# Change: Add Advanced Document Search with Hybrid BM25 + Vector Search

## Prerequisites

- **refactor-unified-content-model**: This proposal assumes the unified Content model with markdown-first storage is implemented. The chunking service will operate on Content.markdown_content rather than multiple content fields across Newsletter/Document tables.

## Why

The current search implementation is limited to simple ILIKE pattern matching on newsletter titles only, missing:
- Full-text search across document content (raw_text, summaries, themes)
- Semantic/conceptual search that finds related content even without exact keyword matches
- Relevance ranking beyond simple substring matching
- Combined search strategies that leverage both lexical precision and semantic understanding

Users need to efficiently discover relevant content across thousands of ingested newsletters, uploaded documents, and YouTube transcripts using natural language queries.

## What Changes

- **Add pg_search extension** for BM25 full-text search with relevance ranking
- **Add pgvector extension** for storing and querying document chunk embeddings
- **Implement semantic chunking** leveraging existing parser infrastructure (DoclingParser, YouTubeParser, MarkItDownParser) to split documents into meaningful units
- **Create document_chunks table** to store chunks with structural metadata (section paths, page numbers, timestamps, deep-links)
- **Implement hybrid search** combining BM25 document search with chunk-level vector similarity search
- **Add Reciprocal Rank Fusion (RRF)** to combine and rerank results from multiple search methods
- **Create chunking service** with parser-aware strategies for PDFs, YouTube transcripts, markdown, and HTML
- **Create embedding pipeline** to generate and store chunk embeddings at ingestion time
- **Add search API endpoints** for unified search with chunk-level highlighting and navigation
- **Add search configuration** for model selection, chunk sizing, weighting, and filtering

## Impact

- **Affected specs**: New capability (document-search)
- **Affected code**:
  - `src/services/chunking.py` - New chunking service with parser-aware strategies
  - `src/services/embedding.py` - Embedding generation service
  - `src/services/search.py` - Hybrid search with chunk aggregation
  - `src/models/chunk.py` - DocumentChunk SQLAlchemy model
  - `src/models/search.py` - Search request/response Pydantic models
  - `src/api/search_routes.py` - New search endpoints
  - `src/config/settings.py` - Search and chunking configuration
  - `alembic/versions/` - Migration for document_chunks, pgvector, pg_search
  - `src/ingestion/` - Integration of chunking/embedding at ingest time
- **Dependencies**:
  - pg_search extension (ParadeDB)
  - pgvector extension
  - Embedding model integration (OpenAI text-embedding-3-small)
- **Breaking changes**: None (additive feature)
