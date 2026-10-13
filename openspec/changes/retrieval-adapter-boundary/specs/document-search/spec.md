## MODIFIED Requirements

### Requirement: Search Response Metadata

The system SHALL include backend, adapter, and strategy metadata in search responses.

The search response SHALL include a `meta` object with:
- `bm25_strategy`: The BM25 strategy used (paradedb_bm25, postgres_native_fts)
- `embedding_provider`: The embedding provider used (openai, voyage, cohere, local)
- `embedding_model`: The specific model used
- `rerank_provider`: The reranking provider used (cohere, jina, local, llm) — only present if reranking active
- `rerank_model`: The specific reranking model used — only present if reranking active
- `query_time_ms`: Total query execution time
- `backend`: Database backend type (local, supabase, neon)
- `retrieval_adapter`: The primary retrieval adapter that served the response (postgres, lancedb)
- `shadow`: Present only when a shadow read was scheduled; names the secondary adapter and whether the comparison was recorded

Existing fields SHALL keep their names and value sets so that consumers and
production evidence relying on `meta.bm25_strategy` remain valid.

#### Scenario: Search response includes strategy metadata

- **WHEN** a search is executed
- **THEN** the response includes `meta.bm25_strategy`
- **AND** the response includes `meta.embedding_provider` and `meta.embedding_model`
- **AND** the response includes `meta.retrieval_adapter`

#### Scenario: Reranking metadata included when active

- **WHEN** a search is executed with reranking enabled
- **THEN** the response includes `meta.rerank_provider` and `meta.rerank_model`

#### Scenario: Shadow metadata present only when shadow reading

- **WHEN** a search is executed with shadow reading disabled
- **THEN** the response omits `meta.shadow`
- **AND** with shadow reading enabled the response includes `meta.shadow.adapter`

#### Scenario: Debugging search quality issues

- **WHEN** a user reports search quality issues
- **THEN** the response metadata identifies the active adapter, BM25 strategy, and embedding provider
- **AND** helps determine if native FTS fallback, an adapter difference, or a suboptimal provider is the cause

### Requirement: Cross-Backend Compatibility

The system SHALL support hybrid search across all three supported PostgreSQL backends: local PostgreSQL, Supabase, and Neon, through the Postgres retrieval adapter.

The system SHALL use pgvector for vector similarity search on all PostgreSQL backends.

The system SHALL provide equivalent search API semantics regardless of backend or retrieval adapter, with potential quality differences documented.

The system SHALL detect backend capabilities at startup and select appropriate strategies within the Postgres adapter; adapter selection itself SHALL be explicit configuration, never capability detection.

#### Scenario: Search works on local PostgreSQL

- **WHEN** the database backend is local PostgreSQL with pgvector and pg_search
- **THEN** hybrid search uses ParadeDB BM25 and pgvector
- **AND** search results are returned with highest quality ranking

#### Scenario: Search works on Supabase

- **WHEN** the database backend is Supabase
- **THEN** hybrid search uses ParadeDB BM25 (if enabled) and pgvector

#### Scenario: Search works on Neon

- **WHEN** the database backend is Neon (AWS region, pg_search available)
- **THEN** hybrid search uses ParadeDB BM25 and pgvector
- **AND** the API response structure is identical to other backends

#### Scenario: Search works with a secondary adapter configured

- **WHEN** a secondary retrieval adapter is configured on any PostgreSQL backend
- **THEN** the primary response is served by the Postgres adapter with identical structure
- **AND** the secondary adapter never changes the primary response

#### Scenario: Backend compatibility documented

- **WHEN** a user reviews search documentation
- **THEN** the documentation includes a backend compatibility matrix
- **AND** explains quality differences between BM25 strategies
- **AND** lists each retrieval adapter with its supported namespaces, storage targets, and known gaps
