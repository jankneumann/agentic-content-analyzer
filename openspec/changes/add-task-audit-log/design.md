# Design: Task Audit Log

## Architecture Overview

The feature adds a read-only audit view that enriches existing job queue data with content metadata. It spans three layers: backend query function, API endpoint, and two frontends (web + CLI).

```
pgqueuer_jobs ──┐
                ├──→ list_job_history() ──→ GET /api/v1/jobs/history ──→ Web UI (Task History page)
content table ──┘                        └──→ aca jobs history (CLI)
```

## Key Design Decisions

### 1. Enrichment via LEFT JOIN (not separate queries)

The `pgqueuer_jobs.payload` contains `content_id` for most task types. We enrich job records by LEFT JOIN-ing with the `content` table to fetch titles. This is a single query — no N+1 problem.

**Why LEFT JOIN**: Not all jobs have a `content_id` (e.g., `scan_newsletters`, `summarize_batch`). LEFT JOIN ensures these jobs still appear in the audit log with `null` title.

**SQL pattern**:
```sql
SELECT j.id, j.entrypoint, j.status, j.payload, j.error,
       j.created_at, j.started_at, j.completed_at,
       c.id AS content_id, c.title AS content_title
FROM pgqueuer_jobs j
LEFT JOIN content c
  ON j.payload ? 'content_id'
  AND (j.payload->>'content_id')::int = c.id
WHERE j.created_at >= $1
ORDER BY j.created_at DESC
LIMIT $2 OFFSET $3
```

**Null-safety**: The `j.payload ? 'content_id'` guard prevents cast errors when `content_id` is absent from the payload (e.g., `ingest_content` and `scan_newsletters` jobs). The LEFT JOIN still includes these rows with `content_id = NULL` and `content_title = NULL`.

### 2. New function, not modifying existing `list_jobs()`

We add `list_job_history()` alongside the existing `list_jobs()` function in `src/queue/setup.py`. Reasons:
- `list_jobs()` is used by background task monitoring and SSE — changing its return type would break callers
- The history function has different filtering needs (time-based) and return shape (includes content title)
- Keeps the existing `JobListItem` model untouched

### 3. Task Type Mapping

The `entrypoint` field stores internal names like `summarize_content`, `extract_url_content`. We map these to human-readable labels for display:

| Entrypoint | Display Label | CLI `--type` alias |
|------------|---------------|--------------------|
| `summarize_content` | Summarize | `summarize` |
| `summarize_batch` | Summarize (Batch) | `batch` |
| `extract_url_content` | URL Extraction | `extract` |
| `scan_newsletters` | Gmail Scan | `scan` |
| `process_content` | Process Content | `process` |
| `ingest_content` | Ingest | `ingest` |

This mapping lives in a shared constant (`ENTRYPOINT_LABELS`) used by both the API response serialization and the CLI formatter. A reverse mapping (`TYPE_ALIASES`) maps CLI `--type` friendly names back to entrypoint strings.

**Note on `ingest_content`**: Ingest jobs store `source` (e.g., "gmail", "rss") in the payload instead of `content_id`. The task label for ingest jobs may optionally be enriched to "Ingest (gmail)" by extracting `payload.source`. These jobs will always have `content_id: null` and `content_title: null`.

### 4. Time-Based Filtering

The API accepts an optional `since` parameter (ISO 8601 datetime or shorthand like `1d`, `7d`, `30d`). The backend converts shorthands to `datetime.now(UTC) - timedelta(days=N)` before querying.

The CLI maps `--since 1d` / `--since 7d` to the same parameter. The `--last N` flag sets `limit=N` without time filtering.

### 5. Frontend Table Design

The web UI table follows the existing pattern from `contents.tsx`:
- shadcn `<Table>` with `<SortableTableHead>` for sortable columns
- Filter controls: dropdown for task type, dropdown for status, date range selector
- `useQuery` hook for data fetching with `keepPreviousData` for smooth pagination
- Responsive: collapses less-important columns on mobile

Columns: Date/Time | Task | Content ID | Job ID | Content Title | Status

### 6. New Pydantic Model

```python
class JobHistoryItem(BaseModel):
    id: int                          # job ID
    entrypoint: str                  # raw entrypoint
    task_label: str                  # human-readable label
    status: JobStatus
    content_id: int | None
    content_title: str | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
```

This is separate from `JobListItem` because it includes `content_title` and `task_label` — fields that don't belong in the existing model used for real-time monitoring.

## File Changes

### Backend (Python)
- `src/models/jobs.py` — Add `JobHistoryItem`, `JobHistoryResponse`, `ENTRYPOINT_LABELS`, `TYPE_ALIASES`
- `src/queue/setup.py` — Add `list_job_history()` function
- `src/api/job_routes.py` — Add `GET /api/v1/jobs/history` endpoint
- `src/cli/job_commands.py` — Add `aca jobs history` command

### Frontend (TypeScript/React)
- `web/src/routes/task-history.tsx` — New route component
- `web/src/lib/navigation.ts` — Add nav item under Management group
- `web/src/hooks/use-jobs.ts` — New hook for job history API
- `web/src/types/index.ts` — Add `JobHistoryItem` type

### Tests
- `tests/api/test_job_routes.py` — Tests for the new history endpoint
- `tests/cli/test_job_commands.py` — Tests for the new history CLI command
- `web/tests/e2e/task-history/` — E2E tests for the web UI
