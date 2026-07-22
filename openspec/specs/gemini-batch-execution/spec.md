# gemini-batch-execution Specification

## Purpose
TBD - created by archiving change add-gemini-batch-processing. Update Purpose after archive.
## Requirements
### Requirement: Safe-default batch configuration

The system SHALL expose a global Gemini batch switch and per-step `sync|batch`
execution modes. The global switch SHALL default false and every step SHALL
default to `sync`.

#### Scenario: Disabled batching writes nothing

- **WHEN** global batch execution is disabled
- **THEN** `is_batch_enabled` SHALL return false for every step
- **AND** collection SHALL write no `batch_requests` or `batch_jobs` rows
- **AND** existing Gemini call paths SHALL remain unchanged

### Requirement: Durable request collection

The collector SHALL persist unique, credential-free request payloads for integer
`Content` targets and SHALL prevent duplicate active requests for the same
`(model_step, content_id)`.

#### Scenario: Enabled step collects one request

- **GIVEN** batching is globally enabled and a step is configured `batch`
- **WHEN** the collector receives a request for a content row
- **THEN** it SHALL persist one `pending` request with a stable unique key
- **AND** a repeated active collection for the same step and target SHALL reuse
  or reject the existing request rather than create a second active request

### Requirement: Concurrency-safe batch submission

The submitter SHALL group pending requests by `(model_step, model_id)`, flush a
group on configured count or age thresholds, and prevent concurrent workers from
claiming the same request by using `FOR UPDATE SKIP LOCKED` and explicit claim
states.

#### Scenario: Group flushes on count

- **GIVEN** a group has reached `flush_max_requests`
- **WHEN** submission runs
- **THEN** it SHALL create one local job, submit the claimed requests once in
  that execution, record the provider job name, and mark them submitted

#### Scenario: Group flushes on age

- **GIVEN** a non-empty group whose oldest request exceeds
  `flush_max_wait_minutes`
- **WHEN** submission runs
- **THEN** it SHALL submit the group below the count threshold

#### Scenario: Oversized inline group is not submitted

- **GIVEN** serialized inline requests meet or exceed `inline_max_bytes`
- **WHEN** submission runs
- **THEN** no provider create call SHALL occur
- **AND** requests SHALL remain recoverable and the error SHALL be observable

### Requirement: Metadata-keyed Gemini provider adapter

The Gemini adapter SHALL use the asynchronous SDK, correlate inline responses by
echoed `request_key` metadata, normalize provider states, and SHALL NOT silently
pair results by list position.

#### Scenario: Successful inline job returns keyed results

- **WHEN** a succeeded provider job returns reordered inline responses
- **THEN** each response SHALL map to its echoed request key

#### Scenario: Duplicate or missing metadata is rejected

- **WHEN** provider output omits a key or repeats a key
- **THEN** the affected output SHALL be reported as an error
- **AND** it SHALL NOT be applied to an arbitrary target

### Requirement: Idempotent reconciliation and bounded fallback

Polling SHALL apply each successful result at most once. Failed, cancelled, or
expired jobs and missing or errored individual results SHALL enter synchronous
fallback. Fallback attempts SHALL be bounded and exhaustion SHALL produce a
terminal failed request with a persisted error.

#### Scenario: Duplicate poll is idempotent

- **GIVEN** a request is already succeeded
- **WHEN** the same terminal provider job is polled again
- **THEN** its handler SHALL NOT run a second time

#### Scenario: Partial result falls back only the affected request

- **GIVEN** a succeeded job with one successful result and one missing result
- **WHEN** reconciliation runs
- **THEN** the successful request SHALL be applied and marked succeeded
- **AND** only the missing request SHALL enter bounded fallback

#### Scenario: Terminal provider failure falls back

- **WHEN** a job reaches failed, cancelled, or expired
- **THEN** every incomplete request SHALL enter bounded fallback
- **AND** the local job SHALL preserve the normalized terminal state and error

#### Scenario: Fallback exhaustion is terminal

- **GIVEN** synchronous fallback has reached `fallback_max_attempts`
- **WHEN** it fails again or remains incomplete
- **THEN** the request SHALL be marked failed with an actionable error

### Requirement: Batch operations are observable

The system SHALL run periodic maintenance under a PostgreSQL advisory lock so
only one worker submits and polls per tick. It SHALL expose read-only
`aca batch status`. JSON output SHALL use the canonical root `--json` mode.

#### Scenario: Concurrent worker ticks elect one maintainer

- **WHEN** multiple workers reach the maintenance interval concurrently
- **THEN** at most one SHALL hold the batch-maintenance advisory lock
- **AND** workers that do not acquire it SHALL skip without error

#### Scenario: Status is read-only

- **WHEN** an operator runs `aca batch status`
- **THEN** the command SHALL report counts and recent jobs without mutating them

### Requirement: Batch savings report is reproducible and read-only

`aca evaluate batch-savings` SHALL report standard and 50%-batch estimates from
model pricing, exported per-step token assumptions, and database counts. It
SHALL expose its assumptions, support root `--json`, and write no data.

#### Scenario: JSON report includes assumptions

- **WHEN** an operator runs `aca --json evaluate batch-savings`
- **THEN** output SHALL include per-step counts, token assumptions, standard
  cost, batch cost, and savings
- **AND** the command SHALL not mutate the database
