# Document Search Specification

## ADDED Requirements

### Requirement: BM25 Full-Text Search

The system SHALL provide BM25-based full-text search across ingested documents using the pg_search extension.

The system SHALL create BM25 indexes on the following fields:
- newsletters: title, raw_text, sender, publication
- documents: filename, markdown_content
- newsletter_summaries: executive_summary

The system SHALL return search results ordered by BM25 relevance score.

The system SHALL support the `@@@` operator for BM25 queries.

#### Scenario: Basic keyword search returns relevant results

- **WHEN** a user searches for "machine learning transformers"
- **THEN** the system returns newsletters containing those terms
- **AND** results are ordered by BM25 relevance score (highest first)
- **AND** each result includes the relevance score

#### Scenario: BM25 search with no matches

- **WHEN** a user searches for a query with no matching documents
- **THEN** the system returns an empty result set
- **AND** the total count is 0

#### Scenario: BM25 index auto-updates on insert

- **WHEN** a new newsletter is ingested
- **THEN** the BM25 index is automatically updated
- **AND** the new document is searchable immediately

---

### Requirement: Vector Embedding Storage

The system SHALL store document embeddings as vector columns using the pgvector extension.

The system SHALL generate embeddings using a configurable embedding model (default: OpenAI text-embedding-3-small).

The system SHALL create HNSW indexes on embedding columns for fast approximate nearest neighbor search.

The system SHALL truncate documents exceeding the embedding model's context limit before generating embeddings.

#### Scenario: Embedding generated on newsletter ingestion

- **WHEN** a newsletter is ingested
- **THEN** the system generates an embedding from the title and content
- **AND** stores the embedding in the newsletter's embedding column

#### Scenario: Embedding generated for uploaded document

- **WHEN** a document is uploaded and parsed
- **THEN** the system generates an embedding from the markdown content
- **AND** stores the embedding in the document's embedding column

#### Scenario: Long document truncation

- **WHEN** a document exceeds 8000 characters
- **THEN** the system truncates the text before embedding generation
- **AND** the truncation preserves the beginning of the document

---

### Requirement: Vector Similarity Search

The system SHALL support semantic search using vector cosine similarity.

The system SHALL convert user queries to embeddings using the same model used for document embeddings.

The system SHALL return results ordered by vector similarity score (cosine distance).

#### Scenario: Semantic search finds conceptually related content

- **WHEN** a user searches for "AI model performance improvements"
- **THEN** the system returns documents about related concepts (optimization, fine-tuning, benchmarks)
- **AND** results include documents that may not contain the exact search terms

#### Scenario: Vector search with query embedding

- **WHEN** a user submits a search query
- **THEN** the system generates an embedding for the query
- **AND** computes cosine similarity against all document embeddings
- **AND** returns the most similar documents

---

### Requirement: Hybrid Search with RRF Reranking

The system SHALL support hybrid search that combines BM25 and vector search results.

The system SHALL use Reciprocal Rank Fusion (RRF) to combine rankings from both search methods.

The system SHALL allow configurable weights for BM25 and vector components.

The system SHALL use a default RRF k-parameter of 60.

#### Scenario: Hybrid search combines lexical and semantic results

- **WHEN** a user performs a hybrid search for "transformer architecture attention"
- **THEN** the system executes both BM25 and vector searches
- **AND** combines results using RRF
- **AND** documents appearing in both result sets are ranked higher

#### Scenario: Hybrid search with custom weights

- **WHEN** a user specifies weights {"bm25": 0.7, "vector": 0.3}
- **THEN** the system applies weighted RRF scoring
- **AND** BM25 rankings contribute more to the final score

#### Scenario: RRF handles disjoint result sets

- **WHEN** BM25 and vector search return completely different documents
- **THEN** RRF assigns scores based on individual rankings
- **AND** all documents from both methods appear in combined results

---

### Requirement: Search Filtering

The system SHALL support filtering search results by metadata fields.

The system SHALL support the following filters:
- sources: list of NewsletterSource values (GMAIL, RSS, FILE_UPLOAD, YOUTUBE, etc.)
- date_from: minimum published date (inclusive)
- date_to: maximum published date (inclusive)
- publications: list of publication names
- statuses: list of ProcessingStatus values

Filters SHALL be applied before search ranking.

#### Scenario: Filter by source type

- **WHEN** a user searches with filter sources=["GMAIL", "RSS"]
- **THEN** only newsletters from Gmail or RSS sources are included in results

#### Scenario: Filter by date range

- **WHEN** a user searches with date_from="2024-01-01" and date_to="2024-06-30"
- **THEN** only documents published within that range are included

#### Scenario: Combined filters

- **WHEN** a user applies multiple filters
- **THEN** all filters are combined with AND logic
- **AND** only documents matching all filters are returned

---

### Requirement: Search API

The system SHALL expose search functionality via REST API endpoints.

The system SHALL provide:
- GET /api/v1/search - Simple query parameter-based search
- POST /api/v1/search - Complex JSON body-based search

The system SHALL return results with:
- id: document identifier
- type: document type (newsletter, document, summary)
- title: document title
- snippet: highlighted text excerpt with matching terms
- score: combined relevance score
- scores: individual scores by method (bm25, vector, rrf)
- metadata: source, published_date, publication

#### Scenario: GET search with query parameter

- **WHEN** a client sends GET /api/v1/search?q=machine+learning&limit=10
- **THEN** the system performs a hybrid search
- **AND** returns up to 10 results with standard response format

#### Scenario: POST search with JSON body

- **WHEN** a client sends POST /api/v1/search with JSON body
- **THEN** the system parses search query, type, weights, and filters
- **AND** executes the specified search type
- **AND** returns results matching the filters

#### Scenario: Search response includes timing

- **WHEN** a search is executed
- **THEN** the response includes query_time_ms
- **AND** the response includes total count of matching documents

#### Scenario: Pagination support

- **WHEN** a user specifies offset=20 and limit=10
- **THEN** the system skips the first 20 results
- **AND** returns results 21-30

---

### Requirement: Search Configuration

The system SHALL support configuration of search parameters via environment variables.

The system SHALL provide the following configuration options:
- EMBEDDING_MODEL: embedding model identifier (default: text-embedding-3-small)
- EMBEDDING_PROVIDER: provider name (default: openai)
- EMBEDDING_DIMENSIONS: vector dimensions (default: 1536)
- SEARCH_BM25_WEIGHT: BM25 weight for hybrid search (default: 0.5)
- SEARCH_VECTOR_WEIGHT: vector weight for hybrid search (default: 0.5)
- SEARCH_RRF_K: RRF k-parameter (default: 60)
- SEARCH_DEFAULT_LIMIT: default result limit (default: 20)
- SEARCH_MAX_LIMIT: maximum allowed result limit (default: 100)

#### Scenario: Default configuration

- **WHEN** no search configuration is specified
- **THEN** the system uses default values for all parameters

#### Scenario: Custom embedding model

- **WHEN** EMBEDDING_MODEL is set to "text-embedding-3-large"
- **THEN** the system uses that model for embedding generation
- **AND** EMBEDDING_DIMENSIONS should be updated accordingly

---

### Requirement: Embedding Backfill

The system SHALL provide a mechanism to generate embeddings for existing documents.

The system SHALL support batch processing with configurable batch size.

The system SHALL track progress and support resumption after interruption.

The system SHALL respect API rate limits during backfill.

#### Scenario: Backfill existing newsletters

- **WHEN** the backfill command is executed
- **THEN** the system processes newsletters with null embeddings
- **AND** generates and stores embeddings for each
- **AND** reports progress periodically

#### Scenario: Backfill resumes after interruption

- **WHEN** the backfill is interrupted and restarted
- **THEN** the system resumes from the last processed document
- **AND** does not regenerate embeddings for already-processed documents

#### Scenario: Rate limiting during backfill

- **WHEN** the embedding API returns a rate limit error
- **THEN** the system waits and retries with exponential backoff
- **AND** continues processing after the wait period
