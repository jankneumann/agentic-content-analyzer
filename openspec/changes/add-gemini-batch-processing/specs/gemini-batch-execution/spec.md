# Spec Delta: Gemini Batch Execution

## ADDED Requirements

### Requirement: Opt-in per-step batch execution

The system SHALL allow each Gemini-backed pipeline step to run in either `sync`
or `batch` execution mode, configured via `batch_execution.<step>` in
`settings/models.yaml` and globally gated by `batch.enabled`
(`GEMINI_BATCH_ENABLED`). The default for every step SHALL be `sync`, and the
default for `batch.enabled` SHALL be `false`.

#### Scenario: Batch globally disabled preserves synchronous behavior

- **WHEN** `batch.enabled` is `false`
- **THEN** every Gemini step SHALL call `LLMRouter.generate*` synchronously
  exactly as before
- **AND** no `batch_requests` or `batch_jobs` rows SHALL be written

#### Scenario: A step enabled for batch defers its LLM call

- **GIVEN** `batch.enabled` is `true` and `batch_execution.content_filtering` is `batch`
- **WHEN** the content filter evaluates a newly persisted `Content` row
- **THEN** the system SHALL persist a `batch_requests` row with `status=pending`,
  `model_step=content_filtering`, `target_table=contents`, and `target_id` of that row
- **AND** the system SHALL NOT call Gemini synchronously for that item

#### Scenario: A step left in sync mode is unaffected by a peer in batch mode

- **GIVEN** `batch_execution.content_filtering=batch` and `batch_execution.caption_proofreading=sync`
- **WHEN** both steps run during ingestion
- **THEN** caption proofreading SHALL execute synchronously
- **AND** content filtering SHALL be deferred to a batch request

### Requirement: Batch submission and flush thresholds

The `batch_submit` worker entrypoint SHALL group `pending` requests by
`(model_step, model_id)` and submit a Gemini batch job when a group reaches
`batch.flush_max_requests` items OR its oldest pending request exceeds
`batch.flush_max_wait_minutes`. Submission SHALL record a `batch_jobs` row and
set the submitted requests' `batch_job_id` and `status=submitted`.

#### Scenario: Group flushes on size threshold

- **GIVEN** `batch.flush_max_requests` is 50 and 50 `pending` requests exist for `(content_filtering, gemini-3.1-flash-lite)`
- **WHEN** `batch_submit` runs
- **THEN** the system SHALL call `LLMRouter.submit_batch` once with those 50 requests
- **AND** create one `batch_jobs` row with `request_count=50` and `state=running`
- **AND** mark the 50 requests `status=submitted` with that `batch_job_id`

#### Scenario: Group flushes on age threshold below size

- **GIVEN** 3 `pending` requests, the oldest created `flush_max_wait_minutes + 1` ago
- **WHEN** `batch_submit` runs
- **THEN** the system SHALL submit those 3 requests rather than wait for the size threshold

#### Scenario: Concurrent workers do not double-submit

- **WHEN** two workers run `batch_submit` simultaneously
- **THEN** pending-request selection SHALL use `FOR UPDATE SKIP LOCKED`
- **AND** each pending request SHALL be included in at most one batch job

### Requirement: Result reconciliation to target rows

The `batch_poll` worker entrypoint SHALL poll non-terminal `batch_jobs` and, on
`JOB_STATE_SUCCEEDED`, match each result by `request_key` to its `batch_requests`
row, apply the registered `ResultHandler` for that `model_step` to the target
row, and mark the request `status=succeeded`.

#### Scenario: Successful job updates the originating content row

- **GIVEN** a `succeeded` Gemini batch job for content-filtering requests
- **WHEN** `batch_poll` reconciles a result whose `request_key` maps to `Content` X
- **THEN** the content-filtering result handler SHALL write `filter_decision`,
  `filter_score`, and the resulting `status` to `Content` X
- **AND** mark the `batch_requests` row `status=succeeded` with `completed_at` set
- **AND** the reconciled outcome SHALL equal the synchronous filter outcome for the same input

### Requirement: Failure and expiry fallback

The system SHALL detect batch jobs that reach `JOB_STATE_FAILED` or
`JOB_STATE_EXPIRED` — and individual results that are missing or errored — mark
the affected requests `status=fallback`, and re-execute them through the
synchronous `LLMRouter` path, so that no item is left permanently unprocessed.

#### Scenario: Expired job falls back to synchronous execution

- **GIVEN** a `batch_jobs` row that polls as `JOB_STATE_EXPIRED`
- **WHEN** `batch_poll` processes it
- **THEN** its still-incomplete `batch_requests` SHALL be marked `status=fallback`
- **AND** each SHALL be re-run synchronously and its target row updated
- **AND** the `batch_jobs` row SHALL be marked `state=expired` with `error` set

### Requirement: Downstream gating for output-blocking steps

The system SHALL persist items awaiting a batch result for output-blocking steps
(e.g. `youtube_processing`) with `ContentStatus.PENDING_BATCH`, and the
summarization and digest-creation stages SHALL exclude `PENDING_BATCH` rows until
reconciliation flips them to `PARSED`.

#### Scenario: Pending-batch YouTube item is excluded from the digest

- **GIVEN** a YouTube `Content` row with `status=PENDING_BATCH`
- **WHEN** the daily digest stage selects eligible content
- **THEN** that row SHALL NOT be included
- **AND** after `batch_poll` reconciles it to `status=PARSED`, a subsequent digest run SHALL include it

#### Scenario: Advisory step requires no pending-batch status

- **GIVEN** `content_filtering` runs in batch mode (post-persist, advisory)
- **WHEN** its request is deferred
- **THEN** the `Content` row SHALL retain its normal ingestion status (not `PENDING_BATCH`)
- **AND** remain eligible for downstream stages while unfiltered

### Requirement: Batch cost-savings reporting

The system SHALL provide `aca evaluate batch-savings` which estimates, per
Gemini step, the standard-tier and 50%-batch-tier cost using model pricing,
per-step token estimates, and actual `contents` volumes, in both a one-time
backfill and a steady-state monthly projection. It SHALL support `--json` and
SHALL NOT mutate any data.

#### Scenario: Cost report prints per-step standard vs batch cost

- **WHEN** a user runs `aca evaluate batch-savings`
- **THEN** the system SHALL print, for each Gemini step, its model, standard
  cost, and batch (half) cost
- **AND** SHALL NOT write to the database
- **AND** `--json` SHALL emit the same figures as a machine-readable object
