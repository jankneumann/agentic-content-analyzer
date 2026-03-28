## Cross-Proposal Dependencies

- **`add-arxiv-ingest`**: Section 6 (auto-ingest) Task 6.3 calls `ingest_arxiv_paper()` which does not yet exist. DOI auto-ingest (Task 6.4) works today via `ingest_scholar_paper()`. Section 6 is deferrable — implement DOI-only auto-ingest first, add arXiv auto-ingest after `add-arxiv-ingest` lands.
- **`metadata_json → jsonb` migration**: Both this proposal and `add-arxiv-ingest` require the same ALTER. Both migrations must check column type before altering (idempotent). Whichever migration runs first performs the ALTER; the second is a no-op.

## Dependencies

```
Section 1 (DB migration)       ─── no deps, run first
Section 2 (extraction refactor) ── no deps, parallel with 1
Section 3 (resolution service)  ─── depends on 1, 2
Section 4 (Neo4j sync)          ─── depends on 1, 3
Section 5 (ingestion hooks)     ─── depends on 2, 3; modifies orchestrator.py (sequential with 8)
Section 6 (auto-ingest)         ─── depends on 3; DOI works now, arXiv needs add-arxiv-ingest
Section 7 (API routes)          ─── depends on 1; modifies app.py (sequential with 9)
Section 8 (CLI commands)        ─── depends on 2, 3; modifies orchestrator.py (sequential with 5)
Section 9 (MCP tools)           ─── depends on 7, 8; modifies mcp_server.py (sequential with 7)
Section 10 (settings)           ─── no deps, parallel with 1, 2
Section 11 (docs)               ─── depends on all
```

**Max parallel width: 3** (sections 1, 2, 10 in first wave)

### File Overlap Warnings (for parallel execution)

| Shared File | Sections | Sequencing |
|---|---|---|
| `src/ingestion/orchestrator.py` | 5, 8 | 5 before 8 |
| `src/api/app.py` | 7, 9 | 7 before 9 |
| `src/mcp_server.py` | 7, 9 | 7 before 9 |

## 1. Database Migration & Models

- [ ] 1.1 Create `ReferenceType`, `ExternalIdType`, `ResolutionStatus` Python `StrEnum` classes in `src/models/content_reference.py` — these are app-level validation only, **no PostgreSQL enum types**
- [ ] 1.2 Create `ContentReference` SQLAlchemy model in `src/models/content_reference.py` — use `sa.String(20)` for enum-like columns with `@validates` decorator; include `source_chunk_id` FK to `document_chunks.id` (nullable, SET NULL on delete); include CHECK constraint `chk_has_identifier`
- [ ] 1.3 Add `references` and `cited_by` relationships on `Content` model (lazy-loaded)
- [ ] 1.4 Create Alembic migration:
  - ALTER `contents.metadata_json` from `json` to `jsonb` if not already `jsonb`: `ALTER TABLE contents ALTER COLUMN metadata_json TYPE jsonb USING metadata_json::jsonb`. **Idempotent coordination**: check `SELECT data_type FROM information_schema.columns WHERE table_name='contents' AND column_name='metadata_json'` — if already `jsonb`, skip ALTER. Both this and `add-arxiv-ingest` migrations independently perform this check; whichever runs first does the ALTER.
  - Create `content_references` table with all columns, CHECK constraint, and unique constraint
  - Create partial unique index: `CREATE UNIQUE INDEX uq_content_reference_url ON content_references (source_content_id, external_url) WHERE external_id IS NULL` (use `op.create_index(unique=True, postgresql_where=...)` in Alembic)
  - Create indexes: `ix_content_refs_source`, `ix_content_refs_target`, `ix_content_refs_external_id`, `ix_content_refs_unresolved`
  - Create GIN index on `contents.metadata_json` if not present (idempotent with `CREATE INDEX IF NOT EXISTS`)
  - Check for Alembic multiple heads and merge if needed
- [ ] 1.5 Update SQLAlchemy Content model to use `JSONB` instead of `JSON` for `metadata_json`
- [ ] 1.6 Run migration and verify table, indexes, and constraints
- [ ] 1.7 Write model unit tests (creation, constraints, CHECK constraint, relationships)

## 2. Reference Extraction Service — Refactor & Extend (parallel with 1, 10)

**Existing code**: `src/ingestion/reference_extractor.py` (227 LOC) already has `ReferenceExtractor` with `ARXIV_PATTERNS`, `DOI_PATTERNS`, `S2_URL_PATTERN`, `extract_all()`, `extract_from_contents()`, and `ingest_extracted_references()`. Tests exist at `tests/test_ingestion/test_reference_extractor.py`.

- [ ] 2.0 **Migrate module**: Move `src/ingestion/reference_extractor.py` → `src/services/reference_extractor.py`. Add re-export shim at old location for backward compatibility: `from src.services.reference_extractor import ReferenceExtractor, ReferenceExtractionResult`. Update imports in `src/ingestion/orchestrator.py`, `src/cli/ingest_commands.py`, and test files.
- [ ] 2.1 **Restructure patterns**: Refactor existing separate `ARXIV_PATTERNS`, `DOI_PATTERNS`, `S2_URL_PATTERN` into unified `REFERENCE_PATTERNS: dict[ExternalIdType, list[re.Pattern]]` mapping. Preserve all existing regex patterns.
- [ ] 2.2 Implement `normalize_id(id_type, raw_id) -> str` — strip arXiv version suffix (existing `extract_dois` already strips trailing punctuation; consolidate this logic)
- [ ] 2.3 Implement `classify_url(url) -> ExtractedReference | None` — NEW: classify known URL patterns into structured IDs (arxiv.org → arxiv, doi.org → doi, semanticscholar.org → s2)
- [ ] 2.4 Implement `_find_chunk_for_offset(chunks, char_offset) -> DocumentChunk | None` — NEW: chunk_index-based sequential matching (cumulative `len(chunk.text)`)
- [ ] 2.5 Implement `extract_context(text, match, window=150) -> str` — NEW: extract surrounding text for context_snippet
- [ ] 2.6 Implement `extract_from_content(content: Content, db: Session) -> list[ExtractedReference]` — NEW: extends existing `extract_all()` with chunk anchoring, URL classification from `links_json`, deduplication. Handles `None`/empty `markdown_content` gracefully (returns empty list).
- [ ] 2.7 Implement `store_references(content_id, refs, db) -> int` — NEW: persist via `INSERT ... ON CONFLICT DO NOTHING`
- [ ] 2.8 Create `ExtractedReference` dataclass — NEW: (external_id, external_id_type, external_url, source_chunk_id, context_snippet, confidence, reference_type)
- [ ] 2.9 Preserve existing APIs: `extract_all()`, `extract_from_contents()`, `ingest_extracted_references()` must continue to work for `aca ingest scholar-refs` backward compatibility
- [ ] 2.10 **Extend tests**: Audit existing `tests/test_ingestion/test_reference_extractor.py`. Add new tests for: URL classification, chunk anchoring, `store_references`, `extract_from_content` with DB, deduplication, empty/null markdown_content. Move test file to `tests/test_services/test_reference_extractor.py` (with symlink or re-export at old location).

## 3. Resolution Service (depends on 1, 2)

- [ ] 3.1 Create `src/services/reference_resolver.py` with `ReferenceResolver` class
- [ ] 3.2 Implement `_find_by_external_id(external_id, id_type, db) -> Content | None` — GIN-indexed `metadata_json @>` containment query
- [ ] 3.3 Implement `_find_by_source_url(url, db) -> Content | None` — match against `contents.source_url`
- [ ] 3.4 Implement `resolve_reference(ref: ContentReference, db) -> ResolutionStatus` — try external_id lookup, then URL lookup, update status
- [ ] 3.5 Implement `resolve_for_content(content_id, db) -> int` — resolve all unresolved refs for a specific content item
- [ ] 3.6 Implement `resolve_batch(batch_size, db) -> int` — resolve oldest unresolved refs in batch
- [ ] 3.7 Implement `resolve_incoming(new_content: Content, db) -> int` — reverse resolution: find unresolved refs matching new content's metadata (arxiv_id, doi, source_url)
- [ ] 3.8 Register `resolve_references` queue handler in `src/queue/worker.py` — add `_register_reference_handlers()` function call in `register_all_handlers()`, following the existing `_register_content_handlers()` pattern
- [ ] 3.9 Write unit tests: resolution by external_id, by URL, reverse resolution, batch processing. **CRITICAL**: GIN-indexed queries must use `CAST(:param AS jsonb)` not `:param::jsonb` — psycopg2 misparsing of double-colon has silently broken queries in this codebase before (CLAUDE.md gotcha). Verify actual metadata_json key names match Scholar implementation: `arxiv_id`, `doi`, `s2_paper_id`.

## 4. Neo4j Citation Edge Sync (depends on 1, 3)

- [ ] 4.1 Create `src/services/reference_graph_sync.py` with `ReferenceGraphSync` class — reuse `GraphitiClient.driver` for raw Cypher queries (do NOT create a separate Neo4j driver instance)
- [ ] 4.2 Implement `_find_episode_uuid(content_id) -> str | None` — query Neo4j for Episode node matching content
- [ ] 4.3 Implement `sync_reference(ref: ContentReference)` — create/update CITES edge between Episode nodes (MERGE with properties)
- [ ] 4.4 Implement `sync_resolved_for_content(content_id)` — sync all resolved refs for a content item
- [ ] 4.5 Make sync fire-and-forget: log errors but never raise (fail-safe)
- [ ] 4.6 Wire sync into resolution service: call after successful resolution
- [ ] 4.7 Write unit tests with mocked Neo4j driver

## 5. Ingestion Hooks (depends on 2, 3)

- [ ] 5.1 Create `src/services/reference_hook.py` with `on_content_ingested(content: Content, db)` function
- [ ] 5.2 Implement the hook:
  - Extract references via `ReferenceExtractor`
  - Store via `store_references()`
  - Enqueue `resolve_references` job
  - Call `resolve_incoming()` for reverse resolution
  - Wrap in try/except: log errors, never block ingestion
- [ ] 5.3 Wire hook into ingestion orchestrator — add `on_content_ingested()` call at the end of each orchestrator function after the service's persist step: `ingest_gmail()`, `ingest_rss()`, `ingest_youtube()`, `ingest_podcast()`, `ingest_substack()`, `ingest_scholar()`, and (when available) `ingest_arxiv()`. Each call is wrapped in the hook's own try/except so ingestion is never blocked.
- [ ] 5.4 Add `supplements` link detection: when arXiv content is ingested and Scholar record exists (or vice versa), create **two** supplements reference rows (one in each direction) for true bidirectionality
- [ ] 5.5 Add chunk re-anchoring hook: after chunks are created or re-indexed for a content item, run `_find_chunk_for_offset` on all references with `source_chunk_id IS NULL` for that content_id to retroactively anchor them
- [ ] 5.6 Write integration tests: hook called on RSS ingestion, hook called on arXiv ingestion, hook failure doesn't block ingestion, chunk re-anchoring after indexing

## 6. Auto-Ingest Trigger (depends on 3; arXiv auto-ingest deferred until `add-arxiv-ingest` lands)

- [ ] 6.1 Create `src/services/reference_auto_ingest.py` with `AutoIngestTrigger` class
- [ ] 6.2 Implement depth check via `metadata_json.auto_ingest_depth` integer (0=user-ingested, 1+=auto-ingested): skip if `auto_ingest_depth >= max_depth`. Tag newly auto-ingested content with both `ingestion_mode: "auto_ingest"` and `auto_ingest_depth: source_depth + 1`
- [ ] 6.3 Implement DOI auto-ingest: call `ingest_scholar_paper()` for unresolved DOIs — **works today**, no cross-proposal dependency
- [ ] 6.4 Implement arXiv auto-ingest: call `ingest_arxiv_paper()` for unresolved arXiv IDs — **DEFERRED**: requires `add-arxiv-ingest` to be implemented first. Add stub that logs "arXiv auto-ingest not available" and returns None. Wire in after arXiv orchestrator lands.
- [ ] 6.5 Wire into resolution service (opt-in, gated on `reference_auto_ingest_enabled` setting)
- [ ] 6.6 Write unit tests: DOI auto-ingest triggered, depth limit respected, disabled by default, arXiv stub logs warning

## 7. API Routes (depends on 1)

- [ ] 7.1 Create `src/api/reference_routes.py` with FastAPI router
- [ ] 7.2 Implement `GET /api/v1/contents/{id}/references` — outgoing references with pagination
- [ ] 7.3 Implement `GET /api/v1/contents/{id}/cited-by` — incoming references with pagination
- [ ] 7.4 Create Pydantic response schemas: `ReferenceResponse`, `ReferenceListResponse`
- [ ] 7.5 Register router in `src/api/app.py`
- [ ] 7.6 Write API tests

## 8. CLI Commands (depends on 2, 3; modifies orchestrator.py — sequential with Section 5)

**Existing**: `aca ingest scholar-refs` extracts identifiers and ingests via Scholar service (fire-and-forget, no `content_references` table). This command remains unchanged for backward compatibility.

- [ ] 8.1 Add `aca manage extract-refs` command to `src/cli/manage_commands.py`
  - Options: `--after`, `--before`, `--source`, `--dry-run`, `--batch-size`
  - Iterates content, extracts references via refactored `ReferenceExtractor.extract_from_content()`, stores to `content_references` table, enqueues resolution
  - **Different from `scholar-refs`**: source-agnostic, persists to DB, doesn't directly ingest papers
- [ ] 8.2 Add `aca manage resolve-refs` command
  - Options: `--batch-size`, `--auto-ingest`
  - Runs resolution pass synchronously
- [ ] 8.3 Write CLI integration tests

## 9. MCP Tools (depends on 7, 8)

- [ ] 9.1 Add `get_content_references(content_id, direction)` tool to `src/mcp_server.py` — delegates to reference service for outgoing/incoming queries
- [ ] 9.2 Add `extract_references(after, before, source, dry_run, batch_size)` tool — mirrors `aca manage extract-refs` CLI
- [ ] 9.3 Add `resolve_references(batch_size, auto_ingest)` tool — mirrors `aca manage resolve-refs` CLI
- [ ] 9.4 Add `ingest_reference(reference_id)` tool — ad-hoc ingest for a specific unresolved reference
- [ ] 9.5 Write MCP tool tests

## 10. Settings (parallel with 1, 2)

- [ ] 10.1 Add reference settings to `src/config/settings.py`:
  - `reference_extraction_enabled: bool = True`
  - `reference_auto_ingest_enabled: bool = False`
  - `reference_auto_ingest_max_depth: int = 1`
  - `reference_neo4j_sync_enabled: bool = True`
  - `reference_min_confidence: float = 0.5`
- [ ] 10.2 Wire settings into `profiles/base.yaml`
- [ ] 10.3 Write settings unit tests

## 11. Documentation (depends on all)

- [ ] 11.1 Update CLAUDE.md with reference management commands and MCP tools
- [ ] 11.2 Document reference extraction patterns and resolution workflow
- [ ] 11.3 Document auto-ingest configuration and depth limiting
- [ ] 11.4 Document Neo4j citation graph queries
