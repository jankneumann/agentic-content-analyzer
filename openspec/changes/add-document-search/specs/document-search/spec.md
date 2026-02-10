# Document Search Specification

## ADDED Requirements

### Requirement: BM25 Full-Text Search

The system SHALL provide BM25-based full-text search across ingested document chunks using a provider-aware strategy.

The system SHALL support multiple BM25 implementations:
- **ParadeDB BM25 Strategy**: Uses pg_search extension with `@@@` operator (higher quality, available on local PostgreSQL and Supabase)
- **PostgreSQL Native FTS Strategy**: Uses `tsvector`/`ts_rank_cd` (works on all backends including Neon)

The system SHALL auto-detect the available BM25 implementation based on database backend:
1. Check for explicit `SEARCH_BM25_STRATEGY` override
2. If pg_search extension is available, use ParadeDB strategy
3. Otherwise, fall back to PostgreSQL Native FTS strategy

The system SHALL create indexes appropriate to the selected strategy:
- **ParadeDB**: BM25 index on `chunk_text`
- **Native FTS**: GIN index on `search_vector` TSVECTOR column with automatic trigger updates

The system SHALL return search results ordered by relevance score regardless of strategy.

The system SHALL expose the active strategy name in search response metadata.

#### Scenario: Basic keyword search returns relevant results

- **WHEN** a user searches for "machine learning transformers"
- **THEN** the system returns document chunks containing those terms
- **AND** results are ordered by relevance score (highest first)
- **AND** each result includes the relevance score
- **AND** the response includes metadata indicating which BM25 strategy was used

#### Scenario: BM25 search with no matches

- **WHEN** a user searches for a query with no matching documents
- **THEN** the system returns an empty result set
- **AND** the total count is 0

#### Scenario: BM25 index auto-updates on insert

- **WHEN** new content is ingested and chunked
- **THEN** the appropriate index is automatically updated (BM25 or TSVECTOR trigger)
- **AND** the content is searchable immediately

#### Scenario: Native FTS fallback on backends without pg_search

- **WHEN** the database backend does not have pg_search installed (e.g., bare PostgreSQL without extensions)
- **THEN** the system uses PostgreSQL Native FTS strategy
- **AND** search results are ranked using `ts_rank_cd`
- **AND** the response metadata indicates "postgres_native_fts" strategy

#### Scenario: ParadeDB BM25 on supported backends

- **WHEN** the database backend has pg_search available (local PostgreSQL, Supabase, or Neon AWS)
- **THEN** the system uses ParadeDB BM25 strategy
- **AND** search results are ranked using true BM25 scoring
- **AND** the response metadata indicates "paradedb_bm25" strategy

#### Scenario: Explicit strategy override

- **WHEN** `SEARCH_BM25_STRATEGY` is set to "native"
- **THEN** the system uses PostgreSQL Native FTS strategy
- **AND** does not attempt to detect pg_search availability

---

### Requirement: Semantic Document Chunking

The system SHALL split documents into semantically meaningful chunks before generating embeddings.

The system SHALL define a `ChunkingStrategy` protocol enabling pluggable chunking implementations that can be added and tested without modifying the core chunking service.

The system SHALL provide a strategy registry and factory that resolves the chunking strategy by: explicit per-source override → auto-detection from `Content.parser_used` → default markdown strategy.

The system SHALL leverage the structured output from advanced document parsers (DoclingParser, YouTubeParser, MarkItDownParser) to determine chunk boundaries.

The system SHALL store chunks in a `document_chunks` table with metadata linking back to the source content.

The system SHALL provide the following built-in chunking strategies:
- **StructuredChunkingStrategy** (`structured`): For DoclingParser output — split on heading boundaries (H1-H6), extract tables as separate chunks, respect page boundaries
- **YouTubeTranscriptChunkingStrategy** (`youtube_transcript`): For raw transcript output (`parser_used="youtube_transcript_api"`) — use existing 30-second timestamp window groupings with sentence boundaries, preserve deep-link URLs
- **GeminiSummaryChunkingStrategy** (`gemini_summary`): For Gemini-processed YouTube content (`parser_used="gemini"`) — split on topic section headers from Gemini structured output, no timestamps
- **MarkdownChunkingStrategy** (`markdown`): For MarkItDownParser output and default (Gmail, RSS) — split on markdown heading structure, keep code blocks together
- **SectionChunkingStrategy** (`section`): For summaries/digests — split on `## Section` headers (Executive Summary, Key Themes, etc.)

The system SHALL support per-source chunking configuration via `sources.d/` YAML files, allowing override of chunk size, overlap, and chunking strategy at the global, per-type, or per-entry level.

The system SHALL resolve chunking parameters using the existing cascading defaults: global `Settings` → `sources.d/_defaults.yaml` → per-file defaults → per-entry fields (most specific wins).

The system SHALL use the default markdown chunking strategy when `Content.parser_used` is NULL or unrecognized and no `chunking_strategy` override is configured for the source.

The system SHALL produce zero chunks (and log a warning) when `Content.markdown_content` is empty or NULL.

The system SHALL target ~512 tokens per chunk with ~64 tokens overlap between consecutive chunks, unless overridden by per-source configuration.

The system SHALL keep tables as whole chunks even if they exceed the target size (up to 2048 tokens).

#### Scenario: PDF document chunked by structure

- **WHEN** a PDF document is parsed by DoclingParser
- **THEN** the system creates chunks at heading boundaries
- **AND** tables are extracted as separate chunks with caption context
- **AND** each chunk includes the page number metadata

#### Scenario: YouTube transcript chunked by timestamp

- **WHEN** a YouTube video is ingested via transcript (`parser_used="youtube_transcript_api"`)
- **THEN** the system uses `YouTubeTranscriptChunkingStrategy`
- **AND** creates chunks using 30-second timestamp windows
- **AND** each chunk includes `timestamp_start` and `timestamp_end` metadata
- **AND** each chunk includes a `deep_link_url` for direct video navigation

#### Scenario: YouTube Gemini summary chunked by topic section

- **WHEN** a YouTube video is ingested via Gemini summarization (`parser_used="gemini"`)
- **THEN** the system uses `GeminiSummaryChunkingStrategy`
- **AND** creates chunks at topic section boundaries (e.g., `## Topic 1: ...`)
- **AND** each chunk includes the section title as `heading_text`
- **AND** chunks do NOT include timestamps (Gemini output has no timestamps)

#### Scenario: YouTube Gemini and transcript configured independently

- **WHEN** a YouTube source in `sources.d/` has `gemini_summary: true` and `chunk_size_tokens: 1024`
- **AND** another YouTube source has `gemini_summary: false` and `chunk_size_tokens: 512`
- **THEN** Gemini-processed content uses 1024-token chunks with `gemini_summary` strategy
- **AND** transcript-processed content uses 512-token chunks with `youtube_transcript` strategy

#### Scenario: Markdown document chunked by headings

- **WHEN** a markdown document is parsed
- **THEN** the system creates chunks at H1/H2/H3 boundaries
- **AND** each chunk includes the `section_path` (e.g., "# Intro > ## Setup")
- **AND** code blocks are kept together within chunks

#### Scenario: Newsletter summary chunked by section

- **WHEN** a newsletter summary is chunked
- **THEN** the system creates chunks for each section (executive summary, key themes, etc.)
- **AND** each chunk uses `chunk_type="section"`

#### Scenario: Oversized section split into paragraphs

- **WHEN** a section exceeds the target chunk size (512 tokens)
- **THEN** the system splits the section at paragraph boundaries
- **AND** includes overlap between consecutive chunks for context continuity

#### Scenario: Table preserved as single chunk

- **WHEN** a document contains a table
- **THEN** the table is stored as a single chunk with `chunk_type="table"`
- **AND** the table caption and headers are prepended as context
- **AND** the chunk is not split even if it exceeds 512 tokens (up to 2048 tokens)

#### Scenario: Per-source chunk size override

- **WHEN** a source entry in `sources.d/rss.yaml` specifies `chunk_size_tokens: 256` and `chunk_overlap_tokens: 32`
- **THEN** content ingested from that source is chunked with 256-token targets and 32-token overlap
- **AND** the global `CHUNK_SIZE_TOKENS` setting is not affected

#### Scenario: Per-source chunking strategy override

- **WHEN** a source entry specifies `chunking_strategy: youtube_transcript`
- **THEN** content from that source uses the `YouTubeTranscriptChunkingStrategy` regardless of `parser_used`
- **AND** other sources without a `chunking_strategy` override continue to auto-detect from `parser_used`

#### Scenario: Per-type chunking defaults

- **WHEN** `sources.d/podcasts.yaml` specifies `defaults.chunk_size_tokens: 1024`
- **THEN** all podcast sources in that file inherit the 1024-token chunk size
- **AND** individual podcast entries can further override with their own `chunk_size_tokens`

#### Scenario: Cascading chunking defaults resolution

- **WHEN** `Settings.chunk_size_tokens` is 512, `sources.d/rss.yaml` defaults specify 384, and one RSS entry specifies 256
- **THEN** most RSS sources use 384-token chunks
- **AND** the specific entry uses 256-token chunks
- **AND** sources in other files without overrides use the global 512-token default

#### Scenario: Source config not found for content

- **WHEN** content is ingested from a source that has no matching entry in `sources.d/` (e.g., direct URL ingestion, file upload)
- **THEN** the system uses global `Settings` defaults for chunk size and overlap
- **AND** auto-detects the chunking strategy from `Content.parser_used`

#### Scenario: Empty content produces no chunks

- **WHEN** a Content record has empty or NULL `markdown_content`
- **THEN** the system produces zero chunks
- **AND** logs a warning identifying the content_id
- **AND** does not create an embedding

#### Scenario: Unknown parser uses default chunking

- **WHEN** a Content record has `parser_used` set to NULL or an unrecognized value
- **AND** no `chunking_strategy` override is configured for the source
- **THEN** the system uses the default `MarkdownChunkingStrategy` (heading-based + paragraph splitting)

#### Scenario: New chunking strategy added via registry

- **WHEN** a new `ChunkingStrategy` implementation is registered in the strategy registry
- **THEN** it can be selected via `chunking_strategy` in `sources.d/` configuration
- **AND** existing strategies are not affected

#### Scenario: YouTube deep-link URL format

- **WHEN** a YouTube transcript chunk is created
- **THEN** the `deep_link_url` is in the format `https://youtube.com/watch?v={video_id}&t={timestamp_seconds}`
- **AND** `timestamp_seconds` is the integer floor of `timestamp_start`

---

### Requirement: Chunk Embedding Storage

The system SHALL store chunk embeddings as vector columns using the pgvector extension (available on all supported backends).

The system SHALL generate embeddings for each chunk using a configurable embedding provider.

The system SHALL support the following embedding providers:
- **OpenAI**: text-embedding-3-small (1536 dims), text-embedding-3-large (3072 dims)
- **Voyage AI**: voyage-3 (1024 dims), voyage-3-lite (512 dims)
- **Cohere**: embed-english-v3.0 (1024 dims), embed-english-light-v3.0 (384 dims)
- **Local**: sentence-transformers models including all-MiniLM-L6-v2 (384 dims), all-mpnet-base-v2 (768 dims)

The system SHALL select the embedding provider based on configuration (`EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`).

The system SHALL create HNSW indexes on chunk embedding columns for fast approximate nearest neighbor search.

The system SHALL support batch embedding generation for efficiency.

The system SHALL handle different vector dimensions based on the configured provider/model.

#### Scenario: Chunks embedded on document ingestion

- **WHEN** a document is ingested and chunked
- **THEN** the system generates embeddings using the configured provider
- **AND** stores embeddings in the `document_chunks.embedding` column

#### Scenario: Batch embedding for multiple chunks

- **WHEN** a document produces multiple chunks
- **THEN** the system batches embedding requests for efficiency
- **AND** respects API rate limits for cloud providers

#### Scenario: Chunk metadata preserved with embedding

- **WHEN** a chunk embedding is stored
- **THEN** the chunk retains all structural metadata (section_path, page_number, timestamps, deep_link_url)
- **AND** can be traced back to its source content via `content_id`

#### Scenario: OpenAI embedding provider

- **WHEN** `EMBEDDING_PROVIDER` is set to "openai"
- **THEN** the system uses the OpenAI embeddings API
- **AND** uses text-embedding-3-small by default (1536 dimensions)

#### Scenario: Local embedding provider

- **WHEN** `EMBEDDING_PROVIDER` is set to "local"
- **THEN** the system uses sentence-transformers locally
- **AND** does not make external API calls

#### Scenario: Provider change requires re-indexing

- **WHEN** the embedding provider or model is changed to one with different vector dimensions
- **THEN** the system requires re-indexing of all chunks
- **AND** logs a warning about dimension mismatch if existing embeddings exist

#### Scenario: Chunk exceeds provider max token limit

- **WHEN** a chunk exceeds the embedding provider's `max_tokens` limit (e.g., a large table chunk)
- **THEN** the system truncates the chunk text to `max_tokens` before embedding
- **AND** logs a warning with the chunk_id and original token count
- **AND** the stored `chunk_text` retains the full untruncated content (only the embedding input is truncated)

#### Scenario: Embedding API failure during ingestion

- **WHEN** the embedding provider returns an error during content ingestion
- **THEN** the system logs the error with content_id and provider details
- **AND** the content is ingested successfully without embeddings
- **AND** the content is searchable via BM25 only until embeddings are generated
- **AND** the content is eligible for the next backfill run

#### Scenario: Chunking failure during ingestion

- **WHEN** the chunking service encounters an error (e.g., malformed markdown)
- **THEN** the system logs the error with content_id
- **AND** the content is ingested successfully without chunks
- **AND** the content remains searchable via document-level BM25 (if available)

---

### Requirement: Chunk-Level Vector Similarity Search

The system SHALL support semantic search using vector cosine similarity on document chunks.

The system SHALL convert user queries to embeddings using the same provider/model used for chunk embeddings.

The system SHALL search against chunk embeddings and aggregate results to document level.

The system SHALL return results with matching chunks highlighted.

#### Scenario: Semantic search finds conceptually related content

- **WHEN** a user searches for "AI model performance improvements"
- **THEN** the system returns documents containing chunks about related concepts
- **AND** results include documents that may not contain the exact search terms
- **AND** the most relevant chunks are highlighted in the response

#### Scenario: Vector search with query embedding

- **WHEN** a user submits a search query
- **THEN** the system generates an embedding for the query using the configured provider
- **AND** computes cosine similarity against all chunk embeddings
- **AND** aggregates chunk scores to document scores
- **AND** returns documents with their best-matching chunks

#### Scenario: Chunk results include navigation metadata

- **WHEN** a matching chunk is from a YouTube transcript
- **THEN** the result includes a `deep_link_url` to the exact video timestamp
- **AND** the result includes the timestamp range for the chunk

#### Scenario: Table chunks searchable

- **WHEN** a user searches for "benchmark comparison table"
- **THEN** chunks with `chunk_type="table"` are searchable
- **AND** table chunks include caption and header context

#### Scenario: Query embedding generation fails

- **WHEN** the embedding provider fails to generate a query embedding (API error, timeout)
- **THEN** the system falls back to BM25-only search
- **AND** the response metadata indicates `embedding_provider: null`
- **AND** vector scores are omitted from the `scores` object

#### Scenario: No chunks have embeddings

- **WHEN** a vector or hybrid search is executed but no chunks in the database have embeddings
- **THEN** the vector component returns an empty result set
- **AND** hybrid search returns BM25-only results (if BM25 component has matches)

---

### Requirement: Hybrid Search with RRF Reranking

The system SHALL support hybrid search that combines BM25 chunk search and chunk-level vector search.

The system SHALL use Reciprocal Rank Fusion (RRF) to combine rankings from both search methods.

The system SHALL allow configurable weights for BM25 and vector components.

The system SHALL use a default RRF k-parameter of 60.

The system SHALL aggregate chunk-level results to document-level by grouping chunks by `content_id` and using the highest chunk RRF score as the document score.

The system SHALL return up to 3 matching chunks per document in the response, ordered by chunk score descending.

The system SHALL use chunk_id as a stable tiebreaker when RRF scores are equal.

#### Scenario: Hybrid search combines lexical and semantic results

- **WHEN** a user performs a hybrid search for "transformer architecture attention"
- **THEN** the system executes BM25 search on chunks
- **AND** executes vector search on chunks
- **AND** combines chunk results using weighted RRF
- **AND** chunks appearing in both result sets are ranked higher

#### Scenario: Hybrid search with custom weights

- **WHEN** a user specifies weights `{"bm25": 0.7, "vector": 0.3}`
- **THEN** the system applies weighted RRF scoring
- **AND** BM25 rankings contribute more to the final score

#### Scenario: RRF handles disjoint result sets

- **WHEN** BM25 and vector search return completely different chunks
- **THEN** RRF assigns scores based on individual rankings
- **AND** all chunks from both methods appear in combined results

---

### Requirement: Cross-Encoder Reranking

The system SHALL support an optional cross-encoder reranking step after RRF fusion to improve final result quality.

The system SHALL take the top-K candidates from RRF (configurable, default: 50) and score each (query, chunk_text) pair using a cross-encoder or fast LLM.

The system SHALL support multiple reranking providers:
- **Cohere Rerank**: Managed API with `rerank-english-v3.0`
- **Jina Rerank**: Managed API with `jina-reranker-v2-base-multilingual`
- **Local cross-encoder**: sentence-transformers `CrossEncoder` (e.g., `ms-marco-MiniLM-L-12-v2`)
- **LLM reranking**: Uses the project's existing LLM router (configurable via `SEARCH_RERANK_MODEL`, e.g., `gemini-2.5-flash`, `claude-haiku-4-5`)

The system SHALL select the reranking provider based on configuration (`SEARCH_RERANK_PROVIDER`, `SEARCH_RERANK_MODEL`).

The system SHALL make reranking optional and disabled by default (`SEARCH_RERANK_ENABLED=false`).

The system SHALL expose the reranking provider in search response metadata when active.

#### Scenario: Reranking reorders RRF results by cross-encoder score

- **WHEN** `SEARCH_RERANK_ENABLED` is true
- **AND** a user performs a hybrid search
- **THEN** the system first produces RRF-ranked results
- **AND** takes the top-K candidates (default: 50)
- **AND** scores each (query, chunk_text) pair with the configured cross-encoder
- **AND** reorders results by cross-encoder score (descending)
- **AND** the final result ordering may differ from the RRF ordering

#### Scenario: Reranking disabled by default

- **WHEN** `SEARCH_RERANK_ENABLED` is not set or is false
- **THEN** the system skips the reranking step
- **AND** returns RRF-ranked results directly

#### Scenario: Reranking with Cohere

- **WHEN** `SEARCH_RERANK_PROVIDER` is set to "cohere"
- **THEN** the system uses the Cohere Rerank API
- **AND** sends (query, chunk_text) pairs in a single batch request
- **AND** reorders by Cohere relevance scores

#### Scenario: Reranking with local cross-encoder

- **WHEN** `SEARCH_RERANK_PROVIDER` is set to "local"
- **THEN** the system uses a sentence-transformers CrossEncoder locally
- **AND** does not make external API calls
- **AND** runs inference in a thread pool to avoid blocking

#### Scenario: Reranking with fast LLM

- **WHEN** `SEARCH_RERANK_PROVIDER` is set to "llm"
- **THEN** the system uses the configured LLM to score (query, document) relevance
- **AND** uses a structured prompt asking for a relevance score (0-10)
- **AND** batches scoring requests for efficiency

#### Scenario: Reranking metadata in response

- **WHEN** reranking is active
- **THEN** the search response metadata includes `rerank_provider` and `rerank_model`
- **AND** includes `rerank_top_k` indicating how many candidates were reranked

#### Scenario: Reranking provider API failure

- **WHEN** the reranking provider returns an error (timeout, rate limit, API failure)
- **THEN** the system logs the error
- **AND** falls back to returning the RRF-ranked results without reranking
- **AND** the response metadata omits `rerank_provider` (indicating reranking did not complete)

#### Scenario: LLM reranking with unparseable response

- **WHEN** `SEARCH_RERANK_PROVIDER` is "llm"
- **AND** the LLM returns a response that cannot be parsed as an integer score
- **THEN** the system assigns a default score of 5 to that document
- **AND** continues reranking the remaining documents normally

#### Scenario: Reranking top_k exceeds available results

- **WHEN** `SEARCH_RERANK_TOP_K` is 50 but RRF produces only 15 candidate chunks
- **THEN** the system reranks all 15 candidates (does not pad or error)
- **AND** the response metadata reflects the actual number reranked

---

### Requirement: Search Filtering

The system SHALL support filtering search results by metadata fields.

The system SHALL support the following filters:
- `sources`: list of source type values (GMAIL, RSS, FILE_UPLOAD, YOUTUBE, SUBSTACK, PODCAST, URL)
- `date_from`: minimum published date (inclusive)
- `date_to`: maximum published date (inclusive)
- `publications`: list of publication names
- `statuses`: list of processing status values
- `chunk_types`: list of chunk types (paragraph, table, code, quote, transcript, section)

Filters SHALL be applied before search ranking.

#### Scenario: Filter by source type

- **WHEN** a user searches with filter `sources=["GMAIL", "RSS"]`
- **THEN** only content from Gmail or RSS sources is included in results

#### Scenario: Filter by date range

- **WHEN** a user searches with `date_from="2024-01-01"` and `date_to="2024-06-30"`
- **THEN** only documents published within that range are included

#### Scenario: Filter by chunk type

- **WHEN** a user specifies `chunk_types=["table", "code"]`
- **THEN** only chunks of those types are included in vector search
- **AND** results highlight matching table and code chunks

#### Scenario: Combined filters

- **WHEN** a user applies multiple filters
- **THEN** all filters are combined with AND logic
- **AND** only documents matching all filters are returned

#### Scenario: Filters produce empty result set

- **WHEN** a user applies filters that match no content
- **THEN** the system returns an empty result set with `total: 0`
- **AND** the response includes the `meta` object with strategy information

---

### Requirement: Search API

The system SHALL expose search functionality via REST API endpoints.

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

The system SHALL support pagination via `offset` and `limit` parameters.

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
- **AND** the response includes `total` count of matching documents

#### Scenario: Pagination support

- **WHEN** a user specifies `offset=20` and `limit=10`
- **THEN** the system skips the first 20 results
- **AND** returns results 21-30

#### Scenario: Chunk detail retrieval

- **WHEN** a client requests `GET /api/v1/search/chunks/{chunk_id}`
- **THEN** the system returns the full chunk with all metadata
- **AND** includes the source content reference

---

### Requirement: Search Response Metadata

The system SHALL include backend and strategy metadata in search responses.

The search response SHALL include a `meta` object with:
- `bm25_strategy`: The BM25 strategy used (paradedb_bm25, postgres_native_fts)
- `embedding_provider`: The embedding provider used (openai, voyage, cohere, local)
- `embedding_model`: The specific model used
- `rerank_provider`: The reranking provider used (cohere, jina, local, llm) — only present if reranking active
- `rerank_model`: The specific reranking model used — only present if reranking active
- `query_time_ms`: Total query execution time
- `backend`: Database backend type (local, supabase, neon)

#### Scenario: Search response includes strategy metadata

- **WHEN** a search is executed
- **THEN** the response includes `meta.bm25_strategy`
- **AND** the response includes `meta.embedding_provider` and `meta.embedding_model`

#### Scenario: Reranking metadata included when active

- **WHEN** a search is executed with reranking enabled
- **THEN** the response includes `meta.rerank_provider` and `meta.rerank_model`

#### Scenario: Debugging search quality issues

- **WHEN** a user reports search quality issues
- **THEN** the response metadata identifies the active BM25 strategy and embedding provider
- **AND** helps determine if native FTS fallback or suboptimal provider is the cause

---

### Requirement: Cross-Backend Compatibility

The system SHALL support hybrid search across all three supported PostgreSQL backends: local PostgreSQL, Supabase, and Neon.

The system SHALL use pgvector for vector similarity search on all backends.

The system SHALL provide equivalent search API semantics regardless of backend, with potential quality differences documented.

The system SHALL detect backend capabilities at startup and select appropriate strategies.

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

#### Scenario: Backend compatibility documented

- **WHEN** a user reviews search documentation
- **THEN** the documentation includes a backend compatibility matrix
- **AND** explains quality differences between BM25 strategies

---

### Requirement: Search Configuration

The system SHALL support configuration of search parameters via environment variables.

**Embedding Configuration:**
- `EMBEDDING_PROVIDER`: provider name (openai, voyage, cohere, local; default: openai)
- `EMBEDDING_MODEL`: model identifier within provider (optional, uses provider default)
- `EMBEDDING_DIMENSIONS`: vector dimensions (auto-detected if not specified)

**BM25 Configuration:**
- `SEARCH_BM25_STRATEGY`: explicit strategy override (paradedb, native; default: auto-detect)

**Reranking Configuration:**
- `SEARCH_RERANK_ENABLED`: enable cross-encoder reranking (default: false)
- `SEARCH_RERANK_PROVIDER`: reranking provider (cohere, jina, local, llm; default: cohere)
- `SEARCH_RERANK_MODEL`: model name within provider (optional, uses provider default)
- `SEARCH_RERANK_TOP_K`: number of RRF candidates to rerank (default: 50)

**Chunking Configuration:**
- `CHUNK_SIZE_TOKENS`: target chunk size in tokens (default: 512)
- `CHUNK_OVERLAP_TOKENS`: overlap between chunks in tokens (default: 64)

**Per-Source Chunking Overrides** (via `sources.d/` YAML):
- `chunk_size_tokens`: override target chunk size for this source/source type
- `chunk_overlap_tokens`: override chunk overlap for this source/source type
- `chunking_strategy`: force a specific chunking strategy (structured, youtube_transcript, gemini_summary, markdown, section; default: auto-detect from parser_used). Must match a key in the strategy registry.

**Search Behavior:**
- `SEARCH_BM25_WEIGHT`: BM25 weight for hybrid search (default: 0.5)
- `SEARCH_VECTOR_WEIGHT`: vector weight for hybrid search (default: 0.5)
- `SEARCH_RRF_K`: RRF k-parameter (default: 60)
- `SEARCH_DEFAULT_LIMIT`: default result limit (default: 20)
- `SEARCH_MAX_LIMIT`: maximum allowed result limit (default: 100)
- `ENABLE_SEARCH_INDEXING`: feature flag to enable/disable chunking and embedding (default: true)

#### Scenario: Default configuration with base profile

- **WHEN** the `base` profile is active (or no profile overrides search settings)
- **THEN** the system uses local sentence-transformers (`all-MiniLM-L6-v2`, 384 dims) for embeddings
- **AND** auto-detects the best available BM25 strategy
- **AND** disables cross-encoder reranking
- **AND** uses default values for all other parameters

#### Scenario: Production profile enables cloud providers

- **WHEN** the `railway` or `staging` profile is active
- **THEN** the system uses OpenAI `text-embedding-3-small` (1536 dims) for embeddings
- **AND** enables Cohere reranking
- **AND** all other settings inherit from base profile unless explicitly overridden

#### Scenario: Profile precedence for search settings

- **WHEN** `profiles/base.yaml` sets `embedding_provider: local`
- **AND** `profiles/railway.yaml` sets `embedding_provider: openai`
- **AND** `PROFILE=railway` is active
- **THEN** the system uses OpenAI (profile override wins over base default)
- **AND** if `EMBEDDING_PROVIDER=voyage` environment variable is also set, Voyage wins (env vars always take precedence)

#### Scenario: Custom embedding provider

- **WHEN** `EMBEDDING_PROVIDER` is set to "voyage" and `EMBEDDING_MODEL` is set to "voyage-3-lite"
- **THEN** the system uses Voyage AI with the lite model
- **AND** `EMBEDDING_DIMENSIONS` defaults to 512

#### Scenario: Reranking enabled with Cohere

- **WHEN** `SEARCH_RERANK_ENABLED` is true and `SEARCH_RERANK_PROVIDER` is "cohere"
- **THEN** the system applies Cohere reranking after RRF fusion
- **AND** reranks the top 50 candidates by default

#### Scenario: Search indexing disabled

- **WHEN** `ENABLE_SEARCH_INDEXING` is set to false
- **THEN** documents are ingested without chunking or embedding
- **AND** only BM25 search is available (no vector or hybrid search)

#### Scenario: Local embedding for air-gapped deployment

- **WHEN** `EMBEDDING_PROVIDER` is set to "local"
- **THEN** the system does not require external API connectivity for embeddings

#### Scenario: Per-source chunking in source configuration

- **WHEN** a source entry in `sources.d/` specifies `chunk_size_tokens`, `chunk_overlap_tokens`, or `chunking_strategy`
- **THEN** those values take precedence over global `Settings` defaults for content from that source
- **AND** the cascading order is: global Settings → _defaults.yaml → per-file defaults → per-entry fields

#### Scenario: BM25 strategy override with unavailable extension

- **WHEN** `SEARCH_BM25_STRATEGY` is set to "paradedb" but pg_search is not installed (e.g., bare PostgreSQL without extensions)
- **THEN** the system raises a configuration error at startup
- **AND** the error message indicates pg_search is required for the "paradedb" strategy

#### Scenario: Embedding dimension mismatch with existing data

- **WHEN** `EMBEDDING_DIMENSIONS` is changed to a value different from existing chunk embeddings
- **THEN** the system logs a warning at startup about dimension mismatch
- **AND** existing embeddings are not usable for vector search until re-indexed via backfill

---

### Requirement: Chunk and Embedding Backfill

The system SHALL provide a mechanism to chunk and generate embeddings for existing documents.

The system SHALL chunk from existing `Content.markdown_content` (parsers already ran at ingest time; backfill does NOT re-fetch raw sources or re-run parsers).

The system SHALL support batch processing with configurable batch size.

The system SHALL track progress and support resumption after interruption.

The system SHALL respect API rate limits during embedding generation.

#### Scenario: Backfill existing content

- **WHEN** the backfill command is executed
- **THEN** the system identifies content without chunks (and chunks with NULL embeddings)
- **AND** chunks each content record's `markdown_content` using parser-appropriate strategy
- **AND** skips content records that already have chunks with non-NULL embeddings
- **AND** generates and stores embeddings for each chunk
- **AND** reports progress periodically

#### Scenario: Backfill resumes after interruption

- **WHEN** the backfill is interrupted and restarted
- **THEN** the system resumes from the last processed content_id
- **AND** does not regenerate chunks for already-processed content

#### Scenario: Rate limiting during backfill

- **WHEN** the embedding API returns a rate limit error
- **THEN** the system waits and retries with exponential backoff

#### Scenario: Backfill progress reporting

- **WHEN** backfill is running
- **THEN** the system reports documents processed, chunks created, and estimated time remaining
- **AND** supports dry-run mode to preview without making changes

---

### Requirement: Chunk Lifecycle Management

The system SHALL automatically delete all associated `DocumentChunk` records when a `Content` record is deleted (via `ON DELETE CASCADE` foreign key).

The system SHALL delete existing chunks and regenerate them when `Content.markdown_content` is updated and search indexing is enabled.

The system SHALL not update chunks when non-content fields are modified (e.g., status, tags).

#### Scenario: Content deletion cascades to chunks

- **WHEN** a Content record is deleted
- **THEN** all DocumentChunk records with that `content_id` are automatically deleted
- **AND** no orphan chunks remain in the database

#### Scenario: Content update triggers rechunking

- **WHEN** `Content.markdown_content` is updated
- **AND** `ENABLE_SEARCH_INDEXING` is true
- **THEN** the system deletes all existing chunks for that content_id
- **AND** re-chunks the updated markdown content
- **AND** generates new embeddings for the new chunks

#### Scenario: Rechunking failure after content update

- **WHEN** `Content.markdown_content` is updated
- **AND** rechunking or re-embedding fails during the update
- **THEN** the old chunks are already deleted
- **AND** the system logs the error with content_id
- **AND** the content is eligible for the next backfill run to regenerate chunks

#### Scenario: Non-content update does not trigger rechunking

- **WHEN** a Content record's `status` or `tags` are updated (but not `markdown_content`)
- **THEN** existing chunks are not modified

---

### Requirement: Search Performance

The system SHALL execute hybrid search queries (without reranking) in under 1000ms for databases with fewer than 100,000 chunks.

The system SHALL execute cross-encoder reranking of 50 candidates in under 500ms for managed API providers (Cohere, Jina) and under 1000ms for local cross-encoder and LLM providers.

#### Scenario: Hybrid search latency within SLA

- **WHEN** a hybrid search is executed against a database with fewer than 100,000 chunks
- **THEN** the `meta.query_time_ms` value is less than 1000

#### Scenario: Reranking adds bounded latency

- **WHEN** reranking is enabled with a managed API provider (Cohere or Jina)
- **THEN** the reranking step adds less than 500ms to the total query time

#### Scenario: Search performance degrades beyond SLA

- **WHEN** a hybrid search query exceeds the 1000ms SLA (e.g., due to large dataset or slow backend)
- **THEN** the `meta.query_time_ms` value accurately reflects the actual duration
- **AND** the system still returns results (no timeout abort)
- **AND** the SLA violation is detectable by monitoring systems via the response metadata
