## ADDED Requirements

### Requirement: Supported transitions persist exact ownership

The system SHALL persist the operation ID, claim generation, and transition phase
in the same transaction that supported operation-backed writers enter `parsing`
or `processing`. Reconciliation MUST use that pointer rather than historical job
payloads, aggregate results, parent ordering, timestamps, or query re-resolution.
Owned generations and owner versions MUST be positive, and owned phase/status
combinations MUST be limited to parsing with `parsing|failed` or processing with
`processing|failed`.

#### Scenario: Canonical URL extraction records parsing ownership

- **WHEN** URL extraction inside canonical `ingestion.execute` enters `parsing`
- **THEN** Content SHALL record that operation's ID and claim generation with phase `parsing`
- **AND** later writes SHALL require the same current claim

#### Scenario: Summary leaf records processing ownership

- **WHEN** `summarize_content` enters `processing`
- **THEN** Content SHALL record that operation's ID and claim generation with phase `processing`
- **AND** a created Summary SHALL copy the same operation provenance

#### Scenario: Initial phase ownership is acquired

- **WHEN** a current uncancelled claim starts supported work from the phase predecessor with no owner
- **THEN** one guarded compare-and-swap SHALL enter the transitional status and persist the current operation, generation, phase, and positive owner version
- **AND** later commits SHALL require exact equality with that token

#### Scenario: Retried claim renews same-operation ownership

- **WHEN** generation N left failed Content owned by an operation and generation N+1 of that same operation resumes the same phase
- **THEN** one guarded compare-and-swap MAY replace N with N+1 and advance owner version
- **AND** a different operation, phase, current generation, or pending cancellation SHALL make acquisition fail closed

#### Scenario: Canonical URL extraction failure is checkpointed

- **WHEN** canonical `ingestion.execute` resolves a URL to `webpage`, creates Content, and extraction fails
- **THEN** it SHALL attach the exact content ID, resolved route, and extraction-failure outcome as attempt-scoped resume evidence
- **AND** the operation SHALL fail retryably rather than complete with failed owned Content

#### Scenario: Canonical URL retry resumes exact Content

- **WHEN** the same operation is claimed at a newer generation with a valid canonical URL extraction checkpoint
- **THEN** it SHALL acquire parsing ownership for that exact Content row and invoke URL extraction directly
- **AND** it SHALL not reclassify the URL, create another Content row, or return through duplicate detection

#### Scenario: Canonical URL resume checkpoint is validated

- **WHEN** retry inspects an operation result as URL resume evidence
- **THEN** it SHALL require strict `IngestionResultV2`, schema version 2, command key `url`, route `webpage`, partial status/outcome, exactly one positive content ID, and an `extraction_failed` diagnostic
- **AND** that webpage Content SHALL be eligible `parsing|failed` with parsing ownership by the same operation

#### Scenario: Worker dies before attaching URL checkpoint

- **WHEN** owned URL extraction stored Content failure but the process died before attaching its operation result
- **THEN** the newer claim SHALL query exact parsing ownership by its own operation ID
- **AND** it MAY resume directly only when exactly one eligible owned Content row exists

#### Scenario: URL resume evidence is ambiguous

- **WHEN** the result is malformed or mismatched and exact owner lookup finds zero or multiple eligible Content rows
- **THEN** the operation SHALL fail closed without URL reclassification, duplicate detection, or Content mutation

#### Scenario: Legacy row has no persisted owner

- **WHEN** candidate content predates ownership tracking or was changed by an unsupported writer
- **THEN** reconciliation SHALL report `missing_operation` or `ownership_conflict`
- **AND** SHALL not infer an owner or mutate the row

#### Scenario: Unsupported writer changes content status

- **WHEN** a writer without a current matching operation claim changes Content status
- **THEN** it SHALL clear any prior transition ownership fields
- **AND** reconciliation SHALL not reuse the displaced operation pointer

#### Scenario: Unsupported writer leaves owner fields unchanged

- **WHEN** a legacy or direct writer changes Content status without advancing the guarded owner version
- **THEN** the database SHALL clear operation ID, generation, phase, and owner version before storing the row

#### Scenario: Historical terminal jobs mention the same content

- **WHEN** multiple old extraction or summary jobs mention a content ID but none matches the persisted ownership pointer
- **THEN** reconciliation SHALL ignore those associations
- **AND** SHALL not choose the newest by timestamp

### Requirement: Claim generations fence every attempt

Every queue claim SHALL atomically advance a durable claim generation. The worker
MUST require `(operation_id, claim_generation, in_progress)` for pre-handler
execution, progress, heartbeat, completion, failure, cancellation, and supported
domain commits.

#### Scenario: Superseded worker reaches handler dispatch

- **WHEN** an old worker reaches handler dispatch after the operation is reclaimed at a newer generation
- **THEN** the old worker SHALL exit after pre-handler generation revalidation
- **AND** SHALL not invoke the handler or update domain/operation state

#### Scenario: Old computation outlives its claim

- **WHEN** a handler continues computation after its operation is reclaimed
- **THEN** its final domain transaction SHALL revalidate job generation and Content ownership
- **AND** SHALL roll back without a domain or terminal write if the claim was superseded

#### Scenario: Cancellation exists before handler dispatch

- **WHEN** a current worker reaches handler dispatch after cancellation was requested
- **THEN** it SHALL checkpoint cancellation before invoking the handler
- **AND** SHALL perform no content-processing work

#### Scenario: Cancellation races ongoing computation

- **WHEN** cancellation is requested after handler dispatch but before its final domain transaction
- **THEN** claim revalidation SHALL reject the final domain write
- **AND** a typed cancelled-claim outcome SHALL checkpoint terminal cancellation without generic failure or a failure notification

#### Scenario: Terminal operation receives a late heartbeat

- **WHEN** a heartbeat or progress update arrives after the operation leaves `in_progress` or changes generation
- **THEN** the update SHALL affect no row

### Requirement: Domain projection requires matching provenance

The system SHALL use only domain output whose operation ID and claim generation
match the Content ownership token. It MUST NOT create or replace domain output
during reconciliation.

#### Scenario: Matching Summary repairs completed content

- **WHEN** `processing` or `failed` content has a matching attempt-owned Summary and no active, cancellation, or force conflict
- **THEN** apply SHALL set Content to `completed`, clear its error and ownership, and set `processed_at` from the Summary
- **AND** SHALL not modify or duplicate the Summary or operation checkpoint

#### Scenario: Mismatched old Summary exists

- **WHEN** a Summary exists but its provenance does not match the current Content owner
- **THEN** reconciliation SHALL report `output_owner_mismatch`
- **AND** SHALL not project completed state

#### Scenario: Completed parsing owner left transitional content

- **WHEN** `parsing` Content exactly matches a completed parsing owner with attempt-scoped successful extraction evidence
- **THEN** apply SHALL set `parsed`, clear its error and ownership, set `parsed_at` from operation completion, and leave `processed_at` null

#### Scenario: Completed parsing owner left failed content

- **WHEN** `failed` Content exactly matches a completed parsing owner or lacks successful extraction evidence
- **THEN** reconciliation SHALL report `completed_output_missing`
- **AND** SHALL not project parsed state or reclassify the URL

#### Scenario: Completed processing owner lacks output

- **WHEN** a completed processing owner has no matching Summary
- **THEN** reconciliation SHALL report `completed_output_missing`
- **AND** SHALL not retry or fabricate completion

#### Scenario: Protected terminal content is encountered

- **WHEN** Content is already `completed` or `filtered_out`
- **THEN** reconciliation SHALL not downgrade, retry, or otherwise mutate it

### Requirement: Retry is canonical and atomically budgeted

Apply SHALL retry only a failed exact owner through a connection-scoped canonical
retry primitive using one atomic comparison and increment against the configured
ceiling. It MUST preserve normalized input, idempotency identity, parent linkage,
and successful checkpoints.

#### Scenario: Failed exact owner remains within budget

- **WHEN** a supported failed owner is below the ceiling and has no force or output conflict
- **THEN** apply SHALL requeue the same operation and increment retry count exactly once
- **AND** SHALL not submit a new parent or reset a checkpoint

#### Scenario: Retry budget is exhausted

- **WHEN** retry count is at or above the ceiling
- **THEN** reconciliation SHALL report `retry_budget_exhausted`
- **AND** SHALL not increment, notify, or change Content

#### Scenario: Concurrent apply requests target one failure

- **WHEN** two apply requests concurrently target the same failed owner
- **THEN** at most one SHALL retry and write an action audit
- **AND** the other SHALL report revalidated state without another increment

#### Scenario: Forced operation is failed

- **WHEN** the exact owner input has `force` or `force_reprocess` enabled
- **THEN** reconciliation SHALL report `forced_reprocessing`
- **AND** SHALL not retry or project output automatically

### Requirement: Cancellation has precedence over retry

Reconciliation SHALL preserve pending or terminal cancellation and MUST NOT reset
`cancel_requested` to retry a cancelled attempt.

#### Scenario: Fresh cancellation remains worker-owned

- **WHEN** an exact active owner has cancellation requested and still holds the fence or has a fresh heartbeat
- **THEN** reconciliation SHALL report `cancellation_pending`
- **AND** SHALL not mutate it

#### Scenario: Abandoned cancellation is finalized

- **WHEN** an exact stale owner has cancellation requested and apply acquires its fence
- **THEN** apply SHALL checkpoint cancellation and restore the phase predecessor
- **AND** SHALL not retry

#### Scenario: Cancelled processing owner is restored

- **WHEN** a cancelled processing owner has no matching Summary
- **THEN** apply SHALL restore `parsed`, clear error/ownership/processed timestamp, and preserve `parsed_at`

#### Scenario: Cancelled parsing owner is restored

- **WHEN** a cancelled parsing owner remains `parsing` or `failed`
- **THEN** apply SHALL restore `pending` and clear error, ownership, `parsed_at`, and `processed_at`

### Requirement: Stale apply is locked and protocol-gated

Apply SHALL be disabled by default and SHALL mutate only current fenced worker
protocol claims. For stale work it MUST acquire the content transaction advisory
lock without waiting, then use one physical connection and lock order defined by
the design.

#### Scenario: Global apply gate is disabled

- **WHEN** a caller requests apply while server apply is disabled
- **THEN** the API SHALL return RFC 7807 status 503
- **AND** SHALL perform no reconciliation mutation

#### Scenario: Old worker protocol owns the row

- **WHEN** candidate Content points to a claim without the current fencing protocol
- **THEN** reconciliation SHALL report `incompatible_worker`
- **AND** SHALL not mutate it even if global apply is enabled

#### Scenario: Fresh active owner is observed

- **WHEN** the exact owner is queued or has heartbeat at or after the cutoff
- **THEN** reconciliation SHALL report `active_operation`
- **AND** SHALL not acquire lifecycle locks or mutate it

#### Scenario: Heartbeat refresh wins revalidation

- **WHEN** a stale candidate refreshes before apply locks and revalidates it
- **THEN** apply SHALL report `revalidation_conflict`
- **AND** SHALL leave it active

#### Scenario: Content transaction is contended

- **WHEN** apply cannot acquire the candidate content transaction lock immediately
- **THEN** it SHALL report `execution_locked`
- **AND** SHALL not treat contention as proof about which operation owns the transition

#### Scenario: Abandoned stale owner is recovered

- **WHEN** an exact stale owner uses the current protocol, has no cancellation/force conflict, is below budget, and apply acquires the content lock
- **THEN** apply SHALL atomically set Content to `failed` while retaining operation/generation/phase and advancing owner version, then fail and retry the same operation
- **AND** the action audit SHALL record transitional-to-failed Content plus in-progress-to-queued operation state
- **AND** its notification SHALL be delivered only after mutation and audit commit

#### Scenario: Retried stale parsing owner resumes

- **WHEN** stale parsing generation N was recovered to failed then the same operation is claimed at N+1
- **THEN** guarded acquisition SHALL renew parsing ownership to N+1 before extraction completes

#### Scenario: Retried stale processing owner resumes

- **WHEN** stale processing generation N was recovered to failed then the same operation is claimed at N+1
- **THEN** guarded acquisition SHALL renew processing ownership to N+1 before Summary completion

### Requirement: Scanning and reports are strictly bounded

The system SHALL scan only `parsing`, `processing`, and `failed` candidates in
ascending Content ID order with one-page limit `1..100`. It SHALL return the last
examined ID as continuation and use a closed non-sensitive report projection.

#### Scenario: Candidate page exceeds its limit

- **WHEN** more candidate rows exist than the request limit
- **THEN** reconciliation SHALL examine at most that limit
- **AND** SHALL return `next_after_content_id` from the last examined row

#### Scenario: Candidate tables contain 10,001 irrelevant rows

- **WHEN** the ownership join runs against at least 10,001 irrelevant rows
- **THEN** it SHALL use a measured index-backed bounded plan
- **AND** SHALL not scan operation payload JSON

#### Scenario: Safe report is emitted

- **WHEN** reconciliation reports a finding
- **THEN** it SHALL include only run ID, numeric identifiers, closed states/counters/actions/reasons, retry counts, and lifecycle timestamps
- **AND** SHALL omit content text, titles, URLs, raw errors, payloads, inputs, results, checkpoints, and secrets

#### Scenario: CLI pagination is requested

- **WHEN** an operator supplies `--after-content-id`
- **THEN** the CLI SHALL request exactly one bounded page from that keyset position
- **AND** SHALL not automatically traverse or apply additional pages

### Requirement: Dry-run is reconciliation-read-only

Dry-run SHALL be the default for HTTP and CLI. It MUST NOT update Content,
operations, heartbeats, reconciliation-action audits, or notifications; the
existing authenticated request audit SHALL still record mode, run ID, and counts.

#### Scenario: Default CLI invocation previews

- **WHEN** an operator invokes `aca operations reconcile-content` without `--apply`
- **THEN** it SHALL request dry-run and render deterministic ordered findings
- **AND** SHALL exit zero even when findings exist

#### Scenario: Dry-run observes a repairable row

- **WHEN** dry-run classifies a proposed repair or retry
- **THEN** domain/operation/action-audit/notification state SHALL remain unchanged
- **AND** the normal request security audit MAY record the request

### Requirement: Apply action evidence is atomic

Every applied mutation SHALL write one closed append-only action record using
the target claim generation/protocol plus explicit before/after content state,
operation state, and retry count in the same transaction. A failure SHALL roll
back mutation, notification, and audit together.

#### Scenario: Apply commits one action

- **WHEN** apply successfully projects Content, restores a predecessor, cancels, or retries
- **THEN** exactly one matching action audit SHALL commit
- **AND** the report SHALL contain observed before/after values

#### Scenario: Action audit insertion fails

- **WHEN** audit persistence fails before commit
- **THEN** Content, operation, retry count, and notification SHALL roll back
- **AND** the item SHALL report `apply_failed` without raw exception detail

#### Scenario: One item fails within a page

- **WHEN** one item transaction fails and later items remain in the bounded page
- **THEN** the failed item SHALL roll back independently
- **AND** reconciliation SHALL continue with later items and count the failure

#### Scenario: Apply is repeated

- **WHEN** apply repeats after a successful repair
- **THEN** the repaired row SHALL be absent or a no-op
- **AND** SHALL not create duplicate output, retry, checkpoint reset, or action audit

### Requirement: Canonical remote controls expose reconciliation

The authenticated operation surface SHALL expose synchronous bounded reports at
`POST /api/v1/operations/reconcile-content`, and the CLI SHALL call it through
`WorkflowApiClient` rather than connecting to the database.

#### Scenario: Valid reconciliation request completes

- **WHEN** an authorized caller submits a valid dry-run or enabled apply request
- **THEN** the API SHALL return status 200 with the canonical report

#### Scenario: Invalid or unauthorized request is rejected

- **WHEN** authentication fails or request fields exceed bounds
- **THEN** existing 401/403 or validation 422 problem behavior SHALL apply
- **AND** SHALL perform no reconciliation mutation

#### Scenario: CLI apply contains item failures

- **WHEN** an apply report contains one or more `apply_failed` items
- **THEN** CLI SHALL render the bounded report and exit nonzero
- **AND** fail-closed no-op reasons alone SHALL not cause a nonzero exit
