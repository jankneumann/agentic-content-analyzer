# pipeline Specification

## Purpose
TBD - created by archiving change add-parallel-job-queue. Update Purpose after archive.
## Requirements
### Requirement: Parallel Source Ingestion

The pipeline SHALL execute all ingestion sources (Gmail, RSS, YouTube, Podcast, Substack) concurrently by calling shared orchestrator functions from `src/ingestion/orchestrator.py` via `asyncio.to_thread()`.

#### Scenario: All sources succeed
- **WHEN** the `aca pipeline daily` command is executed
- **THEN** all ingestion sources are fetched concurrently via `asyncio.gather()` calling orchestrator functions
- **AND** total ingestion time equals the slowest source (not sum of all)
- **AND** each source creates an OTel span named `ingestion.{source_name}`

#### Scenario: Partial source failure
- **WHEN** one source fails during parallel ingestion (e.g., Gmail API returns 401)
- **THEN** other independent sources complete successfully
- **AND** the failed source creates an OTel span with `status=ERROR` including: source_name, error_type, error_message
- **AND** the pipeline continues to summarization if at least 1 source returned content
- **AND** the pipeline exits with code 0 (partial failure is not fatal)

#### Scenario: Source API rate limit
- **WHEN** a source API returns HTTP 429 (rate limited) during parallel ingestion
- **THEN** the source retries with exponential backoff (1s, 2s, 4s, max 3 retries)
- **AND** if all retries fail, the source is marked failed and other sources continue

#### Scenario: Pipeline and task worker use same orchestrator
- **WHEN** the pipeline ingests from a source
- **AND** the task worker processes an `ingest_content` job for the same source
- **THEN** both SHALL call the same orchestrator function from `src/ingestion/orchestrator.py`
- **AND** no ingestion service wiring SHALL exist outside the orchestrator module

### Requirement: Queue-Based Summarization

The pipeline SHALL enqueue content items for summarization and process them via a worker pool.

#### Scenario: Batch summarization via queue
- **WHEN** `aca summarize pending` is executed
- **THEN** pending content IDs are enqueued to `pgqueuer_jobs` with entrypoint `summarize_content`
- **AND** each job payload MUST include `{"content_id": int}`
- **AND** workers process items concurrently up to the concurrency limit
- **AND** progress is tracked in `pgqueuer_jobs.payload.progress` (0-100)

#### Scenario: Worker concurrency limit
- **WHEN** a worker pool starts with `--concurrency 5`
- **THEN** the number of jobs in `in_progress` status is <= 5 at all times
- **AND** when the 6th job is enqueued, it remains in `queued` status until a running job completes

#### Scenario: LLM rate limit during summarization
- **WHEN** the Anthropic API returns HTTP 429 during summarization
- **THEN** the worker retries with exponential backoff (5s, 10s, 20s, max 3 retries)
- **AND** if all retries fail, the job is marked `failed` with error `rate_limit_exceeded`
- **AND** the worker continues processing other jobs

#### Scenario: Idempotent job enqueueing
- **WHEN** `aca summarize pending` is called while jobs for the same content_ids are already queued
- **THEN** duplicate jobs are NOT created
- **AND** only content_ids not already in `queued` or `in_progress` status are enqueued

### Requirement: Pipeline Progress Tracking

The pipeline SHALL emit structured progress events for each stage.

#### Scenario: Stage progress via OTel spans
- **WHEN** the `aca pipeline daily` command is executed
- **THEN** each stage creates an OTel span named `pipeline.{stage}` (e.g., `pipeline.ingestion`, `pipeline.summarization`, `pipeline.digest`)
- **AND** each span MUST include attributes: `status` (success|failure|partial), `item_count` (integer)
- **AND** failure spans MUST include `error_message` attribute

#### Scenario: Resumable pipeline after crash
- **WHEN** the pipeline process is interrupted mid-summarization (SIGTERM or crash)
- **AND** the pipeline command is restarted
- **THEN** only jobs with status `queued` or `in_progress` (updated_at < 1 hour ago) are processed
- **AND** jobs with status `completed` are skipped
- **AND** stale `in_progress` jobs (updated_at >= 1 hour ago) are marked `failed` with error `stale_timeout`

#### Scenario: Pipeline timeout
- **WHEN** the pipeline has been running for more than `PIPELINE_TIMEOUT` (default: 2 hours)
- **THEN** the pipeline logs a warning and continues (does not force-terminate)
- **AND** individual job timeouts are handled separately by workers
