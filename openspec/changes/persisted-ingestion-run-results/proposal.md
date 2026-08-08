# Change: Reconcile persisted ingestion results

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `persisted-ingestion-run-results`
> Effort: L, decomposed into M/S work packages
> Priority: 7

## Why

The canonical workflow refactor already made `pgqueuer_jobs` the durable source
of truth for workflow state, parent-child relationships, checkpoints, retries,
idempotency, results, resources, and terminal problems. The remaining
reliability gap is narrower:

- `IngestionResponse` knows whether work was `ok`, `partial`, or `error`, but
  the queue result drops that status, skipped/failed counts, and structured
  errors. A partial source therefore appears to be a clean completed operation.
- API and CLI operation listings cannot query by source outcome or pipeline
  parent, so per-source history is not an operator-facing capability.
- result diagnostics and public history rows have no size contract;
  `content_ids` are duplicated inside `details`.
- the existing 30-day cleanup helper is not scheduled and can detach retained
  failed children from a deleted completed parent.

This change closes those gaps without introducing `IngestionRun` or
`SourceRunResult` tables or a second workflow state machine.

## What Changes

- Preserve a versioned, typed ingestion result on the existing operation:
  source-domain status, derived outcome, ingested/skipped/failed counts,
  bounded structured diagnostics, exact non-duplicated content provenance,
  and bounded configured-source outcomes identified by opaque source keys.
- Define one classifier for `success`, `zero_items`, `partial`, `failed`,
  `cancelled`, and legacy `unknown` outcomes. Operation lifecycle remains
  distinct from source outcome.
- Add a compact `GET /api/v1/ingestions` history projection derived from
  `pgqueuer_jobs`, with fixed-filter keyset pagination and filters for command,
  opaque configured-source key, outcome, lifecycle status, pipeline parent,
  and creation window.
- Narrow generic operation list rows to wire-compatible bounded summaries; full result,
  checkpoint, and problem detail remain available only from exact-operation
  reads.
- Add `aca ingest history` with the same filters. A pipeline explicitly allowed
  to continue after partial source work remains successful but prints a warning;
  `--fail-on-source-error` continues to produce a failed operation and exit 1.
- Make terminal operation retention automatic, configurable, graph-aware, and
  safe for active or retryable work. Parent-child identity remains intact for
  the whole retained history window.
- Reconcile the stale legacy job-history requirement with the canonical
  operation-derived surface and update the durable workflow contracts.

## Scope Boundaries

In scope:

- typed ingestion and pipeline result projections;
- compact operation-derived ingestion history;
- result bounds, redaction, pagination, and retention;
- canonical API, client, CLI, contract, documentation, and deterministic tests.

Out of scope:

- a new authoritative run table or state machine;
- telemetry sinks or alerts (RI-09);
- content-state reconciliation or requeue policy (RI-08);
- frontend Task History, which remains on legacy `/api/v1/jobs/history`;
- changing ingestion adapter execution semantics;
- deleting legacy `/api/v1/jobs/history`.

## Approaches Considered

### Approach A: Operation-native typed projection — Recommended

Keep `pgqueuer_jobs` authoritative, enrich its typed result, and derive a
compact ingestion-history read model at query time.

Pros:

- preserves retry, checkpoint, idempotency, and parent-child authority;
- no dual-write path or reconciliation process;
- additive domain history plus a wire-compatible summary-only list migration;
- gives RI-08 and RI-09 one shared outcome classifier.

Cons:

- JSONB query predicates require careful indexes only if measurement proves
  they are needed;
- historical rows cannot recover partial details that were never persisted and
  must honestly project `unknown`;
- exact operation results remain larger than compact history rows because the
  pipeline needs complete content provenance while active.

Effort: L, split into bounded M/S packages.

### Approach B: Immutable terminal read-model table

Materialize a terminal `ingestion_history` row keyed by operation ID while
leaving workflow state in `pgqueuer_jobs`.

Pros:

- simple indexed history queries;
- independent history retention and compact rows;
- no need to inspect JSONB during reads.

Cons:

- introduces dual-write and backfill/reconciliation behavior;
- terminal projection failures can make history disagree with operations;
- no measured query or retention requirement currently justifies it.

Effort: L.

### Approach C: Original run and source-result tables

Create authoritative `IngestionRun` and `SourceRunResult` records written by
every pipeline driver.

Pros:

- purpose-built relational reporting;
- natural per-source rows.

Cons:

- duplicates the operation state machine, parent-child graph, retry identity,
  and terminal outcome;
- requires every producer to dual-write correctly;
- conflicts with the canonical workflow architecture already shipped.

Effort: XL. Rejected.

### Selected Approach

Approach A. The approved roadmap explicitly requires existing durable state to
remain authoritative and permits a projection only after a demonstrated query
or retention gap. The current gaps are contract and query gaps, not evidence
that a second persistence model is needed.

## Dependencies

- `ri-05` — real-ingestion fixtures and durable failure taxonomy.
- `ri-06` — cross-surface CLI evaluation coverage.

## Impact

Durable capabilities updated:

- `agentic-operations` — operation-derived history and parent identity;
- `pipeline` — typed source summaries and partial outcome;
- `cli-interface` — canonical `aca ingest history` and partial warning;
- `job-management` — legacy `/jobs/history` becomes compatibility-only.

Primary implementation areas:

- `src/ingestion/result.py`, `src/queue/workflow_handlers.py`;
- `src/workflows/pipeline.py`, `src/services/operation_service.py`;
- `src/api/ingestion_routes.py`, canonical client/CLI modules;
- queue worker maintenance and settings;
- durable content-workflow OpenAPI plus generated models.

Overlapping active changes are coordination constraints, not scope additions:
RI-08 consumes the classifier for recovery, RI-09 consumes it for alerts,
API versioning owns future breaking boundaries, and Obsidian ingestion must
adopt the final result contract.

## Acceptance Outcomes

- Every original persisted-result acceptance case maps to existing durable
  state or an implemented typed projection; no parallel run table is added.
- Partial, zero-item, failed, cancelled, successful, and legacy-unknown
  ingestion outcomes are distinguishable through canonical API and CLI history.
- A 1-of-N configured-source failure survives as a bounded, opaque-keyed source
  outcome rather than only a log message.
- History cursors are bound to their filter set and cannot be replayed under a
  different query.
- Public history rows and diagnostics have deterministic bounds while exact
  content provenance remains available only on the individual operation.
- Automatic retention preserves whole operation graphs, never removes active
  work, keeps retryable failures for a longer finite horizon, and never
  detaches children from their parent.
- Pipeline retry, checkpoint, idempotency, and parent-child behavior remain
  authoritative in `OperationService`.

## Risks

- Existing rows irretrievably lost partial details. They must report `unknown`,
  not infer success from lifecycle `completed`.
- Compact history is terminal-only. Queued and in-progress work stays on the
  generic operations surface, avoiding invented counts before a result exists.
- Source locators can contain private URLs, prompts, or mailbox queries.
  History stores the same secret-derived opaque HMAC key used by
  configured-source discovery, never the natural locator.
- Cleanup runs in every worker process. It therefore requires a PostgreSQL
  advisory lock, graph-level eligibility checks, idempotent bounded batches,
  and finite completed/failed horizons.
- Exact `content_ids` can be large and are needed for pipeline provenance.
  They remain on exact operation results but are excluded from compact history.
