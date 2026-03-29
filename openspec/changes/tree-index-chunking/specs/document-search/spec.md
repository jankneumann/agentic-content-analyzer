# document-search Delta Spec — Tree Index Chunking

## MODIFIED Requirements

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
- **TreeIndexChunkingStrategy** (`tree_index`): For hierarchical tree index construction from heading hierarchy (H1-H6) on long structured documents

The system SHALL support per-source chunking configuration via `sources.d/` YAML files, allowing override of chunk size, overlap, and chunking strategy at the global, per-type, or per-entry level.

The system SHALL resolve chunking parameters using the existing cascading defaults: global `Settings` → `sources.d/_defaults.yaml` → per-file defaults → per-entry fields (most specific wins).

The system SHALL use the default markdown chunking strategy when `Content.parser_used` is NULL or unrecognized and no `chunking_strategy` override is configured for the source.

The system SHALL produce zero chunks (and log a warning) when `Content.markdown_content` is empty or NULL.

The system SHALL target ~512 tokens per chunk with ~64 tokens overlap between consecutive chunks, unless overridden by per-source configuration.

The system SHALL keep tables as whole chunks even if they exceed the target size (up to 2048 tokens).

The system SHALL apply chunk thinning as a post-processing step in `MarkdownChunkingStrategy` and `StructuredChunkingStrategy`, after initial heading-based splitting and before chunk index assignment. Thinning SHALL merge undersized chunks into adjacent chunks when a chunk's token count falls below the configured `min_node_tokens` threshold (default: 50 tokens).

The system SHALL merge an undersized chunk into the preceding chunk (append), or into the following chunk (prepend) if no preceding chunk exists. The system SHALL preserve the `section_path` and `heading_text` of the larger (absorbing) chunk during merging.

The system SHALL NOT merge chunks with `chunk_type` of TABLE or CODE during thinning, regardless of their token count. Thinning SHALL only apply to PARAGRAPH and SECTION chunk types, preserving semantic classification of specialized content.

The system SHALL expose `min_node_tokens` as a configurable setting with a default of 50. Setting `min_node_tokens` to 0 SHALL disable thinning entirely.

The system SHALL auto-select `TreeIndexChunkingStrategy` when ALL of the following conditions are met:
1. The content's `markdown_content` exceeds `tree_index_min_tokens` (default: 8000 tokens)
2. The content's heading hierarchy has depth >= `tree_index_min_heading_depth` (default: 3, e.g., H1 > H2 > H3)

The system SHALL always create flat chunks (via the standard strategy) in addition to tree index chunks. Tree indexing is additive, never replacing flat chunks.

The system SHALL store tree relationships using:
- `parent_chunk_id`: Nullable self-referential FK on `document_chunks` pointing to the parent node
- `tree_depth`: Integer indicating the node's depth in the tree (0 = root). Flat chunks have `tree_depth=NULL`. `tree_depth` is the authoritative discriminator between flat and tree chunks — `parent_chunk_id` is NULL for both flat chunks and tree root nodes.
- `is_summary`: Boolean indicating whether the chunk contains an LLM-generated summary (internal node) vs. actual content (leaf node)

The system SHALL generate LLM summaries for internal (non-leaf) tree nodes using the model resolved via `ModelStep.TREE_SUMMARIZATION` enum → env var `MODEL_TREE_SUMMARIZATION` → DB override → YAML default (`claude-haiku-4-5`). This follows the existing model resolution pattern — it is NOT a Settings field.

The system SHALL perform LLM summarization as an async post-processing step in `index_content()` (following the existing async embedding pattern in `indexing.py`), NOT within the synchronous `ChunkingStrategy.chunk()` method. The `TreeIndexChunkingStrategy.chunk()` method SHALL remain synchronous, building the tree structure and creating placeholder summary chunks with empty `chunk_text`. The indexing service SHALL populate summaries asynchronously after chunk insertion.

The system SHALL parallelize sibling node summarization via `asyncio.gather()` bounded by `asyncio.Semaphore(settings.tree_summarization_max_concurrent)` (default: 10) — nodes at the same tree depth with the same parent are independent and can be summarized concurrently. Bottom-up ordering requires children to be summarized before parents, but not sequential processing within a depth level. The Semaphore prevents rate limit exhaustion on documents with many sibling nodes.

The system SHALL store internal node summaries as `DocumentChunk` records with `is_summary=True` and `chunk_type=SECTION`. No new `ChunkType` enum value is needed — the existing `SECTION` value is reused for summary nodes, disambiguated by the `is_summary` boolean.

The system SHALL store leaf nodes as `DocumentChunk` records with `is_summary=False` and the appropriate `chunk_type` (PARAGRAPH, TABLE, CODE, etc.).

The system SHALL enforce a configurable `tree_max_depth` limit (default: 10) during tree construction. Heading nesting beyond this depth SHALL be merged into the deepest allowed parent node.

The system SHALL expose the following configurable settings with validation bounds:
- `tree_index_min_tokens` (default: 8000, range: 1000–100000)
- `tree_index_min_heading_depth` (default: 3, range: 2–10)
- `tree_summarization_max_concurrent` (default: 10, range: 1–50)
- `tree_max_depth` (default: 10, range: 2–20)

The system SHALL create telemetry spans for tree summarization LLM calls using the existing observability provider. Spans SHALL include `content_id`, `internal_node_count`, and `total_summary_tokens`.

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

#### Scenario: Small fragment merged into preceding chunk

- **WHEN** a heading section produces a chunk with 30 tokens (below the 50-token threshold)
- **AND** a preceding chunk exists
- **THEN** the small chunk's text is appended to the preceding chunk
- **AND** the preceding chunk's `section_path` and `heading_text` are preserved
- **AND** no standalone chunk is created for the 30-token fragment

#### Scenario: Small first chunk merged forward

- **WHEN** the first chunk in a document has 20 tokens (below threshold)
- **AND** a following chunk exists
- **THEN** the small chunk's text is prepended to the following chunk

#### Scenario: Thinning disabled when min_node_tokens is 0

- **WHEN** `min_node_tokens` is set to 0
- **THEN** no chunk merging occurs
- **AND** chunking behavior is identical to the current system

#### Scenario: Table chunk exempt from thinning

- **WHEN** a TABLE chunk has only 25 tokens (below the 50-token threshold)
- **THEN** the TABLE chunk is NOT merged into an adjacent chunk
- **AND** it remains as a standalone chunk with `chunk_type=TABLE` preserved

#### Scenario: Code chunk exempt from thinning

- **WHEN** a CODE chunk has only 15 tokens (below the 50-token threshold)
- **THEN** the CODE chunk is NOT merged into an adjacent chunk
- **AND** it remains as a standalone chunk with `chunk_type=CODE` preserved

#### Scenario: Long PDF auto-selects tree index strategy

- **WHEN** a 15,000-token PDF is parsed by DoclingParser
- **AND** the content has H1 > H2 > H3 heading depth
- **THEN** the system creates flat chunks using `StructuredChunkingStrategy`
- **AND** additionally creates tree index chunks with parent-child relationships
- **AND** internal nodes have LLM-generated summaries (`is_summary=True`)
- **AND** leaf nodes contain actual content (`is_summary=False`)

#### Scenario: Short document does not get tree indexed

- **WHEN** a 3,000-token newsletter is ingested
- **THEN** only flat chunks are created using the standard strategy
- **AND** no tree index is built
- **AND** no `parent_chunk_id` or `tree_depth` values are set

#### Scenario: Document with shallow headings does not get tree indexed

- **WHEN** a 12,000-token document has only H1 and H2 headings (depth 2)
- **THEN** only flat chunks are created
- **AND** no tree index is built (heading depth < tree_index_min_heading_depth)

#### Scenario: Tree index coexists with flat chunks

- **WHEN** a qualifying document is indexed
- **THEN** both flat chunks (for BM25 + vector search) and tree chunks (for tree search) exist in `document_chunks`
- **AND** flat chunks have `parent_chunk_id=NULL`, `tree_depth=NULL`, `is_summary=NULL`
- **AND** tree chunks have populated `parent_chunk_id` (except root), `tree_depth >= 0`, and `is_summary` values

#### Scenario: Per-source tree index override

- **WHEN** a source entry in `sources.d/` specifies `chunking_strategy: tree_index`
- **THEN** the tree index strategy is used regardless of content length or heading depth
- **AND** flat chunks are still created alongside the tree index

#### Scenario: Re-indexing tree-indexed content

- **WHEN** a tree-indexed document is re-indexed (content updated, manual re-index, or backfill)
- **THEN** all existing flat and tree chunks for that `content_id` are deleted (CASCADE on `parent_chunk_id` handles tree cleanup)
- **AND** new flat and tree chunks are created from the current content
- **AND** new LLM summaries are generated for the new tree structure

#### Scenario: Tree summarization fails during indexing

- **WHEN** LLM summarization fails for one or more internal nodes during tree index construction
- **THEN** the system SHALL delete all tree chunks for that content_id (keeping flat chunks intact)
- **AND** log a warning with the failure details and content_id
- **AND** the content remains searchable via flat BM25 + vector search
- **AND** the indexing operation does not fail overall

## ADDED Requirements

### Requirement: Tree Search Retrieval

The system SHALL provide an LLM-based tree search retrieval path for documents that have tree indexes.

The system SHALL automatically route search queries to tree search when the query matches documents with tree indexes (i.e., documents having chunks with `tree_depth IS NOT NULL`).

The system SHALL implement tree search as follows:
1. Load the tree structure for matching documents (summaries and hierarchy only, no leaf text)
2. Assign compact sequential node identifiers (e.g., `N001`, `N002`) when constructing the tree JSON for the LLM prompt. These identifiers SHALL be mapped back to database chunk IDs for retrieval. This keeps prompts concise and avoids confusing the LLM with large arbitrary integers.
3. Send the tree structure and query to an LLM using a managed prompt template (`search.tree_search`)
4. Parse the LLM response to extract selected `node_id` values and reasoning
5. Fetch actual text content from selected leaf nodes (and their descendants)
6. Optionally rerank the retrieved content using the existing reranking infrastructure

The system SHALL use the model resolved via `ModelStep.TREE_SEARCH` enum → env var `MODEL_TREE_SEARCH` → DB override → YAML default (`claude-haiku-4-5`). This follows the existing model resolution pattern — it is NOT a Settings field.

The system SHALL limit tree search to a configurable maximum number of documents per query (default: 3, setting: `tree_search_max_documents`). When more tree-indexed documents match, the system SHALL select the top-N by BM25/vector pre-score and fall back to flat search for the remainder.

The system SHALL execute tree search calls concurrently via `asyncio.gather()` when multiple tree-indexed documents are searched in a single query.

The system SHALL enforce a per-document tree search timeout (default: 5 seconds, setting: `tree_search_timeout_seconds`). Documents exceeding the timeout SHALL fall back to flat hybrid search for that document.

The system SHALL return tree search results as chunk-level candidates with scores (not pre-aggregated `SearchResult` objects). Tree search chunk scores SHALL feed into the existing `_calculate_rrf()` as a third score source alongside BM25 and vector scores. Document-level `SearchResult` objects SHALL be assembled by `_aggregate_to_documents()` after RRF fusion, with `tree_reasoning` populated from tree search metadata.

The system SHALL limit the number of selected nodes per document to `tree_search_max_selected_nodes` (default: 10). If the LLM returns more nodes, the system SHALL truncate to the first N and log an informational message.

The system SHALL add `tree_reasoning: str | None = None` to the `SearchResult` model to store the LLM's reasoning trace for tree search results. This field SHALL be `None` for results retrieved via flat hybrid search.

The system SHALL expose the following configurable settings with validation bounds:
- `tree_search_enabled` (default: `True`)
- `tree_search_max_documents` (default: 3, range: 1–20)
- `tree_search_timeout_seconds` (default: 5, range: 1–30)
- `tree_search_max_selected_nodes` (default: 10, range: 1–50)

The system SHALL fall back to flat hybrid search when tree search fails (LLM error, timeout, invalid response).

The system SHALL create telemetry spans for tree search LLM calls using the existing observability provider. Spans SHALL include: `tree_depth` (max depth of tree), `node_count` (total nodes in tree), `query`, `selected_node_ids` (from LLM response), and `duration_ms`.

#### Scenario: Search query hits tree-indexed document

- **WHEN** a user searches for "What training techniques does DeepSeek-R1 use?"
- **AND** a tree-indexed arXiv paper about DeepSeek-R1 exists in the corpus
- **THEN** the system loads the paper's tree structure (summaries, no text)
- **AND** sends the tree + query to the LLM
- **AND** the LLM reasons about which sections contain the answer
- **AND** the system retrieves leaf content from selected tree nodes
- **AND** results are merged with any BM25/vector results via RRF

#### Scenario: Search query hits mix of tree-indexed and flat-indexed documents

- **WHEN** a search query matches both tree-indexed PDFs and flat-indexed newsletters
- **THEN** the system runs tree search for tree-indexed documents
- **AND** runs standard BM25 + vector search for flat-indexed documents
- **AND** merges all results via RRF into a single ranked result set

#### Scenario: Tree search LLM call fails

- **WHEN** the tree search LLM call fails (timeout, rate limit, invalid JSON response)
- **THEN** the system falls back to standard BM25 + vector search for that document
- **AND** logs a warning with the failure details
- **AND** the overall search request still succeeds

#### Scenario: Tree search disabled via setting

- **WHEN** `tree_search_enabled` is set to `False`
- **THEN** all documents are searched using standard BM25 + vector hybrid search
- **AND** tree indexes in the database are ignored (not deleted)

#### Scenario: Tree search respects max documents limit

- **WHEN** a search query matches 7 tree-indexed documents
- **AND** `tree_search_max_documents` is set to 3
- **THEN** the system runs tree search for the top 3 documents (by BM25/vector pre-score)
- **AND** the remaining 4 documents are searched via standard flat hybrid search
- **AND** all results are merged via RRF

#### Scenario: Tree search times out for one document

- **WHEN** a tree search LLM call for document A exceeds `tree_search_timeout_seconds` (5s)
- **AND** tree search for document B completes within the timeout
- **THEN** document A falls back to flat hybrid search
- **AND** document B uses tree search results
- **AND** results from both paths are merged via RRF
- **AND** a warning is logged for the timeout on document A

#### Scenario: Tree search results include reasoning

- **WHEN** a tree search returns results for a document
- **THEN** the `SearchResult.tree_reasoning` field contains the LLM's reasoning trace
- **AND** flat hybrid search results have `tree_reasoning=None`

#### Scenario: Tree search prompt uses compact node IDs

- **WHEN** the system constructs the tree JSON for the LLM prompt
- **THEN** node identifiers are compact sequential strings (e.g., `N001`, `N002`, `N003`)
- **AND** the system maintains a mapping from compact IDs to database chunk IDs
- **AND** the LLM response's `node_list` uses compact IDs which are resolved back to chunk IDs

#### Scenario: Tree search node selection capped

- **WHEN** a tree search LLM response returns 15 node IDs
- **AND** `tree_search_max_selected_nodes` is set to 10
- **THEN** the system uses only the first 10 node IDs
- **AND** logs an informational message about the truncation
- **AND** the search still succeeds with the truncated set

#### Scenario: Tree search pre-ranks documents by existing scores

- **WHEN** a search query matches 5 tree-indexed documents
- **AND** `tree_search_max_documents` is set to 3
- **THEN** the system selects the top 3 documents using BM25/vector pre-scores from the initial candidate generation
- **AND** the remaining 2 documents are searched via standard flat hybrid search
- **AND** selection is deterministic based on pre-scores

#### Scenario: Tree search prompt managed via prompt system

- **WHEN** a user runs `aca prompts show search.tree_search`
- **THEN** the system displays the tree search prompt template
- **AND** the prompt can be customized via `aca prompts set search.tree_search --value "..."`

### Requirement: Tree Index Backfill

The system SHALL provide a `backfill-tree-index` management command to build tree indexes for existing qualifying content.

The system SHALL scan existing content records and build tree indexes for content that meets the tree index qualification criteria (token count > `tree_index_min_tokens` AND heading depth >= `tree_index_min_heading_depth`).

The system SHALL support a `--dry-run` flag that previews what would be indexed without making changes.

The system SHALL support a `--content-id` flag to target specific content for tree indexing.

The system SHALL support a `--force` flag to rebuild tree indexes for content that already has them (deletes existing tree chunks first, preserves flat chunks). Without `--force`, the system SHALL skip content that already has tree chunks.

#### Scenario: Backfill builds tree index for qualifying content

- **WHEN** an admin runs `aca manage backfill-tree-index`
- **AND** content record 42 has 15,000 tokens and heading depth 4
- **AND** content record 42 has no existing tree chunks
- **THEN** the system builds a tree index for content 42
- **AND** reports progress and summary

#### Scenario: Backfill skips already-indexed content

- **WHEN** an admin runs `aca manage backfill-tree-index` without `--force`
- **AND** content record 42 already has tree chunks (`tree_depth IS NOT NULL`)
- **THEN** content 42 is skipped
- **AND** the summary reports it as skipped

#### Scenario: Force backfill rebuilds existing tree index

- **WHEN** an admin runs `aca manage backfill-tree-index --force`
- **AND** content record 42 already has tree chunks
- **THEN** existing tree chunks for content 42 are deleted (flat chunks preserved)
- **AND** a new tree index is built from current content
- **AND** new LLM summaries are generated

#### Scenario: Dry run previews without changes

- **WHEN** an admin runs `aca manage backfill-tree-index --dry-run`
- **THEN** the system lists qualifying content that would be indexed
- **AND** no database changes are made
