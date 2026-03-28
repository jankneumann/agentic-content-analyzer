## Dependencies

```
Section 1 (DB migration)       ─── no deps, run first
Section 2 (extraction service)  ─── no deps, parallel with 1
Section 3 (resolution service)  ─── depends on 1, 2
Section 4 (Neo4j sync)          ─── depends on 1, 3
Section 5 (ingestion hooks)     ─── depends on 2, 3
Section 6 (auto-ingest)         ─── depends on 3 (+ arxiv/scholar orchestrators exist)
Section 7 (API routes)          ─── depends on 1
Section 8 (CLI commands)        ─── depends on 2, 3
Section 9 (settings)            ─── no deps, parallel with 1, 2
Section 10 (docs)               ─── depends on all
```

**Max parallel width: 3** (sections 1, 2, 9 in first wave)

## 1. Database Migration & Models

- [ ] 1.1 Create `ReferenceType`, `ExternalIdType`, `ResolutionStatus` Python enums in `src/models/content_reference.py`
- [ ] 1.2 Create `ContentReference` SQLAlchemy model in `src/models/content_reference.py`
- [ ] 1.3 Add `references` and `cited_by` relationships on `Content` model (lazy-loaded)
- [ ] 1.4 Create Alembic migration:
  - Add `referencetype`, `externalidtype`, `resolutionstatus` PostgreSQL enum types
  - Create `content_references` table with all columns and constraints
  - Create indexes: `ix_content_refs_source`, `ix_content_refs_target`, `ix_content_refs_external_id`, `ix_content_refs_unresolved`
  - Create GIN index on `contents.metadata_json` if not present (idempotent with Scholar/arXiv migrations)
- [ ] 1.5 Run migration and verify table, enums, and indexes
- [ ] 1.6 Write model unit tests (creation, constraints, relationships)

## 2. Reference Extraction Service (parallel with 1, 9)

- [ ] 2.1 Create `src/services/reference_extractor.py` with `ReferenceExtractor` class
- [ ] 2.2 Implement `REFERENCE_PATTERNS` dict mapping `ExternalIdType` → list of compiled regex patterns for arXiv IDs, DOIs, S2 URLs
- [ ] 2.3 Implement `normalize_id(id_type, raw_id) -> str` — strip arXiv version suffix, lowercase DOIs, clean trailing punctuation
- [ ] 2.4 Implement `classify_url(url) -> ExtractedReference | None` — classify known URL patterns into structured IDs (arxiv.org → arxiv, doi.org → doi, semanticscholar.org → s2)
- [ ] 2.5 Implement `extract_context(text, match, window=150) -> str` — extract surrounding text for context_snippet
- [ ] 2.6 Implement `extract_from_content(content: Content) -> list[ExtractedReference]` — scan markdown_content + links_json, deduplicate
- [ ] 2.7 Implement `store_references(content_id, refs, db) -> int` — persist ExtractedReference list to content_references table, skip existing (unique constraint)
- [ ] 2.8 Create `ExtractedReference` dataclass (external_id, external_id_type, external_url, context_snippet, confidence, reference_type)
- [ ] 2.9 Write unit tests: regex patterns (arXiv variants, DOI variants, S2 URLs), normalization, URL classification, deduplication, context extraction

## 3. Resolution Service (depends on 1, 2)

- [ ] 3.1 Create `src/services/reference_resolver.py` with `ReferenceResolver` class
- [ ] 3.2 Implement `_find_by_external_id(external_id, id_type, db) -> Content | None` — GIN-indexed `metadata_json @>` containment query
- [ ] 3.3 Implement `_find_by_source_url(url, db) -> Content | None` — match against `contents.source_url`
- [ ] 3.4 Implement `resolve_reference(ref: ContentReference, db) -> ResolutionStatus` — try external_id lookup, then URL lookup, update status
- [ ] 3.5 Implement `resolve_for_content(content_id, db) -> int` — resolve all unresolved refs for a specific content item
- [ ] 3.6 Implement `resolve_batch(batch_size, db) -> int` — resolve oldest unresolved refs in batch
- [ ] 3.7 Implement `resolve_incoming(new_content: Content, db) -> int` — reverse resolution: find unresolved refs matching new content's metadata (arxiv_id, doi, source_url)
- [ ] 3.8 Register `resolve_references` queue handler in `src/queue/worker.py`
- [ ] 3.9 Write unit tests: resolution by external_id, by URL, reverse resolution, batch processing

## 4. Neo4j Citation Edge Sync (depends on 1, 3)

- [ ] 4.1 Create `src/services/reference_graph_sync.py` with `ReferenceGraphSync` class
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
- [ ] 5.3 Wire hook into ingestion orchestrator (called after content persist in each service)
- [ ] 5.4 Add `supplements` link detection: when arXiv content is ingested and Scholar record exists (or vice versa), create bidirectional supplements reference
- [ ] 5.5 Write integration tests: hook called on RSS ingestion, hook called on arXiv ingestion, hook failure doesn't block ingestion

## 6. Auto-Ingest Trigger (depends on 3)

- [ ] 6.1 Create `src/services/reference_auto_ingest.py` with `AutoIngestTrigger` class
- [ ] 6.2 Implement depth check: skip if source content has `ingestion_mode == "auto_ingest"` in metadata_json
- [ ] 6.3 Implement arXiv auto-ingest: call `ingest_arxiv_paper()` for unresolved arXiv IDs
- [ ] 6.4 Implement DOI auto-ingest: call `ingest_scholar_paper()` for unresolved DOIs
- [ ] 6.5 Wire into resolution service (opt-in, gated on `reference_auto_ingest_enabled` setting)
- [ ] 6.6 Write unit tests: auto-ingest triggered, depth limit respected, disabled by default

## 7. API Routes (depends on 1)

- [ ] 7.1 Create `src/api/reference_routes.py` with FastAPI router
- [ ] 7.2 Implement `GET /api/v1/contents/{id}/references` — outgoing references with pagination
- [ ] 7.3 Implement `GET /api/v1/contents/{id}/cited-by` — incoming references with pagination
- [ ] 7.4 Create Pydantic response schemas: `ReferenceResponse`, `ReferenceListResponse`
- [ ] 7.5 Register router in `src/api/app.py`
- [ ] 7.6 Write API tests

## 8. CLI Commands (depends on 2, 3)

- [ ] 8.1 Add `aca manage extract-refs` command to `src/cli/manage_commands.py`
  - Options: `--after`, `--before`, `--source`, `--dry-run`, `--batch-size`
  - Iterates content, extracts references, enqueues resolution
- [ ] 8.2 Add `aca manage resolve-refs` command
  - Options: `--batch-size`, `--auto-ingest`
  - Runs resolution pass synchronously
- [ ] 8.3 Write CLI integration tests

## 9. Settings (parallel with 1, 2)

- [ ] 9.1 Add reference settings to `src/config/settings.py`:
  - `reference_extraction_enabled: bool = True`
  - `reference_auto_ingest_enabled: bool = False`
  - `reference_auto_ingest_max_depth: int = 1`
  - `reference_neo4j_sync_enabled: bool = True`
  - `reference_min_confidence: float = 0.5`
- [ ] 9.2 Wire settings into `profiles/base.yaml`
- [ ] 9.3 Write settings unit tests

## 10. Documentation (depends on all)

- [ ] 10.1 Update CLAUDE.md with reference management commands
- [ ] 10.2 Document reference extraction patterns and resolution workflow
- [ ] 10.3 Document auto-ingest configuration and depth limiting
- [ ] 10.4 Document Neo4j citation graph queries
