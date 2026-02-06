# Change: Add Parallel Job Queue for Pipeline Processing

## Why

The current processing pipeline is sequential and lacks visibility into failures:
- **Speed**: Sources (Gmail, RSS, YouTube, Podcast) run one-at-a-time; summarization processes items in a loop
- **Visibility**: In-memory task tracking (`_ingestion_tasks` dict) is lost on server restart; no way to query job history or retry failures
- **Unification**: CLI and frontend use different job tracking mechanisms

PGQueuer infrastructure already exists (`src/queue/setup.py`, `src/tasks/content.py`) but is not integrated into the main pipeline.

## What Changes

### Core Changes
- Integrate PGQueuer into CLI pipeline commands for parallel processing
- Replace in-memory task dicts with PostgreSQL-backed job tracking
- Unify CLI and frontend job infrastructure on `pgqueuer_jobs` table
- Add worker pool management (`aca worker start --concurrency N`)

### API Changes
- SSE endpoints read job status from database instead of in-memory dict
- New `/api/v1/jobs` endpoints for job listing, status, and retry

### Frontend Changes
- Minimal: same SSE pattern, but task_id now references `pgqueuer_jobs.id`
- Optional: Job history/retry UI component

## Impact

### Affected Specs
- `pipeline` - Processing pipeline behavior (new capability)
- `job-management` - Job tracking and worker management (new capability)

### Affected Code
- `src/cli/pipeline_commands.py` - Parallel ingestion, enqueue summarization
- `src/cli/worker_commands.py` - New worker pool commands
- `src/api/content_routes.py` - Replace in-memory task tracking
- `src/api/job_routes.py` - New job management endpoints
- `src/queue/setup.py` - Add job status/progress helpers
- `src/tasks/content.py` - Add progress tracking to task handlers
- `web/src/hooks/use-jobs.ts` - New job management hooks (optional)

### Expected Outcomes
| Metric | Current | After |
|--------|---------|-------|
| Ingestion (4 sources) | ~3min sequential | ~1min parallel |
| Summarization (100 items) | ~50min | ~10min (5 workers) |
| Failure visibility | Logs only | Structured status + retry |
| Resume after crash | Start over | Resume from queue |

## Non-Goals
- Distributed multi-machine processing (single machine is sufficient for now)
- Ray or Celery adoption (PGQueuer already deployed)
- Real-time WebSocket push (SSE polling is adequate)
