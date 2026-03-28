# Tasks — Tree Index Chunking

## Phase 1: Chunk Thinning

### Task 1.1: Add `min_node_tokens` setting
- **File**: `src/config/settings.py`
- **Work**: Add `min_node_tokens: int = 50` to `Settings` class alongside existing `chunk_size_tokens` and `chunk_overlap_tokens`
- **Validation**: Setting loads from env/profile, validated >= 0

### Task 1.2: Implement chunk thinning post-processor
- **File**: `src/services/chunking.py`
- **Work**: Create `_thin_chunks(chunks: list[DocumentChunk], min_tokens: int) -> list[DocumentChunk]` function that merges undersized chunks into adjacent chunks. Merge into preceding chunk (append) by default; merge into following chunk (prepend) if no predecessor exists. Preserve `section_path` and `heading_text` of the absorbing chunk. Skip thinning when `min_tokens == 0`.
- **Integration**: Call `_thin_chunks()` as final step in `MarkdownChunkingStrategy.chunk()` and `StructuredChunkingStrategy.chunk()`, before `chunk_index` assignment

### Task 1.3: Add chunk thinning tests
- **File**: `tests/test_services/test_chunking.py`
- **Work**: Test cases for:
  - Small chunk merged into preceding chunk
  - Small first chunk merged into following chunk
  - `min_node_tokens=0` disables thinning
  - Single chunk below threshold (no merge target) preserved as-is
  - Chunk exactly at threshold not merged
  - Multiple consecutive small chunks merged correctly

### Task 1.4: Add `min_node_tokens` to source config
- **File**: `src/config/sources.py`
- **Work**: Add `min_node_tokens` to `SourceDefaults` model so it can be overridden per-source in `sources.d/` YAML files. Follow existing pattern for `chunk_size_tokens` / `chunk_overlap_tokens`.

---

## Phase 2: Tree Index Strategy

### Task 2.1: Database migration — tree columns
- **File**: New file in `alembic/versions/`
- **Work**: Add three nullable columns to `document_chunks`:
  - `parent_chunk_id INTEGER REFERENCES document_chunks(id) ON DELETE CASCADE` (self-referential FK)
  - `tree_depth INTEGER`
  - `is_summary BOOLEAN DEFAULT FALSE`
  - Index on `parent_chunk_id`
  - Composite index on `(content_id, tree_depth)` for tree structure queries
- **Idempotency**: Use `IF NOT EXISTS` / `information_schema` checks per project conventions

### Task 2.2: Update DocumentChunk model
- **File**: `src/models/chunk.py`
- **Work**: Add `parent_chunk_id`, `tree_depth`, `is_summary` columns to `DocumentChunk` ORM model. Add `parent` and `children` relationships for tree navigation. Add `SUMMARY` to `ChunkType` enum if not already present.

### Task 2.3: Add tree index settings
- **File**: `src/config/settings.py`
- **Work**: Add settings:
  - `tree_index_min_tokens: int = 8000` — minimum content tokens to trigger tree indexing
  - `tree_index_min_heading_depth: int = 3` — minimum heading depth to trigger tree indexing
  - `model_tree_summarization: str = "claude-haiku-4-5"` — model for node summary generation

### Task 2.4: Implement TreeIndexChunkingStrategy
- **File**: `src/services/chunking.py`
- **Work**: Create `TreeIndexChunkingStrategy` class implementing `ChunkingStrategy` protocol:
  1. Parse heading hierarchy from markdown content (reuse existing heading regex)
  2. Build tree structure: each heading section becomes a node, nested by heading level
  3. Classify nodes as internal (has children) or leaf (no children)
  4. For leaf nodes: create `DocumentChunk` with actual content, `is_summary=False`
  5. For internal nodes: create `DocumentChunk` with LLM-generated summary, `is_summary=True`
  6. Set `parent_chunk_id` and `tree_depth` on all tree chunks
  7. Return both tree chunks AND flat chunks (delegate to standard strategy for flat)
- **LLM integration**: Use `llm_router` with `model_tree_summarization` for summaries
- **Register**: Add `"tree_index": TreeIndexChunkingStrategy` to `STRATEGY_REGISTRY`

### Task 2.5: Add auto-selection logic for tree index
- **File**: `src/services/chunking.py`
- **Work**: Modify `ChunkingService.chunk_content()` to:
  1. After standard strategy produces flat chunks, check if content qualifies for tree indexing
  2. Qualification: total tokens > `tree_index_min_tokens` AND heading depth >= `tree_index_min_heading_depth`
  3. If qualified, also run `TreeIndexChunkingStrategy` and append tree chunks to flat chunks
  4. Skip if `chunking_strategy` override is explicitly set to something other than `tree_index`
- **Helper**: Add `_detect_heading_depth(content: str) -> int` utility function

### Task 2.6: Update indexing service for tree chunks
- **File**: `src/services/indexing.py`
- **Work**: Ensure `index_content()` handles tree chunks correctly:
  - Summary chunks (`is_summary=True`) get embedded alongside leaf chunks (summaries are searchable via vector)
  - `parent_chunk_id` FK is resolved after initial chunk insertion (parent must exist first)
  - Tree chunks are committed in depth-first order (parents before children)

### Task 2.7: Add tree index tests
- **Files**: `tests/test_services/test_chunking.py`, `tests/test_services/test_indexing.py`
- **Work**: Test cases for:
  - Tree strategy builds correct hierarchy from nested headings
  - Internal nodes get LLM summaries, leaf nodes get content
  - `parent_chunk_id` and `tree_depth` set correctly
  - Auto-selection triggers above token + depth thresholds
  - Auto-selection skipped for short/flat content
  - Flat chunks always created alongside tree chunks
  - Tree index with mocked LLM calls

---

## Phase 3: Tree Search Retrieval

### Task 3.1: Register tree search prompt template
- **File**: `src/processors/prompts/` (or via prompt management system)
- **Work**: Register `search.tree_search` prompt template:
  ```
  You are given a question and a tree structure of a document.
  Each node contains a node_id, title, and summary.
  Find all nodes likely to contain the answer.

  Question: {query}
  Document tree structure:
  {tree_json}

  Reply as JSON: {"thinking": "...", "node_list": ["id1", "id2"]}
  ```
- **Integration**: Managed via existing `aca prompts` system, overridable by users

### Task 3.2: Add tree search settings
- **File**: `src/config/settings.py`
- **Work**: Add settings:
  - `tree_search_enabled: bool = True`
  - `model_tree_search: str = "claude-haiku-4-5"`

### Task 3.3: Implement tree structure loader
- **File**: `src/services/search.py`
- **Work**: Add `_load_tree_structure(content_id: int, db: Session) -> dict` method:
  1. Query `document_chunks` for tree chunks (`parent_chunk_id IS NOT NULL OR tree_depth = 0`) matching `content_id`
  2. Reconstruct tree as nested dict: `{node_id, title (heading_text), summary (chunk_text for is_summary=True), children: [...]}`
  3. Exclude leaf text content (only summaries needed for tree search)
  4. Return JSON-serializable tree structure

### Task 3.4: Implement tree search method
- **File**: `src/services/search.py`
- **Work**: Add `async _tree_search(query: str, content_ids: list[int], db: Session) -> list[SearchResult]`:
  1. For each content_id with tree index, load tree structure
  2. Format tree search prompt with query + tree JSON
  3. Call LLM via `llm_router` with `model_tree_search`
  4. Parse JSON response to get `node_list` and `thinking`
  5. Fetch leaf chunks under selected nodes (recursive children query)
  6. Convert to `SearchResult` objects with `reasoning` in metadata
  7. Handle LLM errors gracefully — log warning, fall back to empty results for that document

### Task 3.5: Implement query routing
- **File**: `src/services/search.py`
- **Work**: Modify `HybridSearchService.search()`:
  1. After applying filters, partition matching content_ids into tree-indexed and flat-indexed sets
  2. Tree-indexed: content_ids that have chunks with `tree_depth IS NOT NULL`
  3. Run tree search for tree-indexed set (if `tree_search_enabled`)
  4. Run standard BM25 + vector search for flat-indexed set (and as fallback for tree-indexed)
  5. Merge both result sets via existing RRF fusion

### Task 3.6: Add tree search tests
- **Files**: `tests/test_services/test_search.py`
- **Work**: Test cases for:
  - Tree search returns relevant nodes for qualifying content
  - Mixed corpus: tree-indexed + flat-indexed documents return merged results
  - Tree search fallback on LLM failure
  - `tree_search_enabled=False` bypasses tree search
  - Tree search prompt includes correct structure (summaries, no text)
  - Query routing correctly partitions content_ids

### Task 3.7: Add backfill command for existing content
- **File**: `src/cli/manage.py`
- **Work**: Add `aca manage backfill-tree-index` command:
  - Scans existing content records that qualify for tree indexing (token count + heading depth)
  - Builds tree index for qualifying content that doesn't already have one
  - Supports `--dry-run` to preview what would be indexed
  - Supports `--content-id` to target specific content
  - Reports progress and summary
