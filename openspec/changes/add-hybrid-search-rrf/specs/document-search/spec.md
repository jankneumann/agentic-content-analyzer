# Document Search Specification - Cross-Backend Compatibility

## MODIFIED Requirements

### Requirement: BM25 Full-Text Search

The system SHALL provide BM25-based full-text search across ingested documents using a provider-aware strategy.

The system SHALL support multiple BM25 implementations:
- **ParadeDB BM25 Strategy**: Uses pg_search extension with `@@@` operator (higher quality, available on local PostgreSQL and Supabase)
- **PostgreSQL Native FTS Strategy**: Uses `tsvector`/`ts_rank_cd` (works on all backends including Neon)

The system SHALL auto-detect the available BM25 implementation based on database backend:
1. Check for explicit `SEARCH_BM25_STRATEGY` override
2. If pg_search extension is available, use ParadeDB strategy
3. Otherwise, fall back to PostgreSQL Native FTS strategy

The system SHALL create indexes appropriate to the selected strategy:
- **ParadeDB**: BM25 indexes on content fields
- **Native FTS**: GIN indexes on TSVECTOR columns with automatic trigger updates

The system SHALL return search results ordered by relevance score regardless of strategy.

The system SHALL expose the active strategy name in search response metadata.

#### Scenario: Basic keyword search returns relevant results

- **WHEN** a user searches for "machine learning transformers"
- **THEN** the system returns documents containing those terms
- **AND** results are ordered by relevance score (highest first)
- **AND** each result includes the relevance score
- **AND** the response includes metadata indicating which BM25 strategy was used

#### Scenario: BM25 search with no matches

- **WHEN** a user searches for a query with no matching documents
- **THEN** the system returns an empty result set
- **AND** the total count is 0

#### Scenario: BM25 index auto-updates on insert

- **WHEN** new content is ingested
- **THEN** the appropriate index is automatically updated (BM25 or TSVECTOR)
- **AND** the content is searchable immediately

#### Scenario: Native FTS fallback on Neon

- **WHEN** the database backend is Neon (pg_search unavailable)
- **THEN** the system uses PostgreSQL Native FTS strategy
- **AND** search results are ranked using ts_rank_cd
- **AND** the response metadata indicates "postgres_native_fts" strategy

#### Scenario: ParadeDB BM25 on Supabase

- **WHEN** the database backend is Supabase with pg_search available
- **THEN** the system uses ParadeDB BM25 strategy
- **AND** search results are ranked using true BM25 scoring
- **AND** the response metadata indicates "paradedb_bm25" strategy

#### Scenario: Explicit strategy override

- **WHEN** SEARCH_BM25_STRATEGY is set to "native"
- **THEN** the system uses PostgreSQL Native FTS strategy
- **AND** does not attempt to detect pg_search availability

---

### Requirement: Chunk Embedding Storage

The system SHALL store chunk embeddings as vector columns using the pgvector extension (available on all supported backends).

The system SHALL generate embeddings for each chunk using a configurable embedding provider.

The system SHALL support the following embedding providers:
- **OpenAI**: text-embedding-3-small (1536 dims), text-embedding-3-large (3072 dims), text-embedding-ada-002 (1536 dims)
- **Voyage AI**: voyage-3 (1024 dims), voyage-3-lite (512 dims), voyage-code-3 (1024 dims)
- **Cohere**: embed-english-v3.0 (1024 dims), embed-english-light-v3.0 (384 dims), embed-multilingual-v3.0 (1024 dims)
- **Local**: sentence-transformers models including all-MiniLM-L6-v2 (384 dims), all-mpnet-base-v2 (768 dims)

The system SHALL select the embedding provider based on configuration:
- `EMBEDDING_PROVIDER`: Provider name (openai, voyage, cohere, local)
- `EMBEDDING_MODEL`: Model name within provider (optional, uses provider default)
- `EMBEDDING_DIMENSIONS`: Vector dimensions (auto-detected from provider/model if not specified)

The system SHALL create HNSW indexes on chunk embedding columns for fast approximate nearest neighbor search.

The system SHALL support batch embedding generation for efficiency.

The system SHALL handle different vector dimensions based on the configured provider/model.

#### Scenario: Chunks embedded on document ingestion

- **WHEN** a document is ingested and chunked
- **THEN** the system generates embeddings using the configured provider
- **AND** stores embeddings in the document_chunks.embedding column

#### Scenario: Batch embedding for multiple chunks

- **WHEN** a document produces multiple chunks
- **THEN** the system batches embedding requests for efficiency
- **AND** respects API rate limits for cloud providers

#### Scenario: Chunk metadata preserved with embedding

- **WHEN** a chunk embedding is stored
- **THEN** the chunk retains all structural metadata (section_path, page_number, timestamps, deep_link_url)
- **AND** can be traced back to its source document

#### Scenario: OpenAI embedding provider

- **WHEN** EMBEDDING_PROVIDER is set to "openai"
- **THEN** the system uses the OpenAI embeddings API
- **AND** uses text-embedding-3-small by default (1536 dimensions)
- **AND** supports model override via EMBEDDING_MODEL

#### Scenario: Voyage AI embedding provider

- **WHEN** EMBEDDING_PROVIDER is set to "voyage"
- **THEN** the system uses the Voyage AI embeddings API
- **AND** uses voyage-3 by default (1024 dimensions)
- **AND** optimizes for retrieval use cases

#### Scenario: Cohere embedding provider

- **WHEN** EMBEDDING_PROVIDER is set to "cohere"
- **THEN** the system uses the Cohere embeddings API
- **AND** uses embed-english-v3.0 by default (1024 dimensions)
- **AND** uses "search_document" input_type for indexing and "search_query" for queries

#### Scenario: Local embedding provider

- **WHEN** EMBEDDING_PROVIDER is set to "local"
- **THEN** the system uses sentence-transformers locally
- **AND** uses all-MiniLM-L6-v2 by default (384 dimensions)
- **AND** does not make external API calls

#### Scenario: Provider change requires re-indexing

- **WHEN** the embedding provider or model is changed
- **AND** the new configuration produces different vector dimensions
- **THEN** the system requires re-indexing of all chunks
- **AND** logs a warning about dimension mismatch if existing embeddings exist

---

### Requirement: Search Configuration

The system SHALL support configuration of search parameters via environment variables.

The system SHALL provide the following configuration options:

**Embedding Configuration:**
- `EMBEDDING_PROVIDER`: provider name (openai, voyage, cohere, local; default: openai)
- `EMBEDDING_MODEL`: model identifier within provider (optional, uses provider default)
- `EMBEDDING_DIMENSIONS`: vector dimensions (auto-detected if not specified)

**BM25 Configuration:**
- `SEARCH_BM25_STRATEGY`: explicit strategy override (paradedb, native; default: auto-detect)

**Chunking Configuration:**
- `CHUNK_SIZE_TOKENS`: target chunk size in tokens (default: 512)
- `CHUNK_OVERLAP_TOKENS`: overlap between chunks in tokens (default: 64)

**Search Behavior:**
- `SEARCH_BM25_WEIGHT`: BM25 weight for hybrid search (default: 0.5)
- `SEARCH_VECTOR_WEIGHT`: vector weight for hybrid search (default: 0.5)
- `SEARCH_RRF_K`: RRF k-parameter (default: 60)
- `SEARCH_DEFAULT_LIMIT`: default result limit (default: 20)
- `SEARCH_MAX_LIMIT`: maximum allowed result limit (default: 100)
- `ENABLE_SEARCH_INDEXING`: feature flag to enable/disable chunking and embedding (default: true)

#### Scenario: Default configuration

- **WHEN** no search configuration is specified
- **THEN** the system uses OpenAI text-embedding-3-small for embeddings
- **AND** auto-detects the best available BM25 strategy
- **AND** uses default values for all other parameters

#### Scenario: Custom embedding provider

- **WHEN** EMBEDDING_PROVIDER is set to "voyage" and EMBEDDING_MODEL is set to "voyage-3-lite"
- **THEN** the system uses Voyage AI with the lite model
- **AND** EMBEDDING_DIMENSIONS defaults to 512

#### Scenario: Explicit BM25 strategy

- **WHEN** SEARCH_BM25_STRATEGY is set to "native"
- **THEN** the system uses PostgreSQL Native FTS strategy
- **AND** ignores pg_search availability detection

#### Scenario: Custom chunk size

- **WHEN** CHUNK_SIZE_TOKENS is set to 256
- **THEN** the system creates smaller chunks for finer-grained search
- **AND** more chunks are created per document

#### Scenario: Search indexing disabled

- **WHEN** ENABLE_SEARCH_INDEXING is set to false
- **THEN** documents are ingested without chunking or embedding
- **AND** only BM25 search is available

#### Scenario: Local embedding for air-gapped deployment

- **WHEN** EMBEDDING_PROVIDER is set to "local"
- **THEN** the system does not require external API connectivity for embeddings
- **AND** uses sentence-transformers models loaded locally

---

## ADDED Requirements

### Requirement: Cross-Backend Compatibility

The system SHALL support hybrid search across all three supported PostgreSQL backends: local PostgreSQL, Supabase, and Neon.

The system SHALL use pgvector for vector similarity search on all backends (built into Supabase and Neon, installable on local PostgreSQL).

The system SHALL provide equivalent search API semantics regardless of backend, with potential quality differences documented.

The system SHALL detect backend capabilities at startup and select appropriate strategies.

#### Scenario: Search works on local PostgreSQL

- **WHEN** the database backend is local PostgreSQL with pgvector and pg_search
- **THEN** hybrid search uses ParadeDB BM25 and pgvector
- **AND** search results are returned with highest quality ranking

#### Scenario: Search works on Supabase

- **WHEN** the database backend is Supabase
- **THEN** hybrid search uses ParadeDB BM25 (if enabled) and pgvector
- **AND** search results match local PostgreSQL behavior

#### Scenario: Search works on Neon

- **WHEN** the database backend is Neon (pg_search unavailable)
- **THEN** hybrid search uses PostgreSQL Native FTS and pgvector
- **AND** search results are ranked using ts_rank_cd (lower quality than BM25)
- **AND** the API response is identical in structure to other backends

#### Scenario: Backend compatibility documented

- **WHEN** a user reviews search documentation
- **THEN** the documentation includes a backend compatibility matrix
- **AND** explains the quality differences between BM25 strategies
- **AND** provides recommendations for production deployments

---

### Requirement: Search Response Metadata

The system SHALL include backend and strategy metadata in search responses.

The search response SHALL include a `meta` object with:
- `bm25_strategy`: The BM25 strategy used (paradedb_bm25, postgres_native_fts)
- `embedding_provider`: The embedding provider used (openai, voyage, cohere, local)
- `embedding_model`: The specific model used
- `query_time_ms`: Total query execution time
- `backend`: Database backend type (local, supabase, neon)

#### Scenario: Search response includes strategy metadata

- **WHEN** a search is executed
- **THEN** the response includes meta.bm25_strategy
- **AND** the response includes meta.embedding_provider
- **AND** the response includes meta.embedding_model

#### Scenario: Debugging search quality issues

- **WHEN** a user reports search quality issues
- **THEN** the response metadata helps identify if native FTS is being used
- **AND** suggests upgrading to a backend with pg_search support if needed
