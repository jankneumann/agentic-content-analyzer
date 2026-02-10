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

### Requirement: Job History API with Content Enrichment

The system SHALL provide an API endpoint for querying historical job records enriched with content metadata for audit purposes.

#### Scenario: List job history with descriptions
- **WHEN** `GET /api/v1/jobs/history` is called
- **THEN** a 200 OK response is returned with JSON:
```json
{
  "data": [
    {
      "id": 123,
      "entrypoint": "summarize_content",
      "task_label": "Summarize",
      "status": "completed",
      "content_id": 42,
      "description": "AI Newsletter #15 - GPT-5 Launch",
      "error": null,
      "created_at": "ISO8601",
      "started_at": "ISO8601",
      "completed_at": "ISO8601"
    }
  ],
  "pagination": {"page": 1, "page_size": 20, "total": 150}
}
```
- **AND** `task_label` is a human-readable name derived from `entrypoint`
- **AND** `description` is a context-aware text resolved from job payload: content title (via LEFT JOIN) for content-linked jobs, source name for ingestion jobs, batch count for batch jobs, or `null` if no context available
- **AND** jobs without a `content_id` in their payload have `content_id: null` and `description` derived from other payload fields (e.g., "Gmail ingestion" for ingest jobs)

#### Scenario: Filter history by time range shorthand
- **WHEN** `GET /api/v1/jobs/history?since=1d` is called
- **THEN** only jobs created within the last 24 hours are returned
- **AND** supported shorthands are `1d`, `7d`, `30d`

#### Scenario: Filter history by ISO datetime
- **WHEN** `GET /api/v1/jobs/history?since=2025-01-15T00:00:00Z` is called
- **THEN** only jobs created on or after that timestamp are returned

#### Scenario: Filter history by task type
- **WHEN** `GET /api/v1/jobs/history?entrypoint=summarize_content` is called
- **THEN** only jobs with that entrypoint are returned

#### Scenario: Filter history by status
- **WHEN** `GET /api/v1/jobs/history?status=failed` is called
- **THEN** only jobs with that status are returned

#### Scenario: Combined filters
- **WHEN** `GET /api/v1/jobs/history?since=7d&status=completed&entrypoint=summarize_content` is called
- **THEN** only jobs matching ALL filters are returned

#### Scenario: Pagination
- **WHEN** `GET /api/v1/jobs/history?page=2&page_size=50` is called
- **THEN** the second page of 50 results is returned
- **AND** default page_size is 20, max is 100

#### Scenario: Invalid since parameter
- **WHEN** `GET /api/v1/jobs/history?since=invalid` is called
- **AND** `since` is not a valid ISO 8601 datetime or shorthand (`1d`, `7d`, `30d`)
- **THEN** a 400 Bad Request response is returned
- **AND** the error message indicates the supported formats

#### Scenario: Empty result set
- **WHEN** `GET /api/v1/jobs/history?since=1d&entrypoint=summarize_content` is called
- **AND** no jobs match the filter criteria
- **THEN** a 200 OK response is returned with `"data": []` and `"pagination": {"total": 0}`

#### Scenario: Jobs without content_id in payload
- **WHEN** the history includes jobs with entrypoint `ingest_content`
- **AND** these jobs do not have `content_id` in their payload
- **THEN** the response includes these jobs with `content_id: null`
- **AND** `description` is derived from the payload `source` field (e.g., "Gmail ingestion", "RSS ingestion")

### Requirement: Entrypoint Label Mapping

The system SHALL maintain a mapping from job entrypoint names to human-readable task labels.

#### Scenario: Known entrypoints have labels
- **WHEN** a job with entrypoint `summarize_content` is included in a history response
- **THEN** `task_label` SHALL be `"Summarize"`

#### Scenario: Unknown entrypoints use entrypoint as label
- **WHEN** a job has an entrypoint not in the label mapping
- **THEN** `task_label` SHALL be the raw entrypoint value (e.g., `"my_custom_task"`)

### Requirement: Task History Web UI

The system SHALL provide a web page at `/task-history` under the Management navigation group showing historical job executions in a filterable table.

#### Scenario: Table displays job history
- **WHEN** a user navigates to `/task-history`
- **THEN** a table is displayed with columns: Date/Time, Task, Content ID, Job ID, Description, Status
- **AND** rows are ordered by date/time descending (newest first)

#### Scenario: Filter by task type
- **WHEN** a user selects a task type from the filter dropdown
- **THEN** the table re-fetches data with the `entrypoint` query parameter
- **AND** all visible rows display the selected task type in the Task column

#### Scenario: Filter by status
- **WHEN** a user selects a status from the filter dropdown
- **THEN** the table re-fetches data with the `status` query parameter
- **AND** all visible rows display the selected status in the Status column

#### Scenario: Filter by time range
- **WHEN** a user selects "Last 24 hours" from the time range selector
- **THEN** the table re-fetches data with `since=1d` query parameter

#### Scenario: Pagination
- **WHEN** there are more results than fit on one page
- **THEN** pagination controls are displayed showing current page and total pages
- **AND** clicking "Next" increments the page parameter and fetches new data

#### Scenario: Empty state
- **WHEN** the query returns zero results (no jobs or all filtered out)
- **THEN** a centered message "No task history found" is displayed instead of the table
- **AND** if filters are active, the message suggests clearing filters

#### Scenario: Navigation entry
- **WHEN** a user views the sidebar navigation
- **THEN** "Task History" appears under the Management group
- **AND** clicking it navigates to `/task-history`
