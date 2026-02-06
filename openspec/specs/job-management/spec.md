# job-management Specification

## Purpose
TBD - created by archiving change add-parallel-job-queue. Update Purpose after archive.
## Requirements
### Requirement: Persistent Job Tracking

The system SHALL persist all job state in PostgreSQL via `pgqueuer_jobs` table.

#### Scenario: Job survives server restart
- **WHEN** a job is in `in_progress` status with `updated_at` < 1 hour ago
- **AND** the server restarts
- **THEN** the job state is preserved in the database
- **AND** a worker can claim and resume the job after restart

#### Scenario: Stale job detection
- **WHEN** a job is in `in_progress` status with `updated_at` >= 1 hour ago
- **THEN** the job is considered stale (worker likely crashed)
- **AND** a cleanup process marks it `failed` with error `stale_timeout`

#### Scenario: Job progress updates
- **WHEN** a worker updates job progress
- **THEN** the progress MUST be stored in `pgqueuer_jobs.payload.progress` as integer (0-100)
- **AND** a message MUST be stored in `pgqueuer_jobs.payload.message` as string
- **AND** the `updated_at` timestamp is refreshed
- **AND** the progress is queryable via `GET /api/v1/jobs/{id}` and `aca jobs show {id}`

### Requirement: Worker Pool Management

The system SHALL provide CLI commands for managing the worker pool.

#### Scenario: Start worker pool
- **WHEN** `aca worker start --concurrency 5` is executed
- **THEN** 5 worker processes are started and report `ready` status to stdout
- **AND** within 2 seconds, the first available job in `pgqueuer_jobs` is claimed
- **AND** the job status changes from `queued` to `in_progress`

#### Scenario: Start worker pool with defaults
- **WHEN** `aca worker start` is executed without `--concurrency`
- **THEN** 5 workers are started by default (configurable via `WORKER_CONCURRENCY` env var)
- **AND** maximum allowed concurrency is 20

#### Scenario: Graceful shutdown
- **WHEN** the worker pool receives SIGTERM signal
- **THEN** the worker pool SHALL NOT claim any new jobs
- **AND** in-progress jobs are allowed to complete within 5 minutes (grace period)
- **AND** if a job exceeds the grace period, it is left in `in_progress` status for later resumption
- **AND** the worker process exits with code 0 after grace period or when all jobs complete

#### Scenario: Worker crash during job execution
- **WHEN** a worker process crashes while processing a job
- **THEN** the job remains in `in_progress` status in the database
- **AND** after 1 hour (stale threshold), the cleanup process marks it `failed`
- **AND** operators can retry the job via `aca jobs retry {id}`

### Requirement: Job Status API

The system SHALL provide HTTP endpoints for job status and management.

#### Scenario: List jobs with filters
- **WHEN** `GET /api/v1/jobs?status=failed&limit=20` is called
- **THEN** a 200 OK response is returned with JSON:
```json
{
  "data": [
    {
      "id": "string",
      "entrypoint": "string",
      "status": "queued|in_progress|completed|failed",
      "error": "string | null",
      "payload": {"content_id": 42, "progress": 100, "message": "..."},
      "created_at": "ISO8601",
      "updated_at": "ISO8601"
    }
  ],
  "pagination": {"page": 1, "page_size": 20, "total": 150}
}
```
- **AND** default page_size is 20, max is 100
- **AND** only jobs matching the status filter are returned

#### Scenario: Get single job status
- **WHEN** `GET /api/v1/jobs/{id}` is called
- **THEN** a 200 OK response with full job details is returned
- **AND** if job not found, 404 is returned

#### Scenario: Retry failed job
- **WHEN** `POST /api/v1/jobs/{id}/retry` is called
- **AND** the job status is `failed`
- **THEN** the job status is reset to `queued`
- **AND** the `retry_count` is incremented
- **AND** a worker picks up the job for reprocessing
- **AND** 200 OK with updated job is returned

#### Scenario: Retry non-failed job
- **WHEN** `POST /api/v1/jobs/{id}/retry` is called
- **AND** the job status is NOT `failed`
- **THEN** 400 Bad Request is returned with error message

### Requirement: Job Management CLI

The system SHALL provide CLI commands for job management.

#### Scenario: List jobs with table output
- **WHEN** `aca jobs list --status=failed` is executed
- **THEN** output is printed as ASCII table with columns:
  - id (truncated to 8 chars)
  - entrypoint (truncated to 20 chars)
  - error (truncated to 40 chars)
  - created_at (ISO8601 format)
- **AND** rows are sorted by created_at DESC

#### Scenario: Show job details
- **WHEN** `aca jobs show {id}` is executed
- **THEN** full job details are displayed including payload and error
- **AND** progress is shown as percentage with message

#### Scenario: Retry failed jobs
- **WHEN** `aca jobs retry --failed` is executed
- **THEN** all jobs with status `failed` are re-enqueued
- **AND** the count of retried jobs is displayed

#### Scenario: Retry specific job
- **WHEN** `aca jobs retry {id}` is executed
- **THEN** the specific job is re-enqueued if status is `failed`
- **AND** error is shown if job is not retryable

#### Scenario: Cleanup old jobs
- **WHEN** `aca jobs cleanup --older-than 30d` is executed
- **THEN** jobs with status `completed` and `completed_at` older than 30 days are deleted
- **AND** jobs in `queued`, `in_progress`, or `failed` status are NOT deleted
- **AND** the count of deleted jobs is displayed

#### Scenario: Automatic job retention
- **WHEN** no manual cleanup is performed
- **THEN** completed jobs older than `JOB_RETENTION_DAYS` (default: 30) are eligible for automatic cleanup
- **AND** automatic cleanup runs via scheduled task (if configured)

### Requirement: Frontend SSE Integration

The system SHALL provide SSE endpoints that read job status from the database.

#### Scenario: SSE streams database state
- **WHEN** a frontend subscribes to `/api/v1/contents/ingest/status/{task_id}`
- **THEN** the SSE stream polls `pgqueuer_jobs` for status updates
- **AND** progress events are emitted at approximately 500ms intervals (acceptable range: 400-600ms)
- **AND** events continue until the job reaches terminal state (`completed` or `failed`)

#### Scenario: SSE terminal event
- **WHEN** a job reaches `completed` or `failed` status
- **THEN** the SSE stream emits a final event with the terminal status
- **AND** the SSE connection is closed gracefully

#### Scenario: SSE survives API restart
- **WHEN** an SSE connection is active
- **AND** the API server restarts
- **THEN** the frontend detects SSE disconnection (EventSource readyState = CLOSED)
- **AND** frontend can reconnect to the same `/api/v1/contents/ingest/status/{task_id}`
- **AND** job status is retrieved from the database (not lost)
- **AND** if job already completed during downtime, the reconnected SSE emits the terminal event immediately

### Requirement: Job Timeout Configuration

The system SHALL enforce configurable timeouts for job execution.

#### Scenario: Job execution timeout
- **WHEN** a job is in `in_progress` status
- **AND** it exceeds `JOB_TIMEOUT` (default: 1 hour, configurable via environment)
- **THEN** the stale job cleanup process marks it `failed` with error `job_timeout`

#### Scenario: Configurable timeout via environment
- **WHEN** `JOB_TIMEOUT=3600` is set in environment (seconds)
- **THEN** jobs are considered stale after 3600 seconds of no progress update
