# Design: Operation-backed content reconciliation

## Context

`Content.status` currently has neither a transition timestamp nor a durable owner.
Historical jobs can mention a content ID without owning its current transition,
and the canonical URL path performs extraction inside `ingestion.execute` rather
than an `extract_url_content` leaf. Payload association, timestamps, aggregate
results, and parent ordering therefore cannot safely select a repair operation.

Workers heartbeat every 15 seconds, but queue claims have no generation token and
canonical retry has no ceiling. Safe reconciliation requires persisted transition
ownership plus write-time attempt validation; short transaction advisory locks
serialize commits but are not the authority.

## Goals

- Persist the exact operation attempt and phase owning supported transitions.
- Reject domain, heartbeat, and terminal writes from superseded claims.
- Produce a deterministic bounded dry-run report.
- Repair only states proven by current ownership and matching domain output.
- Reuse the same operation row under a finite atomic reconciliation budget.
- Commit one safe action-audit record with every apply mutation.

## Non-Goals

- Infer ownership for legacy rows that predate ownership columns.
- Reconcile unsupported direct/background content writers.
- Add periodic automatic apply or a ninth operation type.
- Re-run aggregate selections, retry parents, or perform forced reprocessing.
- Change the compatibility behavior of the public manual retry endpoint.

## Decisions

### D1: Transition ownership is persisted at the status write

`Content` gains nullable `status_operation_id`, `status_claim_generation`,
`status_operation_phase` (`parsing|processing`), and `status_owner_version`.
All four are null or non-null together. Owned generations and versions are
strictly positive; parsing ownership is valid only for `parsing|failed`, and
processing ownership only for `processing|failed`. A supported operation context
writes them in the same transaction that enters `parsing` or `processing`:

- canonical URL extraction running inside `ingestion.execute` owns `parsing`;
- retained `extract_url_content` owns `parsing`;
- `summarize_content` owns `processing`.

The context flows through `asyncio.to_thread` into `URLExtractor` and
`ContentSummarizer`. The first phase acquisition is a compare-and-swap that
requires the current in-progress job claim, no pending cancellation, and either
the phase predecessor with no owner or `failed` with the same operation and an
older generation. It writes the new generation and advances owner version.
Subsequent progress/failure/output commits require exact owner equality and
advance owner version when status changes. This is the only permitted ownership
handoff from claim N to N+1.

A database trigger clears all ownership fields whenever status changes without
an owner-version advance; an ORM parity hook provides the same behavior in local
test backends. Existing unsupported writers therefore cannot leave a plausible
old token. Stable successful/cancelled projection clears ownership; failed
supported work retains it for retry.
Ownership columns intentionally have no foreign key to retained operations so
missing-operation evidence survives.

Alternative: select the newest job whose payload mentions `content_id`. Rejected
because association and chronology do not prove ownership after reprocessing or
unsupported writes.

### D2: Every queue claim has a durable generation

`pgqueuer_jobs.claim_generation` increments in a database trigger whenever status
changes from `queued` to `in_progress`, including claims made by old workers.
Every transition back to `queued` resets `claim_protocol_version` to 1 in a
database trigger, including legacy retry/defer SQL. A current worker claim
explicitly writes protocol 2; an old claim leaves the reset value at 1. This
prevents a row previously handled by a new worker from retaining a false
compatibility marker when an old worker later claims it. The worker carries
`(job_id, claim_generation)` through execution.
Pre-handler validation, progress, heartbeat, completion, failure, cancellation,
and every supported domain commit require the row to remain `in_progress` at
that generation.

A superseded worker therefore exits at pre-handler revalidation, and a handler
already computing cannot commit after retry or a newer claim invalidates its
generation.

Alternative: use retry count as a claim token. Rejected because not every future
reclaim path is guaranteed to increment retry count, while every claim can
increment a dedicated generation.

Canonical URL extraction persists an attempt-scoped resume checkpoint in the
operation result: resolved `webpage` route, exact content ID, and
`extraction_failed` outcome. The handler attaches that checkpoint and raises a
retryable workflow error, so Content failure cannot leave a completed operation.
Because the synchronous Content transaction and async operation result cannot be
atomic, recovery also handles process loss between them. On the next generation,
the handler accepts a checkpoint only when strict `IngestionResultV2` validation
proves `schema_version=2`, `command_key=url`, `resolved_route=webpage`,
`status=partial`, `outcome=partial`, exactly one positive content ID, and an
`extraction_failed` diagnostic; the operation row and Content owner must be the
same operation with phase `parsing` and source type `webpage`. If the result is absent or invalid, the
handler instead queries by exact persisted `(status_operation_id, phase)` and
continues only when exactly one eligible `parsing|failed` Content row exists.
Zero or multiple rows fail closed. It then acquires that exact owned row and
calls `URLExtractor` directly. It does not reclassify the URL or pass through the
aggregate duplicate short-circuit. A successful direct resume replaces the
checkpoint with canonical success evidence before the operation completes.

### D3: Domain completion evidence is attempt-scoped

New Summaries store `operation_id` and `operation_claim_generation`. A Summary
repairs `processing|failed -> completed` only when its provenance matches the
Content ownership token. The final summary insert and content completion update
run in one transaction after locking Content and revalidating both the job claim
and content ownership. Existing mismatched or unowned summaries never authorize
repair.

A completed parsing owner can repair `parsing -> parsed`; it clears the stale
error, sets `parsed_at` from operation completion, leaves `processed_at` null, and
clears ownership. A completed processing owner without a matching Summary is an
unresolved invariant violation.

A completed parsing owner in `failed` is also an invariant violation and is
reported without mutation: only attempt-scoped successful extraction evidence
may authorize `parsing -> parsed`, while fenced handlers turn extraction failure
into a failed/retryable operation.

Alternative: accept any Summary for the content. Rejected because a prior Summary
may be stale after forced or direct content reprocessing.

### D4: Cancellation and force take precedence

Immediately before handler dispatch, a worker revalidates its generation and
checks `cancel_requested`. It checkpoints cancellation and does no domain work
when cancellation is already pending. Guarded domain commits also require
`cancel_requested = false`, so cancellation racing after dispatch prevents the
final domain write. Guard rejection returns a typed `ClaimCancelled` or
`ClaimSuperseded` outcome. The worker checkpoints `ClaimCancelled` as terminal
`cancelled` without calling generic failure or emitting a failure notification;
`ClaimSuperseded` exits without a stale terminal write.

Reconciliation order checks fresh/current ownership, cancellation, and force
before output repair or retry. A stale cancellation with a free fence becomes
cancelled and restores its predecessor. A terminal cancelled processing owner
restores `parsed`, clears error and `processed_at`, and clears ownership. A
cancelled parsing owner restores `pending`, clears error plus parse/process
timestamps, and clears ownership. Reconciliation never retries a payload with
`force` or `force_reprocess`; it reports `forced_reprocessing`.

For an abandoned stale parsing or processing owner, the single apply transaction
first changes Content to `failed` while retaining operation/generation/phase and
advancing owner version, then fails and requeues the same operation. The action
audit records the transitional-to-failed Content change plus in-progress-to-
queued operation change. This puts the row into the only state from which the
next generation may renew same-operation ownership.

Alternative: let retry preserve an existing force flag. Rejected because recovery
must not delete or replace successful domain output.

### D5: Transaction locking serializes; tokens fence writes

Every supported domain commit and apply transaction uses the same namespaced
PostgreSQL transaction advisory lock on `content_id`. Apply uses
`pg_try_advisory_xact_lock` and reports contention without waiting. Long-running
network/LLM computation does not hold a database connection; its final
transaction takes the lock, locks Content, and revalidates job generation plus
Content ownership before any write.

The durable predicates remain mandatory while the lock is held. A superseded
handler may finish computation, but its final transaction cannot insert a
Summary or change Content. Generation predicates independently prevent late
heartbeat and terminal job writes.

Alternative: hold a session lock across long computation. Rejected because it
consumes a connection, fails open on session loss, and still needs durable tokens.

### D6: Apply uses one physical connection and one lock order

One asyncpg connection owns the content transaction lock, outer transaction, graph
transaction lock, row locks, retry update, action-audit insert, and transactional
`pg_notify`. Lock order is:

1. content transaction advisory lock;
2. root operation graph transaction advisory lock;
3. root job row;
4. target job row;
5. content row;
6. matching Summary row when required;
7. action-audit insert.

`OperationService.retry` is refactored around a connection-scoped locked primitive.
The public method acquires its current graph/root locks then calls the primitive;
reconciliation calls the same primitive after acquiring the documented locks.
It never opens a nested mutation connection.

Alternative: call the opaque public retry method inside apply. Rejected because a
second connection can block on apply's row locks and separate notify from audit.

### D7: Reconciliation retry has an atomic ceiling

`CONTENT_RECONCILIATION_MAX_RETRIES` defaults to 3 (`0..20`). The locked retry
update includes `retry_count < ceiling`; two apply calls cannot both increment.
The public manual retry route passes no ceiling and retains compatibility.

Other policy settings are:

- `CONTENT_RECONCILIATION_STALE_SECONDS=3600` (`60..604800`, at least four
  15-second heartbeat intervals);
- `CONTENT_RECONCILIATION_BATCH_SIZE=50` (`1..100`);
- `CONTENT_RECONCILIATION_LOCK_TIMEOUT_MS=250` (`1..5000`);
- `CONTENT_RECONCILIATION_STATEMENT_TIMEOUT_MS=5000` (`100..30000`, not less
  than lock timeout);
- `CONTENT_RECONCILIATION_APPLY_ENABLED=false` by default.

### D8: Dry-run and apply use separate persistence paths

Dry-run performs bounded reconciliation SELECTs only. It does not call helpers
with read-side mutations and never opens an action-audit or mutation transaction.
The existing HTTP request security audit still records the authenticated request
with mode, run ID, and bounded counters.

Apply re-reads and reclassifies each item under locks. One item failure rolls back
that item and its audit row, reports `apply_failed`, and continues to later items.
Revalidation changes report `revalidation_conflict` without mutation.

Alternative: preview by rolling back apply logic. Rejected because notifications,
locks, and helper side effects are not a pure read contract.

### D9: Action audit is closed append-only evidence

`content_reconciliation_actions` contains copied numeric IDs without destructive
foreign keys, `run_id`, claim generation/protocol, before/after content and
operation states, before/after retry counts, action, reason, and timestamp.
Database CHECK constraints enforce
closed enums, positive IDs, paired nullable operation fields, and nonnegative
counts. Application code exposes no update/delete path. One row is inserted in
the same transaction as each applied mutation; no row is written for dry-run or
no-op findings.

The report uses the same explicit before/after projection. Proposed dry-run
values are represented as `proposed_*`; apply returns observed before/after values.

### D10: Candidate scanning joins persisted ownership

Candidates are exactly `parsing`, `processing`, and `failed` Content rows plus
rows with a matching attempt-owned Summary that need projection repair. Scans use
ascending `Content.id`, `limit <= 100`, and return the last examined ID as
`next_after_content_id`. Ownership joins `Content.status_operation_id` to the job
primary key and validates generation/phase; it never scans payload JSON.

A partial composite Content index and Summary provenance index are retained only
when `EXPLAIN` over more than 10,000 irrelevant rows demonstrates the intended
bounded plan. Legacy/missing operations report `missing_operation`; generation or
phase mismatch reports `ownership_conflict`.

### D11: Apply is protocol-gated during rollout

Server-side apply is disabled by default. When enabled, an item is mutable only
if its owning claim has the current fenced `claim_protocol_version`; old workers
write version 1/default and their rows report `incompatible_worker`. This per-claim
check remains even after operators drain old workers. The endpoint returns RFC
7807 `409` when apply is globally disabled — a conflict with standing server
policy, not a transient outage a retry would clear, and never a 5xx.

## Reconciliation Matrix

The classifier order is protected state -> exact owner/generation/phase -> current
active/cancellation/force checks -> matching output -> terminal action.

| Exact evidence | Owner state | Action | Reason |
|---|---|---|---|
| matching attempt-owned Summary; no active/force conflict | terminal processing owner | set `completed`; clear owner/error; set `processed_at` from Summary | `summary_exists` |
| `parsing` with matching parsing owner plus successful extraction evidence | `completed` | set `parsed`; clear owner/error; set `parsed_at` from operation completion | `extraction_completed` |
| `failed` with matching parsing owner | `completed` | none | `completed_output_missing` |
| processing owner; no matching Summary | `completed` | none | `completed_output_missing` |
| exact current owner | `queued` or fresh `in_progress` | none | `active_operation` |
| exact current owner | `in_progress` with cancellation requested; fence held/fresh | none | `cancellation_pending` |
| exact current owner | stale `in_progress`; content transaction lock contended | none | `execution_locked` |
| exact current owner | stale `in_progress`; lock acquired; cancellation requested | cancel then restore predecessor | `cancellation_requested` |
| exact current owner | stale `in_progress`; lock acquired; under budget | set Content `failed` retaining owner and advancing version; fail then retry same operation | `stale_operation` |
| exact current owner | `failed`; under budget | retry same row | `failed_operation` |
| exact current owner | `failed`; at budget | none | `retry_budget_exhausted` |
| exact current owner | `failed|cancelled`; force flag true | none | `forced_reprocessing` |
| exact processing owner; no Summary | `cancelled` | restore `parsed`; clear owner/error/processed_at | `summarization_cancelled` |
| exact parsing owner | `cancelled` | restore `pending`; clear owner/error/timestamps | `extraction_cancelled` |
| candidate Content | owner operation retained away | none | `missing_operation` |
| candidate Content | pointer/generation/phase mismatch | none | `ownership_conflict` |
| candidate Content | old claim protocol | none | `incompatible_worker` |
| `completed|filtered_out` | any | excluded | protected state |

## API and CLI Contract

`POST /api/v1/operations/reconcile-content` accepts:

- `apply: boolean = false`;
- optional `limit: integer, 1..100`; omission uses the configured batch default,
  while an explicit value cannot exceed the configured server batch limit;
- `after_content_id: positive bigint | null`.

It returns synchronous `200` with one bounded report. Existing authentication
provides `401/403`; invalid input returns `422`; disabled apply returns RFC 7807
`503`. Per-item no-ops and conflicts remain `200`. The CLI processes one page per
invocation, exposes `--limit` and `--after-content-id`, and never auto-traverses.
Dry-run exits zero for findings. Apply exits nonzero only for request failure or
one or more `apply_failed` items; active, locked, exhausted, and other fail-closed
findings remain inspectable no-ops.

## Data Changes

1. `pgqueuer_jobs`: nonnegative `claim_generation BIGINT NOT NULL DEFAULT 0`,
   `claim_protocol_version SMALLINT NOT NULL DEFAULT 1`, a queued-to-active
   generation trigger, and a database protocol-reset trigger on every requeue.
2. `contents`: nullable owner ID/generation/phase/version plus compatible-phase
   CHECK, unchanged-owner clearing trigger, and measured partial candidate index;
   no operation FK.
3. `summaries`: nullable paired operation ID/generation provenance plus CHECK and
   measured lookup index; no operation FK.
4. `content_reconciliation_actions`: closed immutable snapshot fields and indexes
   on `(run_id,id)` and `(content_id,created_at DESC)`; no destructive FK.
5. Queue bootstrap and canonical DB contract mirror the additive Alembic change.
   Downgrade removes indexes/table/columns only after apply is disabled.

## Failure Handling

- Content transaction-lock contention is a reported no-op.
- Attempt/protocol/ownership mismatch fails closed.
- Mutation plus audit plus notification commit or roll back together.
- One item failure does not prevent later items in the bounded page.
- No raw exception text is returned or audited.

## Security and Privacy

- Existing `/api/v1` authentication applies.
- Closed request/report/audit schemas expose no title, URL, content, raw error,
  payload, input, result, checkpoint, or secret.
- Apply is both configuration-gated and claim-protocol-gated.
- Server settings and page bounds prevent request-controlled unbounded work.

## Observability

Closed counters are `scanned`, `reported`, `applied`, `retried`, `projected`,
`restored`, `active`, `locked`, `missing`, `conflicted`, `cancelled`, `forced`,
`exhausted`, `incompatible`, and `failed`. Stable action/reason codes plus the
audit table are the RI-09 integration boundary; external sinks remain deferred.

## Rollout

1. Reconcile the duplicate roadmap item in the planning commit.
2. Deploy additive migration plus claim-generation-aware workers while apply
   remains disabled.
3. Drain/restart pre-protocol workers and verify new claims record the current
   protocol; per-item protocol checks remain mandatory.
4. Deploy API/client/CLI and validate staging dry-run.
5. Enable apply explicitly in staging, then production after worker verification.
6. Rollback first disables apply, then rolls back application code; additive
   columns/table remain harmless until a later migration.

## Risks and Mitigations

- **Legacy rows lack ownership**: report only; never backfill by timestamp/history.
- **Old computation outlives its claim**: final domain/job writes revalidate
  durable job generation and Content ownership in one transaction.
- **Old worker remains**: global default-off gate plus per-claim protocol rejection.
- **Operation retention removes owner**: copied IDs remain visible; no mutation.
- **Audit growth**: one row only per applied mutation; retention deferred until
  evidence requirements are known.

## Open Questions

None. Automatic scheduling and out-of-band delivery belong to later roadmap work.
