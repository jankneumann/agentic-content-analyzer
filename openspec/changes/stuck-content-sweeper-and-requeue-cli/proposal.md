# Change: Reconcile stuck content states

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `stuck-content-sweeper-and-requeue-cli`
> Effort: L
> Priority: 8

## Why

`Content` rows can remain in `parsing` or `processing` after the queue operation
attempt that owns that transition has failed, been cancelled, or lost its worker. Those
rows are excluded from normal selectors and become operational black holes.
Resetting them by age alone is unsafe: a live worker may still be producing the
domain result, aggregate workflow operations do not prove ownership of an
individual row, and unconstrained requeue can exceed retry budgets or duplicate
work.

Recovery therefore needs a bounded, fail-closed reconciliation surface that
uses persisted operation-attempt ownership as lifecycle authority and matching
domain provenance as completion evidence.

## What Changes

- Add durable transition ownership on `Content` plus per-claim generations on
  queue operations. Current canonical URL extraction, legacy URL extraction,
  and summarization writers record the exact operation attempt that owns each
  `parsing` or `processing` transition. A guarded same-operation acquisition
  rolls ownership from a failed claim to its retry generation.
- Make canonical URL extraction failure persist an exact-content resume
  checkpoint and fail retryably; the next claim resumes `URLExtractor` directly
  without URL reclassification or duplicate short-circuiting. If the worker dies
  before checkpoint attachment, the same operation may resume only the single
  webpage Content row proven by its persisted parsing ownership.
- Add a dry-run-by-default canonical HTTP and CLI surface at
  `POST /api/v1/operations/reconcile-content` and
  `aca operations reconcile-content`.
- Add guarded state rules for completed evidence, failed work, cancellation,
  fresh active work, stale active work, missing operations, ambiguous ownership,
  and exhausted retry budgets.
- Add persisted write-time fencing plus a content-scoped transaction advisory
  lock shared by guarded domain commits and apply, so a stale or superseded
  attempt cannot commit even if its computation outlives its earlier DB session.
- Add an atomic optional retry ceiling to canonical operation retry without
  changing the existing public manual-retry contract.
- Add an append-only per-action audit record written atomically with apply
  mutations, plus safe bounded result contracts and counters for RI-09.
- Add provenance to newly created summaries, measured indexes for the ownership
  join, and a default-off server apply gate tied to the fenced worker protocol.
- Enforce legacy safety in database triggers: every requeue resets claim protocol,
  while unsupported status changes that do not advance owner version clear the
  prior Content ownership token.
- Reconcile the older ingestion-reliability roadmap entry that still describes
  direct age-based resets before implementation begins.

## Non-Goals

- No ninth `OperationType`, reconciliation-run state machine, or parallel job
  table.
- No inference of content ownership from job payload association, ingestion
  results, summarization parent inputs, pipeline checkpoints, timestamps,
  titles, URLs, or query re-resolution.
- No automatic periodic apply in this change. Operators may invoke bounded apply
  explicitly; scheduling can be added only after RI-09 consumes stable outcomes.
- No retry of aggregate workflow parents, successful checkpoints, completed
  resources, forced reprocessing, or intentionally `filtered_out` content.
- No exposure of content text, titles, URLs, raw payloads, results, or exception
  messages in reconciliation responses or audit records.

## Approaches Considered

### 1. Persisted-owner bounded reconciliation (Recommended)

Persist the operation ID, claim generation, phase, and owner version when a
supported writer enters a transitional content state. Guard every later
content/Summary write by that ownership token, combine it with matching Summary
or extraction-success provenance, and route retry through a connection-scoped
`OperationService` primitive under an atomic budget.

**Pros**

- Preserves the durable operation model and exact row ownership.
- Supports safe dry-run, idempotent apply, and bounded concurrency.
- Avoids replaying aggregate selections or creating duplicate workflow state.

**Cons**

- Rows without a supported owner are reported for investigation rather than
  guessed into a new state.
- Requires additive ownership/provenance columns, a small audit table, worker
  claim protocol changes, and shared guarded-write code.

**Effort**: L

### 2. Age-based direct status reset

Reset `parsing` and `processing` rows to predecessor states after a timeout and
enqueue new work.

**Pros**

- Small implementation.
- Recovers some obvious stranded rows.

**Cons**

- Races live workers, bypasses canonical retry, loses cancellation intent, and
  can duplicate work.
- Cannot prove which operation owns the transition or preserve retry budgets.

**Effort**: M

### 3. Dedicated reconciliation operations

Add a new operation type and queue handler for every reconciliation run.

**Pros**

- Reuses generic operation observation and terminal history.
- Naturally supports later scheduling.

**Cons**

- Creates a ninth workflow type and an unnecessary second lifecycle around
  repairs.
- Adds more parent/child and retention semantics than the recovery action needs.

**Effort**: L

### Selected Approach

Approach 1 is selected by the approved roadmap item. It best satisfies the
underlying goal: recover stranded domain rows without weakening operation,
checkpoint, idempotency, or cancellation authority.

## Dependencies

- `ri-07` / `persisted-ingestion-run-results` (completed): typed durable results,
  bounded operation surfaces, graph locks, and retention policy.

## Impact

- **Affected specs**: `content-state-reconciliation`, `agentic-operations`,
  `job-management`, `cli-interface`
- **Affected contracts**: canonical content-workflow OpenAPI and generated
  Python/TypeScript models
- **Affected code**: content reconciliation service, operation retry controls,
  queue worker fencing, settings, API/client/CLI adapters, audit persistence
- **Database**: additive content/Summary ownership columns, queue claim
  generation/protocol columns, protocol-reset and ownership-clearing triggers,
  reconciliation-audit table, and measured indexes; no content or operation
  lifecycle replacement
- **Security**: existing `/api/v1` authentication and audit middleware remain
  mandatory; responses use a closed non-sensitive projection
- **Related roadmap**: the older `ingestion-reliability` item with the same
  change ID is superseded by this plan and must not run its direct-reset design

## Acceptance Outcomes

- Tested rules identify the exact persisted operation attempt owning each
  supported transition and enforce bounded retry without historical inference.
- Dry-run lists affected content and operation identifiers in deterministic,
  bounded order without domain/operation mutation, notification, or
  reconciliation-action audit writes; the existing request security audit remains.
- Apply is idempotent, concurrency-safe, and auditable and uses canonical
  operation retry whenever retry can restore state.
- Repeated or concurrent reconciliation cannot duplicate content or summaries,
  reset successful checkpoints, override cancellation, or exceed retry budgets.
- Superseded workers cannot commit domain or terminal operation writes for a
  newer claim generation.
- Failed canonical URL extraction retries the same owned Content row and cannot
  falsely complete through aggregate duplicate detection or route drift.
- Fresh active work, ambiguous ownership, missing/retained-away operations, and
  completed operations without required domain output fail closed with stable
  reason codes.
