# Design: Parallel Job Queue

## Context

The ACA processing pipeline currently runs sequentially with no job tracking persistence. This creates two problems:

1. **Performance**: Processing 100+ items takes 50+ minutes when it could take ~10 minutes with parallelism
2. **Observability**: No way to see why a pipeline failed, retry specific items, or resume after crashes

### Stakeholders
- **Users**: Want faster digests and visibility into failures
- **Developers**: Need to debug pipeline issues
- **Operators**: Need job history and retry capabilities

### Constraints
- PGQueuer is already deployed (use it, don't add Redis/Celery)
- Single machine deployment (no distributed workers needed)
- SSE pattern for frontend progress (don't break existing UI)

## Goals / Non-Goals

### Goals
- Reduce pipeline execution time by 5x via parallelism
- Persist job state across server restarts
- Provide job history and retry capabilities
- Unify CLI and frontend job tracking

### Non-Goals
- Distributed multi-machine processing
- Real-time WebSocket push (SSE polling is fine)
- Ray framework integration (overkill for current scale)
- Job priority scheduling beyond basic FIFO

## Decisions

### Decision 1: Use PGQueuer for All Job Tracking

**What**: All jobs (ingestion, summarization, digest generation) go through `pgqueuer_jobs` table.

**Why**:
- Already deployed, no new infrastructure
- PostgreSQL-backed = durable by default
- `SELECT FOR UPDATE SKIP LOCKED` provides safe concurrent access
- Can query job history with SQL

**Alternatives considered**:
- Redis/Celery: More features, but adds operational complexity
- Ray: Overkill for single-machine, learning curve
- Keep in-memory: Loses state on restart

### Decision 2: Async Parallel Ingestion via `asyncio.gather()`

**What**: Run all 4 ingestion sources concurrently, don't enqueue individual emails/items.

**Why**:
- Each source is already a single HTTP call + batch insert
- Parallelism at source level is sufficient (4 sources → 4 concurrent)
- Avoids queue overhead for thousands of individual items

**Pattern**:
```python
async def _run_ingestion_stage_parallel():
    tasks = [
        asyncio.to_thread(gmail_service.ingest_content),
        asyncio.to_thread(rss_service.ingest_content),
        asyncio.to_thread(youtube_service.ingest_content),
        asyncio.to_thread(podcast_service.ingest_content),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Handle partial failures
```

### Decision 3: Queue-Based Summarization with Worker Pool

**What**: Enqueue content IDs for summarization; N workers pull from queue.

**Why**:
- Summarization is the bottleneck (~30s per item)
- Queue provides natural load distribution
- Failed items can be retried without re-running entire pipeline

**Pattern**:
```python
# Producer (pipeline command)
for content_id in pending_ids:
    await queries.enqueue("summarize_content", {"content_id": content_id})

# Consumer (worker)
@pgq.entrypoint("summarize_content")
async def summarize_content(job: Job):
    content_id = job.payload["content_id"]
    await update_job_progress(job.id, 0, "Starting...")
    summarizer.summarize_content(content_id)
    await update_job_progress(job.id, 100, "Complete")
```

### Decision 4: Store Progress in Job Payload JSON

**What**: Extend `pgqueuer_jobs.payload` JSONB to include `progress` and `message` fields.

**Why**:
- Avoids schema migration for new columns
- Flexible for different job types
- Already using JSONB for job parameters

**Schema** (no migration needed):
```json
{
  "content_id": 42,
  "progress": 50,
  "message": "Processing..."
}
```

### Decision 5: SSE Polls Database, Not In-Memory Dict

**What**: Replace `_ingestion_tasks[task_id]` with `SELECT * FROM pgqueuer_jobs WHERE id = $1`.

**Why**:
- Survives server restart
- Works with multiple API workers
- Queryable for job history

**Trade-off**: Slightly higher latency (DB query vs dict lookup) — acceptable for 500ms polling interval.

## Risks / Trade-offs

### Risk: PGQueuer Polling Overhead
- **Issue**: Workers poll DB for new jobs
- **Mitigation**: PGQueuer uses `pg_notify` for instant wake-up; polling is fallback only

### Risk: Job Table Growth
- **Issue**: `pgqueuer_jobs` grows unbounded
- **Mitigation**: Add cleanup command (`aca jobs cleanup --older-than 30d`)

### Risk: LLM Rate Limits with High Concurrency
- **Issue**: 10 workers × 10 concurrent summarizations = rate limit errors
- **Mitigation**: Configure `--concurrency` based on API limits; add backoff in task handler

### Trade-off: Complexity vs Performance
- **Trade-off**: More moving parts (workers, queue table) for 5x speedup
- **Accepted**: Performance gain justifies modest complexity increase

## Migration Plan

### Phase 1: Add Infrastructure (No Breaking Changes)
1. Add job status helpers to `src/queue/setup.py`
2. Add worker command (`aca worker start`)
3. Add job management command (`aca jobs list`)

### Phase 2: Parallel Ingestion
1. Refactor `_run_ingestion_stage()` to use `asyncio.gather()`
2. Backward compatible — no API changes

### Phase 3: Queue-Based Summarization
1. Add `--use-queue` flag to `aca summarize pending`
2. Make queue-based the default after testing

### Phase 4: API Integration
1. Replace in-memory dicts with DB queries
2. Add `/api/v1/jobs` endpoints
3. Frontend automatically uses new backend

### Rollback Plan
- Phase 1-2: No rollback needed (additive)
- Phase 3: Remove `--use-queue` flag, revert to direct calls
- Phase 4: Re-add in-memory dicts (code preserved in git)

## Resolved Questions

1. **Worker lifecycle**: Should workers run as systemd service, or launched on-demand by pipeline?
   - **Decision**: On-demand via `aca worker start` for development. Systemd integration is out of scope for this proposal (operators can wrap the CLI command).

2. **Job retention**: How long to keep completed jobs?
   - **Decision**: 30 days default, configurable via `JOB_RETENTION_DAYS` environment variable. Manual cleanup via `aca jobs cleanup --older-than 30d`. Automatic scheduled cleanup is optional (requires pg_cron or external scheduler).

3. **Concurrent worker limit**: Hard cap on workers to prevent resource exhaustion?
   - **Decision**: Default 5 workers (configurable via `WORKER_CONCURRENCY`). Maximum 20 workers enforced. This balances LLM API rate limits with throughput.
