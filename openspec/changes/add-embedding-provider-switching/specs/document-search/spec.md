## MODIFIED Requirements

### Requirement: Chunk Embedding Storage

The system SHALL store chunk embeddings as unconstrained vector columns using the pgvector extension (available on all supported backends).

The system SHALL generate embeddings for each chunk using a configurable embedding provider.

The system SHALL support the following embedding providers:
- **OpenAI**: text-embedding-3-small (1536 dims), text-embedding-3-large (3072 dims)
- **Voyage AI**: voyage-3 (1024 dims), voyage-3-lite (512 dims)
- **Cohere**: embed-english-v3.0 (1024 dims), embed-english-light-v3.0 (384 dims)
- **Local**: Any sentence-transformers model, including instruction-tuned models (e.g., all-MiniLM-L6-v2 at 384 dims, gte-Qwen2-1.5B-instruct at 1536 dims)

The system SHALL select the embedding provider based on configuration (`EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`).

The system SHALL create HNSW indexes on chunk embedding columns for fast approximate nearest neighbor search.

The system SHALL support batch embedding generation for efficiency.

The system SHALL use unconstrained vector columns (`vector` without dimension) so that any provider's dimensions are accepted without schema changes.

The system SHALL record embedding provenance by storing the provider name and model identifier alongside each chunk's embedding.

The system SHALL distinguish between query and document embedding when the provider supports asymmetric encoding:
- **Cohere**: `input_type="search_query"` for queries, `"search_document"` for documents
- **Voyage**: `input_type="query"` for queries, `"document"` for documents
- **Local instruction-tuned models**: `prompt_name="query"` for queries when the model's `prompts` dict includes a "query" key
- **OpenAI**: No distinction (symmetric model)

The system SHALL support `trust_remote_code` for local sentence-transformers models that require it (e.g., `gte-Qwen2-1.5B-instruct`), gated by the `EMBEDDING_TRUST_REMOTE_CODE` setting (default: false).

The system SHALL auto-detect embedding dimensions from loaded local models via `model.get_sentence_embedding_dimension()`, falling back to a known-model lookup and then `EMBEDDING_DIMENSIONS` setting.

The system SHALL support overriding the local model's max sequence length via `EMBEDDING_MAX_SEQ_LENGTH` setting.

#### Scenario: Chunks embedded on document ingestion

- **WHEN** a document is ingested and chunked
- **THEN** the system generates embeddings using the configured provider
- **AND** stores embeddings in the `document_chunks.embedding` column
- **AND** stores the provider name in `document_chunks.embedding_provider`
- **AND** stores the model identifier in `document_chunks.embedding_model`

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
- **AND** uses symmetric encoding (no query/document distinction)

#### Scenario: Local embedding provider with instruction-tuned model

- **WHEN** `EMBEDDING_PROVIDER` is set to "local" and `EMBEDDING_MODEL` is set to "Alibaba-NLP/gte-Qwen2-1.5B-instruct"
- **AND** `EMBEDDING_TRUST_REMOTE_CODE` is true
- **THEN** the system loads the model with `trust_remote_code=True`
- **AND** auto-detects 1536 dimensions from the loaded model
- **AND** uses `prompt_name="query"` for search query embeddings
- **AND** uses plain encoding (no prompt) for document chunk embeddings
- **AND** does not make external API calls

#### Scenario: Local embedding provider with standard model

- **WHEN** `EMBEDDING_PROVIDER` is set to "local" and `EMBEDDING_MODEL` is set to "all-MiniLM-L6-v2"
- **THEN** the system loads the model without `trust_remote_code`
- **AND** uses 384 dimensions
- **AND** uses plain encoding for both queries and documents (model has no query prompt)

#### Scenario: Cohere query vs document embedding

- **WHEN** the system embeds a search query using the Cohere provider
- **THEN** the API call uses `input_type="search_query"`
- **AND** when embedding document chunks, the API call uses `input_type="search_document"`

#### Scenario: Voyage query vs document embedding

- **WHEN** the system embeds a search query using the Voyage provider
- **THEN** the API call uses `input_type="query"`
- **AND** when embedding document chunks, the API call uses `input_type="document"`

#### Scenario: Provider change requires re-indexing

- **WHEN** the embedding provider or model is changed to one with different vector dimensions
- **THEN** the system requires re-indexing of all chunks via `aca manage switch-embeddings`
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

The system SHALL convert user queries to embeddings using the same provider/model used for chunk embeddings, with query-specific encoding when the provider supports asymmetric embedding.

The system SHALL search against chunk embeddings and aggregate results to document level.

The system SHALL return results with matching chunks highlighted.

#### Scenario: Semantic search finds conceptually related content

- **WHEN** a user searches for "AI model performance improvements"
- **THEN** the system returns documents containing chunks about related concepts
- **AND** results include documents that may not contain the exact search terms
- **AND** the most relevant chunks are highlighted in the response

#### Scenario: Vector search with query embedding

- **WHEN** a user submits a search query
- **THEN** the system generates an embedding for the query using the configured provider with query-specific encoding (`is_query=True`)
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

### Requirement: Search Configuration

The system SHALL support configuration of search parameters via environment variables.

**Embedding Configuration:**
- `EMBEDDING_PROVIDER`: provider name (openai, voyage, cohere, local; default: local)
- `EMBEDDING_MODEL`: model identifier within provider (optional, uses provider default)
- `EMBEDDING_DIMENSIONS`: vector dimensions (auto-detected if not specified)
- `EMBEDDING_TRUST_REMOTE_CODE`: trust remote code in sentence-transformers models (default: false)
- `EMBEDDING_MAX_SEQ_LENGTH`: override model's max sequence length (default: model's built-in value)

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

#### Scenario: Instruction-tuned local model configuration

- **WHEN** `EMBEDDING_PROVIDER` is "local" and `EMBEDDING_MODEL` is "Alibaba-NLP/gte-Qwen2-1.5B-instruct"
- **AND** `EMBEDDING_TRUST_REMOTE_CODE` is true
- **AND** `EMBEDDING_MAX_SEQ_LENGTH` is 8192
- **THEN** the model loads with `trust_remote_code=True` and max sequence length overridden to 8192
- **AND** `EMBEDDING_DIMENSIONS` auto-detects to 1536

#### Scenario: Dimension mismatch warning

- **WHEN** `EMBEDDING_DIMENSIONS` is set to a value that does not match the known dimensions for the configured provider/model
- **THEN** the system issues a warning at settings validation time
- **AND** does not prevent startup (unknown models may have custom dimensions)

#### Scenario: Embedding config mismatch at startup

- **WHEN** the API starts and existing embeddings in the database were generated by a different provider/model than the current config
- **THEN** the system logs a warning with the mismatch details
- **AND** suggests running `aca manage switch-embeddings` to re-embed
- **AND** does not prevent startup

#### Scenario: Per-source chunking in source configuration

- **WHEN** a source entry in `sources.d/` specifies `chunk_size_tokens`, `chunk_overlap_tokens`, or `chunking_strategy`
- **THEN** those values take precedence over global `Settings` defaults for content from that source
- **AND** the cascading order is: global Settings → _defaults.yaml → per-file defaults → per-entry fields

#### Scenario: BM25 strategy override with unavailable extension

- **WHEN** `SEARCH_BM25_STRATEGY` is set to "paradedb" but pg_search is not installed
- **THEN** the system raises a configuration error at startup
- **AND** the error message indicates pg_search is required for the "paradedb" strategy

#### Scenario: Embedding dimension mismatch with existing data

- **WHEN** `EMBEDDING_DIMENSIONS` is changed to a value different from existing chunk embeddings
- **THEN** the system logs a warning at startup about dimension mismatch
- **AND** existing embeddings are not usable for vector search until re-indexed via `aca manage switch-embeddings`

---

### Requirement: Chunk and Embedding Backfill

The system SHALL provide a mechanism to chunk and generate embeddings for existing documents.

The system SHALL chunk from existing `Content.markdown_content` (parsers already ran at ingest time; backfill does NOT re-fetch raw sources or re-run parsers).

The system SHALL support batch processing with configurable batch size.

The system SHALL track progress and support resumption after interruption.

The system SHALL respect API rate limits during embedding generation.

The system SHALL record embedding provenance (provider name and model) alongside each generated embedding during backfill.

#### Scenario: Backfill existing content

- **WHEN** the backfill command is executed
- **THEN** the system identifies content without chunks (and chunks with NULL embeddings)
- **AND** chunks each content record's `markdown_content` using parser-appropriate strategy
- **AND** skips content records that already have chunks with non-NULL embeddings
- **AND** generates and stores embeddings for each chunk
- **AND** stores the embedding provider and model metadata for each chunk
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

## ADDED Requirements

### Requirement: Embedding Provider Switching

The system SHALL provide a CLI command `aca manage switch-embeddings` to safely switch between embedding providers.

The system SHALL orchestrate the following steps during a provider switch:
1. Validate the target provider/model can be instantiated
2. NULL all existing embeddings and their metadata
3. Drop the HNSW index on the embedding column
4. Recreate the HNSW index
5. Optionally trigger a backfill to regenerate embeddings with the new provider

The system SHALL support a dry-run mode that previews the switch without making changes.

The system SHALL require confirmation before executing a destructive switch (unless `--yes` flag is provided).

The system SHALL support skipping the backfill step (via `--skip-backfill`) for cases where backfill should be scheduled separately.

#### Scenario: Switch embedding provider

- **WHEN** `aca manage switch-embeddings --provider openai --model text-embedding-3-small --yes` is executed
- **THEN** the system validates that OpenAI with text-embedding-3-small can be instantiated
- **AND** NULLs all existing embeddings and metadata in `document_chunks`
- **AND** drops and recreates the HNSW index
- **AND** triggers a backfill to regenerate all embeddings with OpenAI
- **AND** reports the number of embeddings cleared and regenerated

#### Scenario: Dry run switch

- **WHEN** `aca manage switch-embeddings --provider voyage --model voyage-3 --dry-run` is executed
- **THEN** the system reports what would happen (provider, model, dimensions, affected rows)
- **AND** does not modify the database

#### Scenario: Switch with skip backfill

- **WHEN** `aca manage switch-embeddings --provider local --model all-MiniLM-L6-v2 --skip-backfill --yes` is executed
- **THEN** the system clears embeddings and rebuilds the index
- **AND** does NOT trigger a backfill
- **AND** vector search returns empty results until backfill is run manually

#### Scenario: Switch requires confirmation

- **WHEN** `aca manage switch-embeddings --provider openai --model text-embedding-3-small` is executed without `--yes`
- **THEN** the system prompts for confirmation before proceeding
- **AND** aborting the confirmation cancels the operation with no changes

#### Scenario: Invalid provider or model

- **WHEN** `aca manage switch-embeddings --provider nonexistent --model foo` is executed
- **THEN** the system reports a validation error
- **AND** does not modify the database
- **AND** exit code is 1

#### Scenario: BM25 search during switch

- **WHEN** a provider switch is in progress and embeddings are cleared
- **THEN** BM25 search continues to work normally
- **AND** hybrid search returns BM25-only results (vector component returns empty)
