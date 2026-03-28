# document-search Delta Spec — Tree Index Chunking

## Requirement: Chunk Thinning

The system SHALL merge undersized chunks into adjacent chunks when a chunk's token count falls below the configured `min_node_tokens` threshold (default: 50 tokens).

The system SHALL apply chunk thinning as a post-processing step in `MarkdownChunkingStrategy` and `StructuredChunkingStrategy`, after initial heading-based splitting and before chunk index assignment.

The system SHALL merge an undersized chunk into the preceding chunk (append), or into the following chunk (prepend) if no preceding chunk exists.

The system SHALL preserve the `section_path` and `heading_text` of the larger (absorbing) chunk during merging.

The system SHALL NOT merge chunks with `chunk_type` of TABLE or CODE during thinning, regardless of their token count. Thinning SHALL only apply to PARAGRAPH and SECTION chunk types, preserving semantic classification of specialized content.

The system SHALL expose `min_node_tokens` as a configurable setting with a default of 50.

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

---

## Requirement: Tree Index Chunking Strategy

The system SHALL provide a `TreeIndexChunkingStrategy` (`tree_index`) that builds a hierarchical tree structure from document heading hierarchy (H1-H6).

The system SHALL register `tree_index` in the `STRATEGY_REGISTRY` alongside existing strategies.

The system SHALL auto-select `TreeIndexChunkingStrategy` when ALL of the following conditions are met:
1. The content's `markdown_content` exceeds `tree_index_min_tokens` (default: 8000 tokens)
2. The content's heading hierarchy has depth >= 3 (e.g., H1 > H2 > H3)

The system SHALL always create flat chunks (via the standard strategy) in addition to tree index chunks. Tree indexing is additive, never replacing flat chunks.

The system SHALL store tree relationships using:
- `parent_chunk_id`: Nullable self-referential FK on `document_chunks` pointing to the parent node
- `tree_depth`: Integer indicating the node's depth in the tree (0 = root)
- `is_summary`: Boolean indicating whether the chunk contains an LLM-generated summary (internal node) vs. actual content (leaf node)

The system SHALL generate LLM summaries for internal (non-leaf) tree nodes using the model configured via `MODEL_TREE_SUMMARIZATION` (resolved via `ModelStep.TREE_SUMMARIZATION` enum in `src/config/models.py`, default: `claude-haiku-4-5`).

The system SHALL perform LLM summarization as an async post-processing step in `index_content()` (following the existing async embedding pattern in `indexing.py`), NOT within the synchronous `ChunkingStrategy.chunk()` method. The `TreeIndexChunkingStrategy.chunk()` method SHALL remain synchronous, building the tree structure and creating placeholder summary chunks with empty `chunk_text`. The indexing service SHALL populate summaries asynchronously after chunk insertion.

The system SHALL parallelize sibling node summarization via `asyncio.gather()` — nodes at the same tree depth with the same parent are independent and can be summarized concurrently. Bottom-up ordering only requires children to be summarized before parents, not sequential processing within a depth level.

The system SHALL store internal node summaries as `DocumentChunk` records with `is_summary=True` and `chunk_type=SECTION`. No new `ChunkType` enum value is needed — the existing `SECTION` value is reused for summary nodes.

The system SHALL store leaf nodes as `DocumentChunk` records with `is_summary=False` and the appropriate `chunk_type` (PARAGRAPH, TABLE, CODE, etc.).

The system SHALL distinguish flat chunks from tree chunks using the `tree_depth` column: flat chunks have `tree_depth=NULL`, tree root nodes have `tree_depth=0`, and tree children have `tree_depth >= 1`. The `parent_chunk_id` column is `NULL` for both flat chunks and tree root nodes; `tree_depth` is the authoritative discriminator.

The system SHALL expose `tree_index_min_tokens` as a configurable setting (default: 8000).

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
- **AND** no tree index is built (heading depth < 3)

#### Scenario: Tree index coexists with flat chunks

- **WHEN** a qualifying document is indexed
- **THEN** both flat chunks (for BM25 + vector search) and tree chunks (for tree search) exist in `document_chunks`
- **AND** flat chunks have `parent_chunk_id=NULL`, `tree_depth=NULL`, `is_summary=NULL`
- **AND** tree chunks have populated `parent_chunk_id`, `tree_depth`, and `is_summary` values

#### Scenario: Per-source tree index override

- **WHEN** a source entry in `sources.d/` specifies `chunking_strategy: tree_index`
- **THEN** the tree index strategy is used regardless of content length or heading depth
- **AND** flat chunks are still created alongside the tree index

#### Scenario: Re-indexing tree-indexed content

- **WHEN** a tree-indexed document is re-indexed (content updated, manual re-index, or backfill)
- **THEN** all existing flat and tree chunks for that `content_id` are deleted (CASCADE on `parent_chunk_id` handles tree cleanup)
- **AND** new flat and tree chunks are created from the current content
- **AND** new LLM summaries are generated for the new tree structure

---

## Requirement: Tree Search Retrieval

The system SHALL provide an LLM-based tree search retrieval path for documents that have tree indexes.

The system SHALL automatically route search queries to tree search when the query matches documents with tree indexes (i.e., documents having chunks with `tree_depth IS NOT NULL`).

The system SHALL implement tree search as follows:
1. Load the tree structure for matching documents (summaries and hierarchy only, no leaf text)
2. Assign compact sequential node identifiers (e.g., `N001`, `N002`) when constructing the tree JSON for the LLM prompt. These identifiers SHALL be mapped back to database chunk IDs for retrieval. This keeps prompts concise and avoids confusing the LLM with large arbitrary integers.
3. Send the tree structure and query to an LLM using a managed prompt template (`search.tree_search`)
4. Parse the LLM response to extract selected `node_id` values and reasoning
5. Fetch actual text content from selected leaf nodes (and their descendants)
6. Optionally rerank the retrieved content using the existing reranking infrastructure

The system SHALL use the model configured via `MODEL_TREE_SEARCH` (resolved via `ModelStep.TREE_SEARCH` enum in `src/config/models.py`, default: `claude-haiku-4-5`) for tree search LLM calls.

The system SHALL limit tree search to a configurable maximum number of documents per query (default: 3, setting: `tree_search_max_documents`). When more tree-indexed documents match, the system SHALL select the top-N by BM25/vector pre-score and fall back to flat search for the remainder.

The system SHALL execute tree search calls concurrently via `asyncio.gather()` when multiple tree-indexed documents are searched in a single query.

The system SHALL enforce a per-document tree search timeout (default: 5 seconds, setting: `tree_search_timeout_seconds`). Documents exceeding the timeout SHALL fall back to flat hybrid search for that document.

The system SHALL merge tree search results with flat hybrid search results (BM25 + vector) using the existing Reciprocal Rank Fusion mechanism.

The system SHALL add `tree_reasoning: str | None = None` to the `SearchResult` model to store the LLM's reasoning trace for tree search results. This field SHALL be `None` for results retrieved via flat hybrid search.

The system SHALL expose `tree_search_enabled` as a configurable setting (default: `True`).

The system SHALL fall back to flat hybrid search when tree search fails (LLM error, timeout, invalid response).

The system SHALL create telemetry spans for tree search LLM calls using the existing observability provider. Spans SHALL include: `tree_depth` (max depth of tree), `node_count` (total nodes in tree), `query`, `selected_node_ids` (from LLM response), and `duration_ms`. Tree summarization during indexing SHALL also create telemetry spans with `content_id`, `internal_node_count`, and `total_summary_tokens`.

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
- **THEN** the `SearchResult.tree_reasoning` field contains the LLM's reasoning trace (e.g., "Section 2.1 covers RL training and Section 3.2 covers evaluation results")
- **AND** flat hybrid search results have `tree_reasoning=None`

#### Scenario: Tree search prompt uses compact node IDs

- **WHEN** the system constructs the tree JSON for the LLM prompt
- **THEN** node identifiers are compact sequential strings (e.g., `N001`, `N002`, `N003`)
- **AND** the system maintains a mapping from compact IDs to database chunk IDs
- **AND** the LLM response's `node_list` uses compact IDs which are resolved back to chunk IDs

#### Scenario: Tree search prompt managed via prompt system

- **WHEN** a user runs `aca prompts show search.tree_search`
- **THEN** the system displays the tree search prompt template
- **AND** the prompt can be customized via `aca prompts set search.tree_search --value "..."`
