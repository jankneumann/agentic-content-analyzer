# Tasks: Reconcile persisted ingestion results

> Change ID: `persisted-ingestion-run-results`
> Selected approach: operation-native typed projection

## Status

- [x] Planning
- [ ] Implementation
- [ ] Testing
- [ ] Review
- [ ] Done

## Phase 1 — Contract reconciliation

- [ ] 1.1 Write contract tests for the versioned ingestion result, bounded
  diagnostics, opaque configured-source outcomes, compact history row, history
  page, summary-only generic operation page, pipeline ingestion summary, named
  enum generation, V1 compatibility, plus legacy `unknown` outcome. Generated
  Python MUST import and generated TypeScript MUST type-check. (RED)
  **Spec scenarios:** ingestion-run-result-projection — typed durable outcome,
  configured-source partial failure, legacy result, bounded public projection
  **Contracts:** `contracts/openapi/v1.yaml`
  **Design decisions:** D1, D2, D3, D5
  **Dependencies:** None — **Size: M**
- [ ] 1.2 Extend the durable content-workflow OpenAPI contract plus both
  generators with named enum aliases, `IngestionResultV1|V2`, the pipeline
  ingestion summary and `pipeline.run` result-schema registry mapping, plus
  compact history schemas.
  **Dependencies:** 1.1 — **Size: M**
- [ ] 1.3 Add a reconciliation matrix mapping every original acceptance case
  to the existing operation field, the new projection field, or an explicit
  non-recoverable legacy gap.
  **Design decisions:** D1
  **Dependencies:** 1.1 — **Size: S**
- [ ] Checkpoint: run workflow contract generation/drift tests, review the
  contract diff, confirm no run table or workflow state was introduced.

## Phase 2 — Typed durable outcomes

- [ ] 2.1 Write queue-handler tests proving `ok`, `partial`, plus `error`
  ingestion responses persist status, counts, diagnostics, source outcomes,
  and one exact content-ID list before terminal handling. (RED)
  **Spec scenarios:** typed durable outcome, failed outcome before exception,
  no duplicate content provenance
  **Contracts:** `contracts/openapi/v1.yaml#/components/schemas/IngestionResult`
  **Design decisions:** D1, D2, D3
  **Dependencies:** 1.2 — **Size: M**
- [ ] 2.2 Implement the versioned ingestion result plus bounded diagnostic
  projection; attach failed source results before raising the workflow error.
  **Dependencies:** 2.1 — **Size: M**
- [ ] 2.3 Write source-aggregation tests for opaque stable source keys,
  equality with configured-source discovery across URL/ID/query/singleton
  locators, partial visibility, total-budget truncation, plus adversarial
  locator/credential/message redaction across result/problem/notification/log
  projections. (RED)
  **Spec scenarios:** configured-source partial failure, private locator
  redaction, deterministic bounds
  **Design decisions:** D3, D5
  **Dependencies:** 1.2 — **Size: M**
- [ ] 2.4 Centralize secret-derived public source-key creation at the
  configuration boundary, carry configured identity through every aggregation
  adapter, sanitize allowlisted metadata, then preserve it in the operation
  result.
  **Dependencies:** 2.3 — **Size: M**
- [ ] Checkpoint: run ingestion-result, queue-handler, contract, plus strict
  serialization tests; inspect fixtures for raw locators or secrets.

## Phase 3 — Shared pipeline classification

- [ ] 3.1 Write pipeline-classifier tests for success, zero-item, partial,
  failed, cancelled, plus legacy-unknown children; include mixed-source,
  strict-partial, zero-item, stable `result.ingestion_summary`, plus
  retry-resume cases and every aggregate-precedence row from D2. (RED)
  **Spec scenarios:** mixed pipeline outcomes, zero-item source, legacy result,
  retry preserves authority
  **Contracts:** `contracts/openapi/v1.yaml#/components/schemas/IngestionOutcome`
  **Design decisions:** D2, D4
  **Dependencies:** 2.2 — **Size: M**
- [ ] 3.2 Implement typed pipeline source summaries with the shared outcome
  classifier without changing checkpoint, retry-child, or idempotency behavior.
  **Dependencies:** 3.1, 2.4 — **Size: M**
- [ ] 3.3 Write CLI wait tests proving tolerated partial pipelines warn on
  stderr while JSON remains one document; fail-on-source-error still exits 1.
  (RED)
  **Spec scenarios:** tolerated partial pipeline, strict source failure,
  JSON output purity
  **Design decisions:** D4
  **Dependencies:** 3.2 — **Size: S**
- [ ] 3.4 Add the partial/zero-item human summary to pipeline wait output.
  **Dependencies:** 3.3 — **Size: S**
- [ ] Checkpoint: run pipeline workflow, operation retry, plus canonical CLI
  tests; verify checkpoint byte-for-byte compatibility in retry fixtures.

## Phase 4 — Compact ingestion history

- [ ] 4.1 Write service/API tests proving generic operation lists return
  `OperationSummary` without result, input, checkpoint, resource metadata, or
  problem detail, and sanitize lifecycle messages while exact reads remain
  unchanged. Assert rows introduce no key rejected by the old strict
  `OperationHandle`; add bounded traversal/status-filter and
  client/CLI/web generated-type migration tests. (RED)
  **Spec scenarios:** summary-only generic operation list
  **Contracts:** `contracts/openapi/v1.yaml#/paths/~1api~1v1~1operations/get`
  **Design decisions:** D5
  **Dependencies:** 1.2 — **Size: M**
- [ ] 4.2 Implement the summary-only generic operation list and migrate every
  first-party API, CLI, plus web Background Tasks list consumer atomically.
  Add `--max-pages`/truncation signaling; hydrate the web indicator from one
  recent page plus bounded queued/in-progress queries.
  **Dependencies:** 4.1 — **Size: M**
- [ ] 4.3 Write service/API tests for compact history filtering by command,
  opaque configured-source key, outcome, lifecycle status, parent, plus
  creation window; assert terminal-only rows, signed filter-bound cursors,
  invalid windows/IDs/sizes, rejection of active status values,
  authorization/rate budgets, legacy command
  precedence, nullable legacy counts, plus legacy `unknown`. (RED)
  **Spec scenarios:** filtered history, cursor query mismatch, pipeline context,
  legacy history row
  **Contracts:** `contracts/openapi/v1.yaml#/paths/~1api~1v1~1ingestions/get`
  **Design decisions:** D5, D6
  **Dependencies:** 3.2 — **Size: M**
- [ ] 4.4 Implement the compact operation-derived history query over
  `pgqueuer_jobs`; exclude exact result/checkpoint payloads from pages.
  **Dependencies:** 4.3 — **Size: M**
- [ ] 4.5 Write cross-surface tests for `aca ingest history`, including
  omitted optional query values, configured-source filtering, all-pages
  `--max-pages` request budgets, JSON purity, plus bounded human output. (RED)
  **Spec scenarios:** canonical history parity, absent filter omission,
  bounded output
  **Contracts:** `contracts/openapi/v1.yaml#/paths/~1api~1v1~1ingestions/get`
  **Design decisions:** D5
  **Dependencies:** 4.3 — **Size: M**
- [ ] 4.6 Implement `aca ingest history` through the canonical client with the
  same filter vocabulary as the API.
  **Dependencies:** 4.4, 4.5 — **Size: M**
- [ ] 4.7 Write PostgreSQL query-plan tests over at least 10,000 representative
  operations; assert indexed order plus bounded rows scanned for selective
  command/configured-source/outcome/parent queries. (RED)
  **Spec scenarios:** filtered history, bounded output
  **Design decisions:** D5, D6
  **Dependencies:** 4.4 — **Size: M**
- [ ] 4.8 Add only the smallest ordering or JSONB-expression indexes required
  by `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` evidence.
  **Dependencies:** 4.7 — **Size: S**
- [ ] Checkpoint: run service, API, client, CLI, OpenAPI drift, query-plan,
  plus gen-eval
  descriptor-drift tests; confirm existing POST `/api/v1/ingestions` is
  unchanged.

## Phase 5 — Graph-aware retention

- [ ] 5.1 Write PostgreSQL tests for configurable retention, whole-graph
  eligibility, active-work preservation, finite failed horizon, bounded
  settings, bounded batches/timeouts, advisory-lock exclusion, transactional
  recheck, restart duplication, null terminal `completed_at`,
  Gemini-batch-disabled startup, metrics, plus exact cutoff boundaries. (RED)
  **Spec scenarios:** retained operation graph, active descendant, retryable
  failure, automatic cleanup
  **Design decisions:** D7
  **Dependencies:** 3.2 — **Size: M**
- [ ] 5.2 Replace row-local cleanup with graph-aware terminal cleanup.
  **Dependencies:** 5.1 — **Size: M**
- [ ] 5.3 Wire one advisory-locked interval retention tick into the worker using a
  validated `JOB_RETENTION_DAYS`/failed-retention policy independently of
  optional batch maintenance.
  **Dependencies:** 5.2 — **Size: S**
- [ ] Checkpoint: run queue integration tests against PostgreSQL, inspect the
  retention evidence, verify repeated cleanup is idempotent.

## Phase 6 — Documentation and close-out

- [ ] 6.1 Reconcile API/CLI documentation plus the stale job-history spec so
  canonical ingestion history, outcome semantics, bounds, plus retention are
  explicit; note that legacy `/jobs/history` remains compatibility-only.
  **Spec scenarios:** all
  **Design decisions:** D1–D7
  **Dependencies:** 4.6, 5.2 — **Size: S**
- [ ] 6.2 Add RI-06 gen-eval scenarios for filtered history, zero-item output,
  and partial warning behavior without enabling mutation in the PR tier.
  **Spec scenarios:** canonical history parity, tolerated partial pipeline
  **Design decisions:** D4, D5
  **Dependencies:** 4.6 — **Size: S**
- [ ] 6.3 Run strict OpenSpec validation, contract drift, focused tests, full
  default tests, lint, type checks, and implementation/security review.
  **Dependencies:** all — **Size: S**
- [ ] Checkpoint: review the complete diff, confirm every file maps to a task,
  verify no telemetry sink, content reconciliation, or second run model
  entered scope.
