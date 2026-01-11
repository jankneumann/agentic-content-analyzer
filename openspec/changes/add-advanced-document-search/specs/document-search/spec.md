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

- **WHEN** new content is ingested
- **THEN** the BM25 index is automatically updated
- **AND** the content is searchable immediately

---

### Requirement: Semantic Document Chunking

The system SHALL split documents into semantically meaningful chunks before generating embeddings.

The system SHALL leverage the structured output from advanced document parsers (DoclingParser, YouTubeParser, MarkItDownParser) to determine chunk boundaries.

The system SHALL store chunks in a `document_chunks` table with metadata linking back to the source document.

The system SHALL use different chunking strategies based on parser type (all content is markdown with unified model):
- **DoclingParser output**: Split on heading boundaries (H1-H6), extract tables as separate chunks, respect page boundaries
- **YouTubeParser output**: Use existing 30-second timestamp window groupings with sentence boundaries
- **MarkItDownParser output**: Split on markdown heading structure, keep code blocks together
- **Default** (Gmail, RSS): Split on heading boundaries, fall back to paragraph splitting
- **Summaries/Digests**: Split on `## Section` headers (Executive Summary, Key Themes, etc.)

#### Scenario: PDF document chunked by structure

- **WHEN** a PDF document is parsed by DoclingParser
- **THEN** the system creates chunks at heading boundaries
- **AND** tables are extracted as separate chunks with caption context
- **AND** each chunk includes the page number metadata

#### Scenario: YouTube transcript chunked by timestamp

- **WHEN** a YouTube transcript is parsed
- **THEN** the system creates chunks using 30-second timestamp windows
- **AND** each chunk includes timestamp_start and timestamp_end metadata
- **AND** each chunk includes a deep_link_url for direct video navigation

#### Scenario: Markdown document chunked by headings

- **WHEN** a markdown document is parsed
- **THEN** the system creates chunks at H1/H2/H3 boundaries
- **AND** each chunk includes the section_path (e.g., "# Intro > ## Setup")
- **AND** code blocks are kept together within chunks

#### Scenario: Newsletter summary chunked by section

- **WHEN** a newsletter summary is chunked
- **THEN** the system creates chunks for each section (executive summary, key themes, etc.)
- **AND** each chunk includes the section type as chunk_type

#### Scenario: Oversized section split into paragraphs

- **WHEN** a section exceeds the target chunk size (512 tokens)
- **THEN** the system splits the section at paragraph boundaries
- **AND** includes overlap between consecutive chunks for context continuity

---

### Requirement: Chunk Embedding Storage

The system SHALL store chunk embeddings as vector columns using the pgvector extension.

The system SHALL generate embeddings for each chunk using a configurable embedding model (default: OpenAI text-embedding-3-small).

The system SHALL create HNSW indexes on chunk embedding columns for fast approximate nearest neighbor search.

The system SHALL support batch embedding generation for efficiency.

#### Scenario: Chunks embedded on document ingestion

- **WHEN** a document is ingested and chunked
- **THEN** the system generates embeddings for all chunks
- **AND** stores embeddings in the document_chunks.embedding column

#### Scenario: Batch embedding for multiple chunks

- **WHEN** a document produces multiple chunks
- **THEN** the system batches embedding requests for efficiency
- **AND** respects API rate limits

#### Scenario: Chunk metadata preserved with embedding

- **WHEN** a chunk embedding is stored
- **THEN** the chunk retains all structural metadata (section_path, page_number, timestamps, deep_link_url)
- **AND** can be traced back to its source document

---

### Requirement: Chunk-Level Vector Similarity Search

The system SHALL support semantic search using vector cosine similarity on document chunks.

The system SHALL convert user queries to embeddings using the same model used for chunk embeddings.

The system SHALL search against chunk embeddings and aggregate results to document level.

The system SHALL return results with matching chunks highlighted.

#### Scenario: Semantic search finds conceptually related content

- **WHEN** a user searches for "AI model performance improvements"
- **THEN** the system returns documents containing chunks about related concepts
- **AND** results include documents that may not contain the exact search terms
- **AND** the most relevant chunks are highlighted in the response

#### Scenario: Vector search with query embedding

- **WHEN** a user submits a search query
- **THEN** the system generates an embedding for the query
- **AND** computes cosine similarity against all chunk embeddings
- **AND** aggregates chunk scores to document scores
- **AND** returns documents with their best-matching chunks

#### Scenario: Chunk results include navigation metadata

- **WHEN** a matching chunk is from a YouTube transcript
- **THEN** the result includes a deep_link_url to the exact video timestamp
- **AND** the result includes the timestamp range for the chunk

#### Scenario: Table chunks searchable

- **WHEN** a user searches for "benchmark comparison table"
- **THEN** chunks with chunk_type="table" are searchable
- **AND** table chunks include caption and header context in the search

---

### Requirement: Hybrid Search with RRF Reranking

The system SHALL support hybrid search that combines BM25 document search and chunk-level vector search.

The system SHALL use Reciprocal Rank Fusion (RRF) to combine rankings from both search methods.

The system SHALL aggregate chunk-level vector rankings to document-level before RRF fusion.

The system SHALL allow configurable weights for BM25 and vector components.

The system SHALL use a default RRF k-parameter of 60.

#### Scenario: Hybrid search combines lexical and semantic results

- **WHEN** a user performs a hybrid search for "transformer architecture attention"
- **THEN** the system executes BM25 search on documents
- **AND** executes vector search on chunks and aggregates to documents
- **AND** combines document results using RRF
- **AND** documents appearing in both result sets are ranked higher

#### Scenario: Hybrid search with custom weights

- **WHEN** a user specifies weights {"bm25": 0.7, "vector": 0.3}
- **THEN** the system applies weighted RRF scoring
- **AND** BM25 rankings contribute more to the final score

#### Scenario: RRF handles disjoint result sets

- **WHEN** BM25 and vector search return completely different documents
- **THEN** RRF assigns scores based on individual rankings
- **AND** all documents from both methods appear in combined results

#### Scenario: Hybrid results include best matching chunks

- **WHEN** hybrid search returns a document
- **THEN** the result includes the top matching chunks from vector search
- **AND** chunks are ordered by their similarity scores

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
- GET /api/v1/search/chunks/{chunk_id} - Retrieve specific chunk details

The system SHALL return results with:
- id: document identifier
- type: document type (newsletter, document, summary)
- title: document title
- score: combined relevance score
- scores: individual scores by method (bm25, vector, rrf)
- metadata: source, published_date, publication
- matching_chunks: list of relevant chunks with:
  - chunk_id: unique chunk identifier
  - content: chunk text content
  - section: section path or heading
  - score: chunk similarity score
  - highlight: text with matching terms highlighted
  - deep_link: direct URL to chunk location (if available)
  - chunk_type: paragraph, table, code, quote, or transcript

#### Scenario: GET search with query parameter

- **WHEN** a client sends GET /api/v1/search?q=machine+learning&limit=10
- **THEN** the system performs a hybrid search
- **AND** returns up to 10 document results with matching chunks

#### Scenario: POST search with JSON body

- **WHEN** a client sends POST /api/v1/search with JSON body
- **THEN** the system parses search query, type, weights, and filters
- **AND** executes the specified search type
- **AND** returns results with matching chunks

#### Scenario: Search response includes timing

- **WHEN** a search is executed
- **THEN** the response includes query_time_ms
- **AND** the response includes total count of matching documents

#### Scenario: Pagination support

- **WHEN** a user specifies offset=20 and limit=10
- **THEN** the system skips the first 20 results
- **AND** returns results 21-30

#### Scenario: Filter by chunk type

- **WHEN** a user specifies chunk_types=["table", "code"]
- **THEN** only chunks of those types are included in vector search
- **AND** results highlight matching table and code chunks

#### Scenario: Chunk detail retrieval

- **WHEN** a client requests GET /api/v1/search/chunks/{chunk_id}
- **THEN** the system returns the full chunk with all metadata
- **AND** includes the source document reference

---

### Requirement: Search Configuration

The system SHALL support configuration of search parameters via environment variables.

The system SHALL provide the following configuration options:
- EMBEDDING_MODEL: embedding model identifier (default: text-embedding-3-small)
- EMBEDDING_PROVIDER: provider name (default: openai)
- EMBEDDING_DIMENSIONS: vector dimensions (default: 1536)
- CHUNK_SIZE_TOKENS: target chunk size in tokens (default: 512)
- CHUNK_OVERLAP_TOKENS: overlap between chunks in tokens (default: 64)
- SEARCH_BM25_WEIGHT: BM25 weight for hybrid search (default: 0.5)
- SEARCH_VECTOR_WEIGHT: vector weight for hybrid search (default: 0.5)
- SEARCH_RRF_K: RRF k-parameter (default: 60)
- SEARCH_DEFAULT_LIMIT: default result limit (default: 20)
- SEARCH_MAX_LIMIT: maximum allowed result limit (default: 100)
- ENABLE_SEARCH_INDEXING: feature flag to enable/disable chunking and embedding (default: true)

#### Scenario: Default configuration

- **WHEN** no search configuration is specified
- **THEN** the system uses default values for all parameters

#### Scenario: Custom embedding model

- **WHEN** EMBEDDING_MODEL is set to "text-embedding-3-large"
- **THEN** the system uses that model for embedding generation
- **AND** EMBEDDING_DIMENSIONS should be updated accordingly

#### Scenario: Custom chunk size

- **WHEN** CHUNK_SIZE_TOKENS is set to 256
- **THEN** the system creates smaller chunks for finer-grained search
- **AND** more chunks are created per document

#### Scenario: Search indexing disabled

- **WHEN** ENABLE_SEARCH_INDEXING is set to false
- **THEN** documents are ingested without chunking or embedding
- **AND** only BM25 search is available

---

### Requirement: Chunk and Embedding Backfill

The system SHALL provide a mechanism to chunk and generate embeddings for existing documents.

The system SHALL re-parse documents using the appropriate parser (DoclingParser, YouTubeParser, MarkItDownParser) to extract structure.

The system SHALL support batch processing with configurable batch size.

The system SHALL track progress and support resumption after interruption.

The system SHALL respect API rate limits during embedding generation.

#### Scenario: Backfill existing newsletters

- **WHEN** the backfill command is executed
- **THEN** the system identifies documents without chunks
- **AND** re-parses each document with the appropriate parser
- **AND** chunks the content using parser-appropriate strategy
- **AND** generates and stores embeddings for each chunk
- **AND** reports progress periodically

#### Scenario: Backfill resumes after interruption

- **WHEN** the backfill is interrupted and restarted
- **THEN** the system resumes from the last processed document
- **AND** does not regenerate chunks for already-processed documents

#### Scenario: Rate limiting during backfill

- **WHEN** the embedding API returns a rate limit error
- **THEN** the system waits and retries with exponential backoff
- **AND** continues processing after the wait period

#### Scenario: Backfill progress reporting

- **WHEN** backfill is running
- **THEN** the system reports documents processed, chunks created, and estimated time remaining
- **AND** supports dry-run mode to preview without making changes
