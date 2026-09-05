## MODIFIED Requirements

### Requirement: Search API

The system SHALL expose search functionality via REST API endpoints with exact totals and
cursor-based paging.

The system SHALL provide:
- `GET /api/v1/search` — Simple query parameter-based search
- `POST /api/v1/search` — Complex JSON body-based search with filters and weights
- `GET /api/v1/search/chunks/{chunk_id}` — Retrieve specific chunk details

The system SHALL return results with:
- `id`: content identifier
- `type`: content type
- `title`: content title
- `score`: combined relevance score
- `scores`: individual scores by method (bm25, vector, rrf, rerank if active)
- `metadata`: source, published_date, publication
- `matching_chunks`: list of up to 3 relevant chunks per document with chunk_id, content, section, score, highlight, deep_link, chunk_type

The system SHALL highlight matching query terms in chunk content using `<mark>` HTML tags in the `highlight` field. For vector-only results where no query terms appear literally, the `highlight` field SHALL contain the first 200 characters of `chunk_text` without `<mark>` tags.

The system SHALL include a `meta` object in the response (see Search Response Metadata requirement).

The system SHALL support pagination via a `cursor` request field and a `next_cursor` response field. The `offset` parameter is removed.

#### Scenario: GET search with query parameter

- **WHEN** a client sends `GET /api/v1/search?q=machine+learning&limit=10`
- **THEN** the system performs a hybrid search
- **AND** returns up to 10 document results with matching chunks

#### Scenario: POST search with JSON body

- **WHEN** a client sends `POST /api/v1/search` with JSON body including query, type, weights, and filters
- **THEN** the system executes the specified search type (bm25, vector, or hybrid)
- **AND** returns results with matching chunks

#### Scenario: Search response includes timing

- **WHEN** a search is executed
- **THEN** the response includes `meta.query_time_ms`
- **AND** the response includes `total` as the exact count of distinct documents satisfying the lexical predicate and filters (for vector-only searches, the count of filter-eligible embedded documents)

#### Scenario: Pagination support

- **WHEN** a client sends the `next_cursor` from a previous response as `cursor` with the same query, type, filters, and weights
- **THEN** the system returns the next page cut from the same deterministic ranking
- **AND** no document from an earlier page reappears
- **AND** `next_cursor` is `null` on the final page

#### Scenario: Cursor from a different query is rejected

- **WHEN** a client sends a `cursor` whose signed query digest does not match the request
- **THEN** the system returns `422` with problem code `invalid_cursor`
- **AND** no search is executed

#### Scenario: Chunk detail retrieval

- **WHEN** a client requests `GET /api/v1/search/chunks/{chunk_id}`
- **THEN** the system returns the full chunk with all metadata
- **AND** includes the source content reference

### Requirement: Search Response Metadata

The system SHALL include completeness, omissions, backend, and strategy metadata in search responses.

The search response SHALL include a `meta` object with:
- `completeness`: `complete`, `truncated`, or `degraded`
- `omissions`: list of `{reason, detail, affected}` where `reason` is one of `candidate_window_truncated`, `rerank_failed`, `rerank_partial`, `vector_unavailable`, `tree_search_fallback`, `filter_excluded`
- `bm25_strategy`: The BM25 strategy used (paradedb_bm25, postgres_native_fts)
- `embedding_provider` and `embedding_model`: present only when the vector arm contributed results
- `rerank_provider` and `rerank_model`: present only when reranking ran to completion over the full candidate window
- `query_time_ms`: Total query execution time
- `backend`: Database backend type (local, supabase, neon)

#### Scenario: Search response includes strategy metadata

- **WHEN** a hybrid search executes with a working vector arm
- **THEN** the response includes `meta.bm25_strategy`, `meta.embedding_provider`, and `meta.embedding_model`
- **AND** `meta.completeness` is `complete` when the fused window covered every matching document

#### Scenario: Reranking metadata included when active

- **WHEN** a search is executed with reranking enabled and the reranker succeeds over the whole window
- **THEN** the response includes `meta.rerank_provider` and `meta.rerank_model`

#### Scenario: Reranking failure is disclosed

- **WHEN** the reranker raises or covers fewer candidates than the fused window
- **THEN** `meta.rerank_provider` is `null`
- **AND** `meta.omissions` contains `rerank_failed` or `rerank_partial` with the affected count
- **AND** `meta.completeness` is `degraded` or `truncated` respectively

#### Scenario: Vector arm failure is disclosed

- **WHEN** query embedding fails during a hybrid search
- **THEN** results come from BM25 alone
- **AND** `meta.embedding_provider` is `null` and `meta.omissions` contains `vector_unavailable`
- **AND** `meta.completeness` is `degraded`

#### Scenario: Candidate window truncation is disclosed

- **WHEN** `total` exceeds the number of documents in the fused ranking
- **THEN** `meta.omissions` contains `candidate_window_truncated` with `affected = total - window`
- **AND** `meta.completeness` is `truncated`

#### Scenario: Debugging search quality issues

- **WHEN** a user reports search quality issues
- **THEN** the response metadata identifies the active BM25 strategy and embedding provider
- **AND** helps determine if native FTS fallback or suboptimal provider is the cause
