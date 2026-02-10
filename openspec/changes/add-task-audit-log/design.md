# Design: Task Audit Log

## Architecture Overview

The feature adds a read-only audit view that enriches existing job queue data with content metadata. It spans three layers: backend query function, API endpoint, and two frontends (web + CLI).

```
pgqueuer_jobs ──┐
                ├──→ list_job_history() ──→ GET /api/v1/jobs/history ──→ Web UI (Task History page)
content table ──┘                        └──→ aca jobs history (CLI)
```

## Key Design Decisions

### 1. Description Column: Context-Aware Text

The table uses a **Description** column instead of a narrow "Content Title" column. This provides meaningful context for every job type, not just those with a `content_id`:

| Entrypoint | Description source | Example |
|---|---|---|
| `summarize_content` | Content title from DB (via LEFT JOIN) | "AI Newsletter #15 - GPT-5 Launch" |
| `summarize_batch` | Count from `payload.content_ids` array | "Batch of 12 items" |
| `extract_url_content` | Content title from DB (via LEFT JOIN) | "How to Fine-Tune LLMs" |
| `process_content` | Content title + task_type from payload | "Summarize: AI Weekly Recap" |
| `ingest_content` | Source name from `payload.source` | "Gmail ingestion" / "RSS ingestion" |
| (unknown) | Progress message from `payload.message` | "Starting summarization" |

**Resolution strategy** (applied in `list_job_history()`):
1. If `content_id` exists in payload → LEFT JOIN to get content title
2. Else if `source` exists in payload → format as "{source} ingestion"
3. Else if `content_ids` exists in payload → format as "Batch of {N} items"
4. Else use `payload.message` as fallback → last progress message
5. Else `null`

### 2. Enrichment via LEFT JOIN (not separate queries)

The `pgqueuer_jobs.payload` contains `content_id` for most task types. We enrich job records by LEFT JOIN-ing with the `content` table to fetch titles. This is a single query — no N+1 problem.

**Why LEFT JOIN**: Not all jobs have a `content_id` (e.g., `ingest_content`, `summarize_batch`). LEFT JOIN ensures these jobs still appear in the audit log with `null` title — the description is then built from other payload fields.

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

**Null-safety**: The `j.payload ? 'content_id'` guard prevents cast errors when `content_id` is absent from the payload (e.g., `ingest_content` jobs). The LEFT JOIN still includes these rows — the Python layer builds the description from other payload fields.

**Description assembly**: The SQL returns raw `content_title` and `payload`. The Python `list_job_history()` function builds the `description` field using the resolution strategy above. This keeps the SQL simple and moves the conditional logic to Python where it's easier to test.

### 3. New function, not modifying existing `list_jobs()`

We add `list_job_history()` alongside the existing `list_jobs()` function in `src/queue/setup.py`. Reasons:
- `list_jobs()` is used by background task monitoring and SSE — changing its return type would break callers
- The history function has different filtering needs (time-based) and return shape (includes description)
- Keeps the existing `JobListItem` model untouched

### 4. Task Type Mapping

The `entrypoint` field stores internal names like `summarize_content`, `extract_url_content`. We map these to human-readable labels for display:

| Entrypoint | Display Label | CLI `--type` alias |
|------------|---------------|--------------------|
| `summarize_content` | Summarize | `summarize` |
| `summarize_batch` | Summarize (Batch) | `batch` |
| `extract_url_content` | URL Extraction | `extract` |
| `process_content` | Process Content | `process` |
| `ingest_content` | Ingest | `ingest` |

**Note**: `scan_newsletters` is a legacy entrypoint that is registered but never enqueued by any current code path. The `ingest_content` entrypoint with `source=gmail` superseded it via the orchestrator pattern. If encountered in historical data, it falls back to its raw entrypoint name as the label.

This mapping lives in a shared constant (`ENTRYPOINT_LABELS`) used by both the API response serialization and the CLI formatter. A reverse mapping (`TYPE_ALIASES`) maps CLI `--type` friendly names back to entrypoint strings.

### 5. Time-Based Filtering

The API accepts an optional `since` parameter (ISO 8601 datetime or shorthand like `1d`, `7d`, `30d`). The backend converts shorthands to `datetime.now(UTC) - timedelta(days=N)` before querying.

The CLI maps `--since 1d` / `--since 7d` to the same parameter. The `--last N` flag sets `limit=N` without time filtering.

### 6. Frontend Table Design

The web UI table follows the existing pattern from `contents.tsx`:
- shadcn `<Table>` with `<SortableTableHead>` for sortable columns
- Filter controls: dropdown for task type, dropdown for status, date range selector
- `useQuery` hook for data fetching with `keepPreviousData` for smooth pagination
- Responsive: collapses less-important columns on mobile

Columns: Date/Time | Task | Content ID | Job ID | Description | Status

### 7. New Pydantic Model

```python
class JobHistoryItem(BaseModel):
    id: int                          # job ID
    entrypoint: str                  # raw entrypoint
    task_label: str                  # human-readable label
    status: JobStatus
    content_id: int | None
    description: str | None          # context-aware text (see resolution strategy)
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
```

This is separate from `JobListItem` because it includes `description` and `task_label` — fields that don't belong in the existing model used for real-time monitoring.

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
