# Tasks: Add Content Query Builder

## Task Dependencies

```
Phase 1: [1.1–1.3] Model + Service + Tests (foundation, all others depend on this)
Phase 2 (parallel):
  ├─ [1.4] Refactor content_routes.py to use ContentQueryService
  ├─ [2.1–2.2] CLI shared options + tests
  └─ [4.1] Frontend types + API client + hooks
Phase 3 (parallel, after Phase 2):
  ├─ [3.1–3.4] Extend Summarize CLI + Service (depends on 1.x, 2.1)
  ├─ [3.5–3.8] Extend Digest CLI + Service (depends on 1.x, 2.1)
  ├─ [4.2–4.5] Frontend sub-components (depends on 4.1)
  └─ [5.1–5.2] API query endpoint + summarize extension (depends on 1.4)
Phase 4 (after Phase 3):
  ├─ [5.3–5.5] API digest extension + all API tests (depends on 3.5, 5.1)
  └─ [4.6] ContentQueryBuilder main component (depends on 4.2–4.5)
Phase 5: [4.7] Frontend dialog integration (depends on 4.6, 5.x)
Phase 6: [6.1–6.3] E2E tests (depends on 4.7)
Phase 7: [7.1–7.4] Documentation (depends on all above)
```

**Max parallel width**: 4 (in Phase 3)
**File overlap**: `src/api/content_routes.py` modified by 1.4 then 5.1–5.2 (must be sequential).
**File overlap**: `src/processors/summarizer.py` modified by 3.2 and 3.3 (same phase, done atomically).

**Note**: Task groups below are numbered by area (1=model, 2=CLI options, 3=CLI commands, 4=frontend, 5=API, 6=E2E, 7=docs). Execution order follows the dependency graph above, not the numbering.

---

## 1. ContentQuery Model & Query Service

- [ ] 1.1 Create `src/models/query.py` with models
  - `ContentQuery`: source_types, statuses, publications, publication_search, start_date, end_date, search, limit (gt=0), sort_by (validated via field_validator), sort_order (asc|desc pattern)
  - `ContentQueryPreview`: total_count, by_source (dict, alphabetical), by_status (dict, alphabetical), date_range ({earliest, latest}), sample_titles (max `PREVIEW_SAMPLE_LIMIT=10`)
  - `CONTENT_SORT_FIELDS` constant matching existing content_routes.py set
  - `PREVIEW_SAMPLE_LIMIT = 10` constant
  - `sort_by` field_validator: reject invalid fields with ValueError listing valid options
  - Null semantics: `None` means no filter; empty list `[]` treated as `None`
- [ ] 1.2 Create `src/services/content_query.py` with `ContentQueryService`
  - `build_query(db, query) -> SQLAlchemy Query` — translate ContentQuery to filters
  - `preview(query) -> ContentQueryPreview` — COUNT + GROUP BY for breakdowns, separate query for up to 10 sample titles ordered by published_date desc. Returns total_count=0 with empty dicts/lists when no match.
  - `resolve(query) -> list[int]` — return all matching content IDs (bounded by query.limit)
  - Empty lists treated as None (no filter applied)
- [ ] 1.3 Add unit tests in `tests/services/test_content_query.py`
  - Test each filter dimension independently (source_types, statuses, publications, publication_search, start_date, end_date, search)
  - Test filter combinations (source + date, status + search)
  - Test empty query (no filters) matches all content
  - Test empty list fields (`source_types=[]`) treated as None
  - Test preview returns correct by_source and by_status breakdowns
  - Test preview with zero matches returns total_count=0, empty dicts, empty list
  - Test resolve returns correct IDs in sort order
  - Test invalid sort_by raises ValueError with valid fields listed
  - Test limit must be > 0 (Pydantic validation)
  - Test start_date > end_date returns empty result (not an error)
  - Test sample_titles limited to PREVIEW_SAMPLE_LIMIT
  - Test sample_titles ordered by published_date desc
  - Test sort_order asc/desc both work correctly
- [ ] 1.4 Refactor `content_routes.py` `list_contents` endpoint to use `ContentQueryService.build_query()`
  - Wrap singular `source_type` param into `source_types=[source_type]` for ContentQuery compatibility
  - Preserve exact same API response (no breaking changes)
  - Add regression tests verifying: source_type, status, publication, date range, search, sort, pagination all produce identical results before and after
  - **Modifies**: `src/api/content_routes.py`

## 2. CLI Shared Options

- [ ] 2.1 Create `src/cli/query_options.py` with shared definitions and `build_query_from_options()` helper
  - `--source` / `-s`: Comma-separated ContentSource. Invalid values → `typer.BadParameter` listing valid options.
  - `--status`: Comma-separated ContentStatus. Invalid values → `typer.BadParameter` listing valid options.
  - `--after`: Start date (YYYY-MM-DD strict). Invalid → `typer.BadParameter` with format hint.
  - `--before`: End date (YYYY-MM-DD strict). Invalid → `typer.BadParameter` with format hint.
  - `--publication` / `-p`: Publication name search (ILIKE)
  - `--search` / `-q`: Title search (ILIKE)
  - `--dry-run`: Calls `ContentQueryService.preview()`, displays Rich table or JSON, exits without executing
  - `default_statuses` parameter for operation-specific defaults
- [ ] 2.2 Add unit tests in `tests/cli/test_query_options.py`
  - Test valid comma-separated source parsing
  - Test invalid source value raises BadParameter with valid options listed
  - Test empty string `--source ""` rejected
  - Test leading/trailing comma handling
  - Test valid date parsing (YYYY-MM-DD)
  - Test invalid date format shows helpful error
  - Test default_statuses applied when --status not provided
  - Test default_statuses overridden when --status provided
  - Test limit validation (> 0)

## 3. Extend Summarize CLI with Filters

**Depends on**: 1.1, 1.2, 2.1

- [ ] 3.1 Add filter options to `aca summarize pending` command
  - Import shared options from `query_options.py`
  - When any filter provided: construct ContentQuery via `build_query_from_options(default_statuses=[PENDING, PARSED])`
  - When `--dry-run`: call `ContentQueryService.preview()`, display Rich table or JSON, exit without summarizing
  - Default behavior unchanged when no filters provided
  - **Modifies**: `src/cli/summarize_commands.py`
- [ ] 3.2 Update `ContentSummarizer.summarize_pending_contents()` to accept optional `query: ContentQuery`
  - When query provided: merge default statuses if query.statuses is None (use `model_copy(update=...)`)
  - When query not provided: preserve existing behavior exactly (regression)
  - **Modifies**: `src/processors/summarizer.py`
- [ ] 3.3 Update `ContentSummarizer.enqueue_pending_contents()` similarly
  - Accept optional `query: ContentQuery`
  - Use ContentQueryService for ID resolution when query provided
  - **Modifies**: `src/processors/summarizer.py` (same file as 3.2 — do atomically)
- [ ] 3.4 Add unit tests in `tests/cli/test_summarize_commands.py` and `tests/processors/test_summarizer.py`
  - Test summarize_pending CLI with source filter (mock ContentQueryService)
  - Test summarize_pending CLI with date filter
  - Test summarize_pending CLI with combined filters
  - Test --dry-run displays preview without summarizing (no enqueue calls)
  - Test --dry-run --output json outputs correct JSON structure
  - Test default behavior unchanged (no filters = same as before, regression)
  - Test invalid --source value shows error and exits 1
  - Test summarizer.summarize_pending_contents(query=...) with source filter
  - Test summarizer.enqueue_pending_contents(query=...) with status filter

## 3B. Extend Digest CLI with Filters

**Depends on**: 1.1, 1.2, 2.1

- [ ] 3.5 Add `content_query: ContentQuery | None = None` field to `DigestRequest` model
  - Optional field, backward compatible (default None)
  - **Modifies**: `src/models/digest.py`
- [ ] 3.6 Add filter options to `aca create-digest` command
  - Add `--source`, `--publication`, `--search`, `--dry-run` options (via shared query_options.py)
  - `--after`/`--before` already handled by period_start/period_end — do NOT add duplicate date options
  - When filters provided, populate `content_query` on DigestRequest
  - `--dry-run` shows preview of content that would be included in digest
  - **Modifies**: `src/cli/digest_commands.py`
- [ ] 3.7 Update `DigestCreator._fetch_contents()` to use ContentQuery when `request.content_query` is provided
  - Merge semantics: if query.start_date is None → use period_start; if query.end_date is None → use period_end
  - If query.statuses is None → default to [COMPLETED]
  - If query.statuses explicitly includes non-COMPLETED statuses → honor them
  - **Modifies**: `src/processors/digest_creator.py`
- [ ] 3.8 Add unit tests in `tests/cli/test_digest_commands.py` and `tests/processors/test_digest_creator.py`
  - Test digest CLI with source filter
  - Test digest CLI with publication filter
  - Test --dry-run preview for digest (no digest created)
  - Test default behavior unchanged (no content_query = same as before, regression)
  - Test merge semantics: period_start used when query.start_date is None
  - Test merge semantics: COMPLETED appended when query.statuses is None
  - Test explicit non-COMPLETED statuses honored when provided

## 5. API Endpoints

**Depends on**: 1.4 (content_routes.py must be refactored first)

- [ ] 5.1 Add `POST /api/v1/contents/query/preview` endpoint
  - Accept ContentQuery as JSON body
  - Return ContentQueryPreview (HTTP 200)
  - Auth: require session cookie or X-Admin-Key
  - 400 for invalid source_types, statuses, or sort_by (Pydantic validation)
  - 200 with total_count=0 when no content matches (not 204 or error)
  - **Modifies**: `src/api/content_routes.py`
- [ ] 5.2 Extend `POST /api/v1/contents/summarize` to accept optional `query` and `dry_run` fields
  - When `query` provided, resolve matching IDs and summarize those
  - When `content_ids` provided (existing), use those
  - When both provided, `query` takes precedence
  - When neither: default behavior (all PENDING/PARSED)
  - When `dry_run: true`: return ContentQueryPreview (HTTP 200), no jobs enqueued
  - **Modifies**: `src/api/content_routes.py`
- [ ] 5.3 Extend `POST /api/v1/digests/generate` to accept optional `content_query` and `dry_run` fields
  - Pass content_query through to DigestRequest
  - When `dry_run: true`: return ContentQueryPreview (HTTP 200), no digest created
  - **Modifies**: `src/api/digest_routes.py`
- [ ] 5.4 Add API tests in `tests/api/test_query_api.py`
  - Test preview endpoint with various filters
  - Test preview with zero matches returns 200 with total_count=0 and empty breakdowns
  - Test preview with invalid source_type returns 400
  - Test preview with invalid sort_by returns 400
  - Test summarize with query filter enqueues correct IDs
  - Test summarize with both content_ids and query (query wins)
  - Test summarize with neither (default behavior)
  - Test summarize with dry_run=true returns preview without enqueueing
  - Test digest generate with content_query
  - Test digest generate with dry_run=true returns preview
  - Test auth requirements (401 without credentials)
- [ ] 5.5 Update OpenAPI schema: add ContentQuery, ContentQueryPreview to API docs

## 4. Frontend Query Builder

**Depends on**: 5.1 (preview endpoint must exist)

- [ ] 4.1 Create frontend foundation (types + API client + hooks)
  - `web/src/types/query.ts`: ContentQuery, ContentQueryPreview interfaces
  - `web/src/lib/api/query.ts`: `previewContentQuery(query): Promise<ContentQueryPreview>`
  - Add to `web/src/lib/api/query-keys.ts`: `queryKeys.contents.queryPreview(query)`
  - `web/src/hooks/useContentQuery.ts`: `useContentQueryPreview(query)` with 2s staleTime, enabled only when filters active
- [ ] 4.2 Create `web/src/components/query/FilterChip.tsx` — chip with label + value + remove button
- [ ] 4.3 Create `web/src/components/query/SourceFilter.tsx` — multi-select source type picker, checkboxes, select all/clear all
- [ ] 4.4 Create `web/src/components/query/StatusFilter.tsx` — multi-select status picker with badge colors
- [ ] 4.5 Create filter sub-components (can be done in parallel with 4.2–4.4):
  - `web/src/components/query/DateRangeFilter.tsx` — presets (Today, Last 3 days, Last week, Last month) + custom inputs
  - `web/src/components/query/PublicationFilter.tsx` — publication search input
  - `web/src/components/query/QueryPreview.tsx` — count, source/status breakdown, sample titles (collapsed by default, first 3 shown, "Show all" expands). Loading spinner during fetch. Error state with "Retry" button, retains last known preview.
- [ ] 4.6 Create `web/src/components/query/ContentQueryBuilder.tsx` — main composable component
  - Props: `defaultQuery`, `onChange(query)`, `showPreview: boolean`
  - Composes: FilterChip, SourceFilter, StatusFilter, DateRangeFilter, PublicationFilter, QueryPreview
  - "Add filter" dropdown for new dimensions
  - Responsive: `grid-cols-2 md:grid-cols-4` (NOT fixed `min-w-[600px]` — see mobile gotcha)
  - **Depends on**: 4.2–4.5
- [ ] 4.7 Integrate `ContentQueryBuilder` into dialogs
  - Summarize dialog: default query `statuses: [pending, parsed]`, button shows "Summarize N items"
  - Generate Digest dialog: collapsible "Advanced filters" section, default: no query (existing behavior)
  - **Modifies**: `web/src/components/generation/GenerateDigestDialog.tsx` (or equivalent)
  - **Depends on**: 4.6, 5.x

## 6. E2E Tests

**Depends on**: 4.7

- [ ] 6.1 Add E2E test for query preview in summarize dialog
  - Open summarize dialog → verify default status filters → add source filter → verify preview count updates → verify sample titles display
  - Mock `POST /api/v1/contents/query/preview` with deterministic ContentQueryPreview
- [ ] 6.2 Add E2E test for query preview in digest dialog
  - Open generate digest → expand "Advanced filters" → add source filter → verify preview → confirm generation
  - Mock preview endpoint
- [ ] 6.3 Add mock data factories in `web/tests/e2e/fixtures/mock-data.ts`
  - `createMockContentQueryPreview()`: deterministic preview with known counts
  - `createEmptyContentQueryPreview()`: total_count=0, empty breakdowns
  - All fields use snake_case (API convention)

## 7. Documentation

- [ ] 7.1 Update CLAUDE.md: add `--source`, `--status`, `--after`, `--before`, `--publication`, `--search`, `--dry-run` options on summarize/digest commands
- [ ] 7.2 Update `docs/DEVELOPMENT.md`: ContentQuery model usage, ContentQueryService patterns, dry-run conventions
- [ ] 7.3 Inline help text already defined in `query_options.py` (task 2.1) — verify renders correctly
- [ ] 7.4 Update spec to reflect final implementation: `openspec/specs/content-query/spec.md`
