# Tasks — Tree Index Chunking

## Dependency Graph

```
Phase 1 (max parallel width: 3):
  1.1 ── 1.2 ── 1.3
  1.4 (independent)

Phase 2:
  2.1 ── 2.2 ──┐
               ├── 2.4 ── 2.5 ── 2.6 ── 2.6b ── 2.7
  2.3 ─────────┘                                   │
                                                    │
Phase 3:                                            │
  3.1 ─────────────┐                                │
  3.2 ─────────────┤                                │
  3.5 ─────────────┤                                │
               3.3 ┤── 3.4 ── 3.6 ── 3.7           │
                                                    └── 3.8
```

**Summary**: Independent: 7 tasks (1.1, 1.4, 2.1, 2.3, 3.1, 3.2, 3.5) | Sequential chains: 3 | Max parallel width: 4 (Phase 3: 3.1, 3.2, 3.3, 3.5 concurrent) | Note: 3.8 depends on 2.6b, not 3.6 (backfill is indexing, not search)

---

## Phase 1: Chunk Thinning

### Task 1.1: Add `min_node_tokens` setting
- **File**: `src/config/settings.py`
- **Depends on**: nothing (independent)
- **Work**: Add `min_node_tokens: int = 50` to `Settings` class alongside existing `chunk_size_tokens` and `chunk_overlap_tokens`
- **Validation**: Add `@field_validator` enforcing range 0–5000 (0 = disabled). Follow existing validator pattern in Settings class.

### Task 1.2: Implement chunk thinning post-processor
- **File**: `src/services/chunking.py`
- **Depends on**: 1.1 (reads `min_node_tokens` from settings)
- **Work**: Create `_thin_chunks(chunks: list[DocumentChunk], min_tokens: int) -> list[DocumentChunk]` function that merges undersized chunks into adjacent chunks. Merge into preceding chunk (append) by default; merge into following chunk (prepend) if no predecessor exists. Preserve `section_path` and `heading_text` of the absorbing chunk. Skip thinning when `min_tokens == 0`.
- **Exempt chunk types**: Do NOT merge TABLE or CODE chunks regardless of token count — preserve semantic classification
- **Integration**: Call `_thin_chunks()` as final step in `MarkdownChunkingStrategy.chunk()` and `StructuredChunkingStrategy.chunk()`, before `chunk_index` assignment

### Task 1.3: Add chunk thinning tests
- **File**: `tests/test_services/test_chunking.py`
- **Depends on**: 1.2 (tests the implementation)
- **Work**: Test cases for:
  - Small chunk merged into preceding chunk
  - Small first chunk merged into following chunk
  - `min_node_tokens=0` disables thinning
  - Single chunk below threshold (no merge target) preserved as-is
  - Chunk exactly at threshold not merged
  - Multiple consecutive small chunks merged correctly
  - TABLE chunk below threshold NOT merged (exempt)
  - CODE chunk below threshold NOT merged (exempt)

### Task 1.4: Add `min_node_tokens` to source config
- **File**: `src/config/sources.py`
- **Depends on**: nothing (independent)
- **Work**: Add `min_node_tokens` to `SourceDefaults` model so it can be overridden per-source in `sources.d/` YAML files. Follow existing pattern for `chunk_size_tokens` / `chunk_overlap_tokens`.

---

## Phase 2: Tree Index Strategy

### Task 2.1: Database migration — tree columns
- **File**: New file in `alembic/versions/`
- **Depends on**: nothing (independent, but must complete before 2.2)
- **Work**: Add three nullable columns to `document_chunks`:
  - `parent_chunk_id INTEGER REFERENCES document_chunks(id) ON DELETE CASCADE` (self-referential FK)
  - `tree_depth INTEGER` (NULL for flat chunks, 0 for tree root, >= 1 for children)
  - `is_summary BOOLEAN DEFAULT FALSE`
  - Index on `parent_chunk_id`
  - Composite index on `(content_id, tree_depth)` for tree structure queries
- **No ChunkType enum change**: Reuse existing `SECTION` value for summary nodes — avoids `ALTER TYPE ... ADD VALUE` PG migration gotcha
- **Idempotency**: Use `IF NOT EXISTS` / `information_schema` checks per project conventions

### Task 2.2: Update DocumentChunk model
- **File**: `src/models/chunk.py`
- **Depends on**: 2.1 (columns must exist in DB)
- **Work**: Add `parent_chunk_id`, `tree_depth`, `is_summary` columns to `DocumentChunk` ORM model. Add `parent` and `children` relationships for tree navigation.
- **No ChunkType change**: Do NOT add SUMMARY to ChunkType enum — reuse SECTION for summary nodes
- **Disambiguation rule**: Flat chunks have `tree_depth=NULL`; tree roots have `tree_depth=0`; `tree_depth` is the authoritative discriminator, NOT `parent_chunk_id` (which is NULL for both flat chunks and tree roots)

### Task 2.3: Add tree index settings and model steps
- **Files**: `src/config/settings.py`, `src/config/models.py`, `src/config/model_registry.yaml`
- **Depends on**: nothing (independent — touches different files from 2.1/2.2)
- **Work**:
  - In `settings.py`: Add `tree_index_min_tokens: int = 8000`, `tree_index_min_heading_depth: int = 3`, `tree_summarization_max_concurrent: int = 10`, `tree_max_depth: int = 10`
  - Add `@field_validator` bounds: `tree_index_min_tokens`: 1000–100000, `tree_index_min_heading_depth`: 2–10, `tree_summarization_max_concurrent`: 1–50, `tree_max_depth`: 2–20
  - In `models.py`: Add `TREE_SUMMARIZATION = "tree_summarization"` to `ModelStep` enum
  - In `model_registry.yaml`: Add `tree_summarization: claude-haiku-4-5` to `default_models:`
  - Do NOT add `model_tree_summarization` as a Settings field — use the existing `ModelStep` enum → env var → DB override → YAML default resolution pattern

### Task 2.4: Implement TreeIndexChunkingStrategy (tree-only)
- **File**: `src/services/chunking.py`
- **Depends on**: 2.2 (needs ORM model with tree columns), 2.3 (needs settings for thresholds)
- **Work**: Create `TreeIndexChunkingStrategy` class implementing `ChunkingStrategy` protocol:
  1. Parse heading hierarchy from markdown content (reuse existing heading regex)
  2. Build tree structure using stack-based algorithm: each heading section becomes a node, nested by heading level
  3. **Enforce `tree_max_depth` limit**: stop nesting beyond this depth and merge remaining sections into the deepest allowed parent
  4. Classify nodes as internal (has children) or leaf (no children)
  5. For leaf nodes: create `DocumentChunk` with actual content, `is_summary=False`
  6. For internal nodes: create `DocumentChunk` with `is_summary=True`, `chunk_type=SECTION`, and **placeholder empty `chunk_text`** (summaries populated later by async indexing step)
  7. Set `tree_depth` on all tree chunks (0 for root, incrementing for children). Set `parent_chunk_id` references (resolved after DB insertion via flush)
  8. **Return ONLY tree chunks** — do NOT include flat chunks. Flat chunk generation is handled by `ChunkingService.chunk_content()` via the standard strategy (Task 2.5 orchestrates both)
- **Sync-only**: The `chunk()` method remains synchronous — NO LLM calls here. Summaries are populated by `index_content()` async post-processing (Task 2.6)
- **Register**: Add `"tree_index": TreeIndexChunkingStrategy` to `STRATEGY_REGISTRY`

### Task 2.5: Add auto-selection and orchestration logic for tree index
- **File**: `src/services/chunking.py`
- **Depends on**: 2.4 (needs TreeIndexChunkingStrategy), 2.3 (needs threshold settings)
- **Work**: Modify `ChunkingService.chunk_content()` to orchestrate flat + tree chunking:
  1. Run the standard strategy (as today) to produce flat chunks
  2. Check if content qualifies for tree indexing: total tokens > `tree_index_min_tokens` AND heading depth >= `tree_index_min_heading_depth`
  3. If qualified, **additionally** run `TreeIndexChunkingStrategy` which returns tree-only chunks, then append them to the flat chunks list
  4. When `chunking_strategy` override is explicitly `tree_index` (per-source): run standard strategy for flat + TreeIndexChunkingStrategy for tree, regardless of qualification thresholds
  5. When `chunking_strategy` override is something else (e.g., `markdown`): do NOT auto-select tree index even if content qualifies
- **Key invariant**: Flat chunks are ALWAYS produced by the standard strategy, tree chunks are ALWAYS produced by `TreeIndexChunkingStrategy`. No duplication because each strategy produces its own chunk type.
- **Helper**: Add `_detect_heading_depth(content: str) -> int` utility function

### Task 2.6: Update indexing service for tree chunks
- **File**: `src/services/indexing.py`
- **Depends on**: 2.5 (needs tree chunks in the pipeline), 2.3 (needs ModelStep.TREE_SUMMARIZATION + concurrency settings)
- **Work**: Extend `index_content()` to handle tree chunks:
  - After chunk insertion and flush (so IDs are assigned), detect summary chunks (`is_summary=True` with empty `chunk_text`)
  - Run async LLM summarization as post-processing step, following existing `_run_async()` pattern for embeddings
  - Summarize bottom-up: deepest nodes first, then parents use children's summaries
  - **Bound concurrency with `asyncio.Semaphore(settings.tree_summarization_max_concurrent)`** — wrap each `_summarize_single_node()` call. Follows the established codebase pattern (youtube.py, reranking.py, image_extractor.py, html_markdown.py, audio_generator_v2.py all use Semaphore)
  - Use `ModelStep.TREE_SUMMARIZATION` for model resolution
  - After summaries populated, update chunk records in DB, then proceed to embedding
  - Summary chunks (`is_summary=True`) get embedded alongside leaf chunks (summaries are searchable via vector)
  - Create telemetry spans for summarization with `content_id`, `internal_node_count`, `total_summary_tokens`
  - **Failure handling**: If LLM summarization fails, delete all tree chunks for that `content_id` (keep flat chunks), log warning, and continue indexing without tree index

### Task 2.6b: Add tree-only indexing API
- **File**: `src/services/indexing.py`
- **Depends on**: 2.6 (builds on tree chunk handling in index_content)
- **Work**: Add `build_tree_index(content_id: int, db: Session, force: bool = False) -> int`:
  1. Load `Content` record by ID, verify `markdown_content` exists
  2. If `force=False` and tree chunks already exist (`tree_depth IS NOT NULL`) for this content_id, return 0 (skipped)
  3. If `force=True`, delete ONLY tree chunks (`tree_depth IS NOT NULL`) for this content_id — preserve flat chunks
  4. Run `TreeIndexChunkingStrategy.chunk()` on the content's markdown
  5. Insert tree chunks, flush for IDs
  6. Run `_summarize_tree_nodes()` with Semaphore-bounded concurrency
  7. Update chunk records, generate embeddings for new tree chunks
  8. Return count of tree chunks created
- **Key invariant**: This method NEVER touches flat chunks — it only creates/replaces tree chunks
- **Reused by**: Task 3.8 (backfill CLI command)

### Task 2.7: Add tree index tests
- **Files**: `tests/test_services/test_chunking.py`, `tests/test_services/test_indexing.py`
- **Depends on**: 2.6b (tests full tree index pipeline including tree-only API)
- **Work**: Test cases for:
  - Tree strategy builds correct hierarchy from nested headings
  - Internal nodes have `is_summary=True`, `chunk_type=SECTION`, placeholder empty text
  - Leaf nodes have `is_summary=False` with actual content
  - `tree_depth` set correctly: root=0, children incrementing
  - **`tree_max_depth` enforced**: document with H1→H2→...→H6 nesting beyond limit gets truncated
  - Flat chunks have `tree_depth=NULL` (not 0)
  - `parent_chunk_id` correctly links children to parents
  - **TreeIndexChunkingStrategy returns tree-only chunks** — no flat chunks in result
  - **ChunkingService.chunk_content() orchestrates both**: flat from standard strategy + tree from TreeIndexChunkingStrategy, no duplicates
  - Auto-selection triggers above token + depth thresholds
  - Auto-selection skipped for short/flat content
  - `chunking_strategy: tree_index` override forces tree indexing regardless of thresholds
  - Explicit non-tree strategy override prevents auto-selection
  - Async summary population in indexing: mock LLM returns deterministic summaries, verify parent summaries are generated after children (bottom-up), verify call order
  - **Semaphore bounds concurrency**: mock LLM with delay, verify max concurrent calls ≤ `tree_summarization_max_concurrent`
  - Sibling parallelization produces same results as sequential
  - Re-indexing: old tree + flat chunks deleted, new ones created
  - **Summarization failure**: mock LLM to raise, verify tree chunks deleted, flat chunks preserved, warning logged
  - **build_tree_index()**: creates tree chunks without touching flat chunks
  - **build_tree_index(force=True)**: deletes existing tree chunks, preserves flat chunks, rebuilds
  - **build_tree_index() skip**: returns 0 when tree chunks already exist and force=False
  - **Settings validation**: tree_index_min_tokens < 1000 rejected, tree_summarization_max_concurrent < 1 rejected

---

## Phase 3: Tree Search Retrieval

### Task 3.1: Register tree search prompt template
- **File**: `src/processors/prompts/` (or via prompt management system)
- **Depends on**: nothing (independent)
- **Work**: Register `search.tree_search` prompt template:
  ```
  You are given a question and a tree structure of a document.
  Each node contains a node_id, title, and summary.
  Find all nodes likely to contain the answer.

  Question: {query}
  Document tree structure:
  {tree_json}

  Reply as JSON: {"thinking": "...", "node_list": ["N001", "N002"]}
  ```
- **Node IDs**: Template references compact sequential IDs (N001, N002) not DB integers
- **Integration**: Managed via existing `aca prompts` system, overridable by users

### Task 3.2: Add tree search settings and model step
- **Files**: `src/config/settings.py`, `src/config/models.py`, `src/config/model_registry.yaml`
- **Depends on**: nothing (independent)
- **Work**:
  - In `settings.py`: Add `tree_search_enabled: bool = True`, `tree_search_max_documents: int = 3`, `tree_search_timeout_seconds: int = 5`, `tree_search_max_selected_nodes: int = 10`
  - Add `@field_validator` bounds: `tree_search_max_documents`: 1–20, `tree_search_timeout_seconds`: 1–30, `tree_search_max_selected_nodes`: 1–50
  - In `models.py`: Add `TREE_SEARCH = "tree_search"` to `ModelStep` enum
  - In `model_registry.yaml`: Add `tree_search: claude-haiku-4-5` to `default_models:`
  - Do NOT add `model_tree_search` as a Settings field

### Task 3.3: Implement tree structure loader with compact IDs
- **File**: `src/services/search.py`
- **Depends on**: 2.2 (needs ORM model with tree columns for queries)
- **Work**: Add `_load_tree_structure(content_id: int, db: Session) -> tuple[dict, dict[str, int]]` method:
  1. Query `document_chunks` for tree chunks (`tree_depth IS NOT NULL`) matching `content_id`
  2. Reconstruct tree as nested dict: `{node_id, title (heading_text), summary (chunk_text for is_summary=True), children: [...]}`
  3. Assign compact sequential IDs (N001, N002, ...) and build a mapping `{compact_id: db_chunk_id}`
  4. Exclude leaf text content (only summaries needed for tree search)
  5. **Serialize via `json.dumps()`** — never use f-string interpolation for tree JSON construction. This ensures proper escaping of any special characters in heading text (defense against prompt injection via document titles)
  6. Return JSON-serializable tree structure AND the compact-to-DB ID mapping

### Task 3.4: Implement tree search method
- **File**: `src/services/search.py`
- **Depends on**: 3.3 (needs tree loader), 3.1 (needs prompt template), 3.2 (needs settings + ModelStep)
- **Work**: Add `async _tree_search(query: str, content_ids: list[int], db: Session) -> list[tuple[int, int, float, str | None]]` returning `(chunk_id, content_id, score, reasoning)` tuples — **NOT** `SearchResult` objects. This matches the existing RRF fusion contract where `_calculate_rrf()` operates on chunk-level score dicts and `_aggregate_to_documents()` assembles `SearchResult` objects afterwards.
  1. Cap `content_ids` at `tree_search_max_documents` (overflow goes to flat search)
  2. For each content_id, load tree structure + compact ID mapping
  3. Format tree search prompt with query + tree JSON (compact IDs, serialized via json.dumps)
  4. Execute LLM calls concurrently via `asyncio.gather()` with `tree_search_timeout_seconds` timeout (concurrency is already bounded by `tree_search_max_documents` ≤ 20)
  5. **Parse and validate JSON response** in a try/except block:
     - `json.loads()` the response — on `JSONDecodeError`, log warning, fall back to empty for that document
     - Validate `node_list` key exists and is `list[str]` — on type error, log warning, fall back
     - Validate each ID matches regex `N\d{3,}` — skip non-matching IDs with warning
     - **Cap `node_list` at `tree_search_max_selected_nodes`** (default: 10) — truncate excess, log info
  6. Validate returned compact IDs exist in the mapping — silently skip unknown IDs (LLM hallucination guard), log warning if any skipped
  7. Resolve valid compact IDs back to DB chunk IDs via mapping
  8. Fetch leaf chunks under selected nodes (recursive children query) — use only tree chunks (`tree_depth IS NOT NULL`), never flat chunks for the same content_id
  9. Convert to `(chunk_id, content_id, score, reasoning)` tuples: score = `1.0 / (rank_in_node_list + 1)`, reasoning from `thinking` field
  10. Handle LLM errors/timeouts gracefully — log warning, fall back to empty results for that document
  11. Create telemetry spans with `tree_depth`, `node_count`, `query`, `selected_node_ids`, `duration_ms`
- **Model resolution**: Use `ModelStep.TREE_SEARCH` (not a Settings field)

### Task 3.5: Update SearchResult model
- **File**: `src/models/search.py`
- **Depends on**: nothing (independent)
- **Work**: Add `tree_reasoning: str | None = None` to `SearchResult` model. This field is `None` for flat hybrid search results and contains the LLM reasoning trace for tree search results. Populated by `_aggregate_to_documents()` when tree search results are present.

### Task 3.6: Implement query routing and RRF integration
- **File**: `src/services/search.py`
- **Depends on**: 3.4 (needs tree search method), 3.5 (needs updated SearchResult)
- **Work**: Modify `HybridSearchService.search()`:
  1. Run BM25 + vector candidate generation as today — this produces chunk-level score dicts and a set of matching `content_id`s with pre-scores
  2. Partition matching content_ids into tree-indexed and flat-indexed sets. Tree-indexed: content_ids that have chunks with `tree_depth IS NOT NULL` (authoritative check)
  3. **Pre-rank tree-indexed content_ids** using the BM25/vector pre-scores already computed in step 1. Select top-N by pre-score where N = `tree_search_max_documents`. Overflow content_ids fall back to flat search path.
  4. Run `_tree_search()` for the top-N tree-indexed set (if `tree_search_enabled`). This returns `(chunk_id, content_id, score, reasoning)` tuples.
  5. **Feed tree search chunk scores into the existing RRF pipeline**: add tree scores as a third score source alongside BM25 and vector scores in `_calculate_rrf()`. Tree search results from tree chunks only — flat chunks for the same content_id are NOT included from the tree path (they exist for BM25/vector fallback, not tree search).
  6. Run standard BM25 + vector search for flat-indexed content_ids (and as fallback for tree-indexed overflow and timeouts)
  7. RRF fuses all three score sources (BM25, vector, tree) into a single ranked list
  8. `_aggregate_to_documents()` assembles `SearchResult` objects — populate `tree_reasoning` from the tree search reasoning metadata when present

### Task 3.7: Add tree search tests
- **Files**: `tests/test_services/test_search.py`
- **Depends on**: 3.6 (tests full tree search pipeline)
- **Work**: Test cases for:
  - Tree search returns relevant nodes for qualifying content
  - Mixed corpus: tree-indexed + flat-indexed documents return merged results
  - Tree search fallback on LLM failure
  - Tree search fallback on timeout (`tree_search_timeout_seconds`)
  - `tree_search_enabled=False` bypasses tree search
  - `tree_search_max_documents` caps LLM calls (overflow goes to flat)
  - **Pre-ranking**: top-N tree-indexed documents selected by BM25/vector pre-score, not arbitrary
  - Tree search prompt uses compact IDs (N001, N002), not DB integers
  - Compact IDs correctly resolved back to DB chunk IDs
  - `tree_reasoning` populated on tree results, `None` on flat results
  - Query routing correctly partitions content_ids using `tree_depth IS NOT NULL`
  - **Tree search returns chunk-level tuples, not SearchResult** — verify RRF integration works
  - **node_list capped at tree_search_max_selected_nodes** — verify truncation
  - **Malformed LLM responses**: invalid JSON, missing node_list, node_list not a list, non-matching IDs — all fall back gracefully
  - **Prompt injection in headings**: document with heading containing `{query}` or `ignore above` — verify json.dumps escaping prevents template breakout
  - **Settings validation**: tree_search_max_documents < 1 rejected, tree_search_timeout_seconds < 1 rejected

### Task 3.8: Add backfill command for existing content
- **File**: `src/cli/manage.py`
- **Depends on**: 2.6b (needs `build_tree_index()` API from indexing service)
- **Work**: Add `aca manage backfill-tree-index` command:
  - Scans existing content records that qualify for tree indexing (token count + heading depth)
  - **Calls `build_tree_index(content_id, db, force=force)` for each qualifying record** — this API handles all tree chunk creation, summarization, and embedding while preserving flat chunks
  - Supports `--dry-run` to preview what would be indexed
  - Supports `--content-id` to target specific content
  - Supports `--force` to rebuild tree indexes for content that already has them (build_tree_index handles delete + rebuild)
  - Without `--force`, skips content that already has tree chunks (build_tree_index returns 0)
  - Reports progress and summary
