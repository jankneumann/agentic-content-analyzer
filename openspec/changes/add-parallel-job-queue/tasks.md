# Implementation Tasks

## File Overlap Notes (Critical for Parallel Execution)

**MUST sequence these sections to avoid merge conflicts:**

| File | Sections Modifying | Resolution |
|------|-------------------|------------|
| `src/cli/pipeline_commands.py` | 1, 3, 4 | Complete Section 3 before Section 4 |
| `src/api/content_routes.py` | 1, 5 | Section 5 after Section 1 |
| `src/queue/setup.py` | 2, 3, 4 | Section 2 first (creates helpers) |

**Independent streams (can run in parallel):**
- Stream A: Section 2 (infrastructure) → required by all others
- Stream B: Section 1 (visibility) → depends on Section 2
- Stream C: Section 3 (parallel ingestion) → depends on Sections 1-2
- Stream D: Section 4 (worker pool) → depends on Sections 2-3
- Stream E: Section 5-6 (API/CLI) → depends on Section 2
- Stream F: Section 7-8 (testing/docs) → after all implementation

---

## 1. Pipeline Visibility (Foundation)

**Depends on:** Section 2 (for progress helpers)

- [x] 1.1 Add structured logging with OTel spans for each pipeline stage in `src/cli/pipeline_commands.py`
  - Span names: `pipeline.ingestion`, `pipeline.summarization`, `pipeline.digest`
  - Attributes: `status`, `item_count`, `error_message` (on failure)
- [x] 1.2 Add pipeline stage metrics to `src/telemetry/metrics.py` (start/complete/error counters)
  - Meters: `pipeline.stage.started`, `pipeline.stage.completed`, `pipeline.stage.failed`
- [x] 1.3 Add per-item status tracking in `src/processors/summarizer.py`
  - **Depends on:** 2.2 (`update_job_progress` helper must exist)
  - Create OTel span per content item being summarized

## 2. Job Status Infrastructure

**Depends on:** Nothing (foundation layer)
**Blocks:** Sections 1, 3, 4, 5, 6

- [x] 2.1 Add `get_job_status(job_id)` helper to `src/queue/setup.py`
  - Returns `JobStatus` model with id, status, progress, message, timestamps
- [x] 2.2 Add `update_job_progress(job_id, progress, message)` helper to `src/queue/setup.py`
  - Updates `payload.progress` (0-100) and `payload.message`
  - Refreshes `updated_at` timestamp
- [x] 2.3 Add progress field support to `pgqueuer_jobs` schema (via payload JSON)
  - Document payload schema: `{"content_id": int, "progress": 0-100, "message": str}`
  - No alembic migration needed (uses existing JSONB column)
- [x] 2.4 Create `JobStatus` Pydantic model in `src/models/jobs.py`
  - Fields: id, entrypoint, status, error, payload, created_at, updated_at

## 3. Parallel Ingestion

**Depends on:** Section 2 (for progress helpers)
**Modifies:** `src/cli/pipeline_commands.py` (lines ~20-87)
**Blocks:** Section 4 (must complete before 4.2-4.4)

- [x] 3.1 Refactor `_run_ingestion_stage()` to use `asyncio.gather()` for parallel source ingestion
  - Wrap each source in `asyncio.to_thread()`
  - Handle `return_exceptions=True` for partial failures
- [x] 3.2 Add error handling for partial failures (some sources fail, others succeed)
  - **Depends on:** 3.1
  - Log failed sources with OTel spans (status=ERROR)
  - Continue if at least 1 source succeeds
- [x] 3.3 Add ingestion progress tracking per source
  - **Depends on:** 3.1, 2.1, 2.2
  - Create OTel span per source: `ingestion.gmail`, `ingestion.rss`, etc.
- [x] 3.4 Update CLI output to show parallel progress
  - **Depends on:** 3.3
  - Show concurrent source status (e.g., "[2/4 complete, 1 failed, 1 running]")

## 4. Worker Pool for Summarization

**Depends on:** Sections 2, 3
**Modifies:** `src/cli/pipeline_commands.py` (lines ~90-102), `src/tasks/content.py`
**CRITICAL:** Must wait for Section 3 to complete before modifying `pipeline_commands.py`

- [x] 4.1 Create `src/cli/worker_commands.py` with `aca worker start --concurrency N`
  - **Depends on:** 2.1, 2.2
  - Default concurrency: 5 (via `WORKER_CONCURRENCY` env var)
  - Max concurrency: 20
  - Print "ready" status when workers start
- [ ] 4.2 Refactor `summarize_pending_contents()` to enqueue jobs instead of direct processing
  - **Depends on:** 4.1
  - **Modifies:** `src/processors/summarizer.py`, `src/cli/pipeline_commands.py`
  - Enqueue with payload: `{"content_id": int}`
  - Skip content_ids already in `queued` or `in_progress` status (idempotency)
- [ ] 4.3 Add `summarize_content` entrypoint to `src/tasks/content.py` with progress tracking
  - **Depends on:** 4.1, 2.2
  - Call `update_job_progress(job.id, progress, message)` during processing
  - Handle Anthropic 429 with exponential backoff (5s, 10s, 20s)
- [ ] 4.4 Add `--wait` flag to pipeline commands to wait for worker completion
  - **Depends on:** 4.2
  - Poll `pgqueuer_jobs` until all enqueued jobs complete
- [x] 4.5 Implement worker health check and graceful shutdown
  - **Depends on:** 4.1
  - Handle SIGTERM: stop claiming jobs, wait 5 min for in-progress
  - Exit code 0 on clean shutdown

## 5. API Integration

**Depends on:** Section 2
**Modifies:** `src/api/content_routes.py` (different functions, can parallelize 5.1 and 5.2)

- [ ] 5.1 Replace `_ingestion_tasks` dict with `pgqueuer_jobs` queries in `src/api/content_routes.py`
  - **Depends on:** 2.1
  - Modifies: `trigger_content_ingestion()`, `get_ingestion_status()`
- [ ] 5.2 Replace `_summarization_tasks` dict with `pgqueuer_jobs` queries
  - **Depends on:** 2.1
  - Modifies: `trigger_content_summarization()`, `get_summarization_status()`
  - Can run in parallel with 5.1 (different functions)
- [ ] 5.3 Update SSE endpoints to read from database
  - **Depends on:** 5.1, 5.2
  - Poll at ~500ms intervals (400-600ms acceptable)
  - Close gracefully on terminal state
- [ ] 5.4 Create `src/api/job_routes.py` with list/status/retry endpoints
  - **Depends on:** 2.4
  - GET /jobs (with filters), GET /jobs/{id}, POST /jobs/{id}/retry
  - Return JSON per spec (pagination included)
- [ ] 5.5 Add job routes to FastAPI app
  - **Depends on:** 5.4
  - Register router in `src/api/app.py`

## 6. Job Management CLI

**Depends on:** Section 2
**Independent of:** Sections 3, 4, 5 (new file, no conflicts)

- [x] 6.1 Create `src/cli/job_commands.py` with `aca jobs list/show/retry` commands
  - **Depends on:** 2.4
  - ASCII table output with truncation
- [x] 6.2 Add filtering by status, entrypoint, date range
  - **Depends on:** 6.1
- [x] 6.3 Add bulk retry for failed jobs
  - **Depends on:** 6.1
  - `aca jobs retry --failed`
- [x] 6.4 Add job cleanup for old completed jobs
  - **Depends on:** 6.1
  - `aca jobs cleanup --older-than 30d`
  - Only delete `completed` jobs (never delete queued/in_progress/failed)

## 7. Testing

**Depends on:** Sections 2-6 (implementation must be testable)

- [ ] 7.1 Unit tests for job status helpers (`tests/test_queue/test_setup.py`)
  - Test `get_job_status()`, `update_job_progress()`
  - Mock database connection
- [ ] 7.2 Integration tests for parallel ingestion (`tests/test_cli/test_pipeline.py`)
  - **Depends on:** 7.1, Section 3
  - Test partial failure handling
  - Test timeout behavior
- [ ] 7.3 Integration tests for worker pool (`tests/test_cli/test_worker.py`)
  - **Depends on:** 7.1, Section 4
  - Test concurrency limit enforcement
  - Test graceful shutdown
- [ ] 7.4 E2E test: trigger ingestion from frontend, verify SSE progress
  - **Depends on:** 7.1, 7.2, Section 5
  - Test SSE event format and timing
- [ ] 7.5 E2E test: server restart mid-job, verify resume
  - **Depends on:** 7.3, Section 5
  - Test stale job detection
  - Test frontend reconnection
- [ ] 7.6 Unit test: job deduplication in enqueue logic
  - Test that same content_id is not enqueued twice
- [ ] 7.7 Integration test: API pagination edge cases
  - Test page_size=0, negative, >100

## 8. Documentation

**Depends on:** Sections 1-7 (document after implementation)

- [ ] 8.1 Update `docs/ARCHITECTURE.md` with job queue architecture diagram
  - Add section: "Job Queue Architecture"
  - Include flow diagram: Producer → Queue → Worker Pool
- [ ] 8.2 Update `docs/DEVELOPMENT.md` with worker commands
  - Add `aca worker start` to key commands table
  - Add troubleshooting section for worker issues
- [ ] 8.3 Update `CLAUDE.md` with new CLI commands
  - Add `aca worker` and `aca jobs` command groups
  - Add to "Key Commands" section
