# Tasks: Add Task Audit Log

## Phase 1: Backend Data Layer

- [ ] 1. Add `JobHistoryItem`, `JobHistoryResponse`, `ENTRYPOINT_LABELS`, and `TYPE_ALIASES` to `src/models/jobs.py`
  - `JobHistoryItem`: id, entrypoint, task_label, status, content_id, content_title, error, created_at, started_at, completed_at
  - `JobHistoryResponse`: data list + pagination dict
  - `ENTRYPOINT_LABELS`: dict mapping entrypoint strings to display labels (6 entries: summarize_content, summarize_batch, extract_url_content, scan_newsletters, process_content, ingest_content)
  - `TYPE_ALIASES`: reverse dict mapping CLI `--type` aliases to entrypoint strings (summarize→summarize_content, batch→summarize_batch, extract→extract_url_content, scan→scan_newsletters, process→process_content, ingest→ingest_content)
  - **Verify**: Import and instantiate models in a Python REPL
  - **Files**: `src/models/jobs.py`

- [ ] 2. Add `list_job_history()` function to `src/queue/setup.py`
  - **Depends on**: Task 1
  - LEFT JOIN `pgqueuer_jobs` with `content` table on `payload->>'content_id'`
  - Use `j.payload ? 'content_id'` guard to prevent cast errors for jobs without content_id (ingest_content, scan_newsletters)
  - Accept filters: `since` (datetime), `status` (JobStatus), `entrypoint` (str), `limit`, `offset`
  - Return `tuple[list[JobHistoryItem], int]`
  - Map entrypoint to `task_label` using `ENTRYPOINT_LABELS` (fallback: raw entrypoint)
  - **Verify**: Unit test with mocked asyncpg connection
  - **Files**: `src/queue/setup.py`

- [ ] 3. Add `GET /api/v1/jobs/history` endpoint to `src/api/job_routes.py`
  - **Depends on**: Task 2
  - Query params: `since` (str: ISO datetime or shorthand "1d"/"7d"/"30d"), `status`, `entrypoint`, `page`, `page_size`
  - Parse `since` shorthands into datetime; return 400 for invalid formats
  - Return empty `data: []` with `total: 0` when no results match
  - Call `list_job_history()` and return `JobHistoryResponse`
  - **Verify**: `pytest tests/api/test_job_routes.py` passes
  - **Files**: `src/api/job_routes.py`

## Phase 2: CLI Command

- [ ] 4. Add `aca jobs history` command to `src/cli/job_commands.py`
  - **Depends on**: Task 2
  - Flags: `--since` (1d/7d/30d/custom), `--last N`, `--type` (alias mapped via `TYPE_ALIASES`), `--status`
  - Rich table output: Date/Time, Task, Content ID, Job ID, Content Title, Status
  - JSON output mode support (global `--json` flag via `is_json_mode()`)
  - Map `--type` friendly names to entrypoint values using `TYPE_ALIASES`
  - **Verify**: `pytest tests/cli/test_job_commands.py` passes
  - **Files**: `src/cli/job_commands.py`

## Phase 3: Web UI

- [ ] 5. Add `JobHistoryItem` type and `useJobHistory` hook
  - **Depends on**: Task 3 (API endpoint must exist)
  - Add type to `web/src/types/index.ts`
  - Create `web/src/hooks/use-jobs.ts` with `useJobHistory()` TanStack Query hook
  - **Verify**: Hook compiles and returns typed data
  - **Files**: `web/src/types/index.ts`, `web/src/hooks/use-jobs.ts` (new)

- [ ] 6. Add "Task History" nav item under Management in `web/src/lib/navigation.ts`
  - **Depends on**: None (can run in parallel with task 5)
  - Icon: `ClipboardList` from lucide-react
  - href: `/task-history`
  - **Verify**: Nav item appears in sidebar under Management
  - **Files**: `web/src/lib/navigation.ts`

- [ ] 7. Create `web/src/routes/task-history.tsx` — table and data display
  - **Depends on**: Tasks 5, 6
  - Route definition with `createRoute()`
  - Table with columns: Date/Time, Task, Content ID, Job ID, Content Title, Status
  - Status badges with color coding (matching existing patterns)
  - Loading skeleton and empty state ("No task history found")
  - Pagination controls
  - **Verify**: Page renders with API data
  - **Files**: `web/src/routes/task-history.tsx` (new)

- [ ] 8. Add filter controls to task-history page
  - **Depends on**: Task 7
  - Task type dropdown (from `ENTRYPOINT_LABELS` values)
  - Status dropdown (queued, in_progress, completed, failed)
  - Time range selector (Last 24h, Last 7d, Last 30d, All)
  - Filters update query parameters and trigger re-fetch
  - **Verify**: Filters work with real API
  - **Files**: `web/src/routes/task-history.tsx`

## Phase 4: Tests

- [ ] 9. Add backend tests for history endpoint and CLI command
  - **Depends on**: Tasks 3, 4
  - API test: `tests/api/test_job_routes.py` — test history endpoint with filters, pagination, time parsing, invalid since parameter (400), empty results
  - CLI test: `tests/cli/test_job_commands.py` — test history command output, filters, JSON mode, --type alias resolution
  - **Verify**: `pytest tests/api/test_job_routes.py tests/cli/test_job_commands.py` passes
  - **Files**: `tests/api/test_job_routes.py`, `tests/cli/test_job_commands.py`

- [ ] 10. Add E2E tests for Task History page
  - **Depends on**: Tasks 7, 8
  - `web/tests/e2e/task-history/task-history.spec.ts` — table rendering, filtering, pagination, empty state
  - Mock API responses in test fixtures
  - **Verify**: `cd web && pnpm test:e2e` passes
  - **Files**: `web/tests/e2e/task-history/` (new)
