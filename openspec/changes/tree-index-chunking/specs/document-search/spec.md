# document-search Delta Spec — Tree Index Chunking

## Requirement: Chunk Thinning

The system SHALL merge undersized chunks into adjacent chunks when a chunk's token count falls below the configured `min_node_tokens` threshold (default: 50 tokens).

The system SHALL apply chunk thinning as a post-processing step in `MarkdownChunkingStrategy` and `StructuredChunkingStrategy`, after initial heading-based splitting and before chunk index assignment.

The system SHALL merge an undersized chunk into the preceding chunk (append), or into the following chunk (prepend) if no preceding chunk exists.

The system SHALL preserve the `section_path` and `heading_text` of the larger (absorbing) chunk during merging.

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

The system SHALL generate LLM summaries for internal (non-leaf) tree nodes using the model configured via `MODEL_TREE_SUMMARIZATION` (default: `claude-haiku-4-5`).

The system SHALL store internal node summaries as `DocumentChunk` records with `is_summary=True` and `chunk_type=SECTION`.

The system SHALL store leaf nodes as `DocumentChunk` records with `is_summary=False` and the appropriate `chunk_type` (PARAGRAPH, TABLE, CODE, etc.).

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

---

## Requirement: Tree Search Retrieval

The system SHALL provide an LLM-based tree search retrieval path for documents that have tree indexes.

The system SHALL automatically route search queries to tree search when the query matches documents with tree indexes (i.e., documents having chunks with `parent_chunk_id IS NOT NULL`).

The system SHALL implement tree search as follows:
1. Load the tree structure for matching documents (summaries and hierarchy only, no leaf text)
2. Send the tree structure and query to an LLM using a managed prompt template (`search.tree_search`)
3. Parse the LLM response to extract selected `node_id` values and reasoning
4. Fetch actual text content from selected leaf nodes (and their descendants)
5. Optionally rerank the retrieved content using the existing reranking infrastructure

The system SHALL use the model configured via `MODEL_TREE_SEARCH` (default: `claude-haiku-4-5`) for tree search LLM calls.

The system SHALL merge tree search results with flat hybrid search results (BM25 + vector) using the existing Reciprocal Rank Fusion mechanism.

The system SHALL include the LLM's reasoning trace in search response metadata for explainability.

The system SHALL expose `tree_search_enabled` as a configurable setting (default: `True`).

The system SHALL fall back to flat hybrid search when tree search fails (LLM error, timeout, invalid response).

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

#### Scenario: Tree search prompt managed via prompt system

- **WHEN** a user runs `aca prompts show search.tree_search`
- **THEN** the system displays the tree search prompt template
- **AND** the prompt can be customized via `aca prompts set search.tree_search --value "..."`
