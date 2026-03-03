# Change: Add Content Query Builder for Batch Operations

## Why

Today, `aca summarize pending` grabs **all** PENDING/PARSED content indiscriminately, and `aca create-digest daily` uses only a date range + COMPLETED status filter. There is no way to express targeted selections like:

- "Summarize only YouTube content from the last 3 days"
- "Create a digest from RSS + Gmail sources, excluding podcasts"
- "Re-summarize failed items from a specific publication"

Users need a **query builder** that lets them express complex content selection criteria — filters by source, date range, status, publication — preview the matching set (dry-run), and then submit the batch operation. This should work both in the **CLI** and the **frontend UI**.

## Current State

### What exists
- **API listing filters**: `GET /api/v1/contents` already supports `source_type`, `status`, `publication`, `start_date`, `end_date`, `search`, `sort_by`, `sort_order` — but only for **listing**, not for batch action targeting.
- **Summarizer selection**: `summarize_pending_contents()` hardcodes `status IN (PENDING, PARSED)` with only a `limit` parameter.
- **Digest selection**: `DigestRequest` accepts `period_start`/`period_end` and always filters `status = COMPLETED`.
- **Dry-run pattern**: `aca jobs cleanup --dry-run` and `aca manage backfill-chunks --dry-run` show the established codebase pattern.
- **Frontend filters**: Content page has source/status dropdowns and search, but these are disconnected from summarization/digest generation actions.

### The gap
No bridge between "filter/list content" → "submit batch job for filtered set." The selection criteria and the action are separate systems that can't compose.

## What Changes

### 1. Content Query Model (shared foundation)

A `ContentQuery` Pydantic model that encapsulates all filter criteria, reusable across CLI, API, and services:

```python
class ContentQuery(BaseModel):
    """Reusable content selection criteria for batch operations."""
    source_types: list[ContentSource] | None = None
    statuses: list[ContentStatus] | None = None
    publications: list[str] | None = None   # exact match list
    publication_search: str | None = None    # ILIKE pattern
    start_date: datetime | None = None
    end_date: datetime | None = None
    search: str | None = None               # title ILIKE
    limit: int | None = Field(default=None, gt=0)
    sort_by: str = "published_date"         # validated against CONTENT_SORT_FIELDS
    sort_order: str = "desc"
```

**Null field semantics**: `None` means "no filter" (match all). Empty list `[]` is treated the same as `None`.

**Sort field validation**: `sort_by` is validated against `CONTENT_SORT_FIELDS = {"id", "title", "source_type", "publication", "status", "published_date", "ingested_at"}` — invalid values return 400.

**Operation-specific defaults**: When `ContentQuery` is passed without explicit `statuses`, each operation applies its own default:
- Summarizer: defaults to `[PENDING, PARSED]`
- Digest creator: defaults to `[COMPLETED]`

This ensures `ContentQuery()` (empty) behaves differently depending on the operation context, not as a global "match all."

### 2. Query Execution Service

A `ContentQueryService` that:
- Translates `ContentQuery` → SQLAlchemy query
- Provides `resolve(query) -> ContentQueryResult` with matched IDs + summary stats
- Provides `preview(query) -> ContentQueryPreview` with count, breakdown by source/status, date range span
- Reuses the same filter logic already in `content_routes.py` (DRY)

### 3. CLI Integration

New filter and `--dry-run` options on existing commands:

```bash
# Preview what would be summarized (dry-run calls ContentQueryService.preview())
aca summarize pending --source youtube,rss --after 2026-02-20 --dry-run

# Summarize with filters
aca summarize pending --source youtube --status parsed --limit 50

# Preview content for digest
aca create-digest daily --source gmail,rss --publication "The Batch" --dry-run
```

**`--dry-run` semantics**: Calls `ContentQueryService.preview()` and displays a `ContentQueryPreview` as a Rich table (or JSON with `--output json`). No batch operation is executed. This is the same preview the API returns.

**Validation**: Invalid `--source` or `--status` values print an error with valid options and exit code 1. Invalid `--after`/`--before` dates (not YYYY-MM-DD format) print a format error. `--limit` must be > 0.

### 4. API Integration

New and extended endpoints:

- `POST /api/v1/contents/query/preview` — Preview matching content (count, breakdown, up to 10 sample titles)
- Extended `POST /api/v1/contents/summarize` — Accept optional `query` field (alternative to `content_ids`); supports `dry_run: true` to return preview without executing
- Extended `POST /api/v1/digests/generate` — Accept optional `content_query` field for content selection override; supports `dry_run: true`

**`dry_run: true` API semantics**: Returns `ContentQueryPreview` in the response body. No jobs are enqueued, no digest is generated. HTTP 200 with preview payload.

**Empty result**: When query matches zero items, returns `total_count: 0` with empty breakdowns (not 204 or error).

### 5. Frontend Query Builder

A composable `ContentQueryBuilder` component that:
- Renders filter chips for source types, statuses, date range, publications
- Shows live preview count as filters change (debounced)
- Integrates into the existing Summarize and Generate Digest dialogs
- Replaces the current simple filter dropdowns with a unified query builder
- Shows a dry-run preview panel before confirming batch operations

## Impact

- **Affected specs**: `content-query` (new capability spec)
- **Affected code**:
  - `src/models/query.py` — New ContentQuery model
  - `src/services/content_query.py` — New query execution service
  - `src/processors/summarizer.py` — Accept ContentQuery filters
  - `src/processors/digest_creator.py` — Accept ContentQuery for content override
  - `src/models/digest.py` — Add optional `content_query` field to DigestRequest
  - `src/api/content_routes.py` — New preview endpoint, refactored listing to use ContentQuery
  - `src/api/digest_routes.py` — Extended generation endpoint
  - `src/cli/summarize_commands.py` — New filter options + `--dry-run`
  - `src/cli/digest_commands.py` — New filter options + `--dry-run`
  - `src/cli/query_options.py` — Shared CLI option definitions
  - `web/src/components/query/` — New ContentQueryBuilder component
  - `web/src/lib/api/query.ts` — New API client functions
  - `web/src/hooks/useContentQuery.ts` — New React hook
- **Test coverage**: Unit tests for ContentQueryService, CLI command tests, API integration tests, E2E tests for dialog workflows
- **Breaking changes**: None — all additions are opt-in. Existing commands and API endpoints work unchanged.
- **Performance**: Preview queries are lightweight (COUNT + GROUP BY). No full content loading for dry-run.

## Non-Goals

- **Full-text/semantic search** — Use the existing search system (`src/services/search.py`) instead
- **Saved/favorite queries** — Future enhancement; users can re-type or script CLI flags
- **Scheduled query execution** — Future enhancement; pipelines handle scheduling
- **Complex boolean operators** (AND/OR/NOT, regex) — Structured filters are sufficient for the known dimensions
- **Standalone `aca query` command group** — Redundant with `--dry-run` on existing commands; may be added later if exploration use cases emerge
- **Tags filtering** — Content model does not have a tags field; deferred until content tagging is implemented
- **Content listing page refactor** — The existing Contents page filter UI continues to work; shared components may be adopted later

## Design Decisions

### Why not a full SQL/DSL parser?
A structured filter model is safer, more discoverable, and composable across CLI flags, API JSON, and UI components. A raw SQL-like DSL would require parsing, validation, and SQL injection prevention — overkill for a well-defined set of filter dimensions. The CLI flag syntax (`--source youtube,rss --after 2026-02-20`) feels natural and is easy to tab-complete.

### Why extend existing commands instead of a standalone query command?
Adding `--source`, `--status`, `--after`, `--before`, `--publication`, `--dry-run` to `aca summarize pending` and `aca create-digest` is more ergonomic than a separate `aca query` command group. The `--dry-run` flag on existing commands provides the same exploration/preview capability without duplicating filter logic across multiple command modules.

### Why `ContentQuery` as a shared model?
A single model ensures CLI, API, and frontend all express the same filter semantics. The CLI translates flags → ContentQuery, the API accepts it as JSON body, and the frontend serializes it from the query builder component.

## Related Work

- **Existing content listing** (`GET /api/v1/contents`) — Filter logic will be extracted and reused
- **Job queue system** (`src/queue/`) — Batch operations enqueue through existing worker infrastructure
- **Search system** (`src/services/search.py`) — Complementary; search is full-text/semantic, query builder is structured filters
