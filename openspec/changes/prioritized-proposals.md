# Proposal Prioritization Report

**Date**: 2026-07-18 20:02:03 EDT
**Analyzed Range**: `HEAD~50..HEAD` (50 commits)
**Baseline**: `0922874d` (`main`, identical to `origin/main`)
**Entries Analyzed**: 13 active OpenSpec entries (12 proposals and 1 analysis-only directory)

> **Reconciled 2026-07-23:** This report is a historical input to
> `reconcile-openspec-inventory`. Its implemented and superseded entries are
> now archived, genuine residual work is captured in four focused successors,
> and `add-cross-surface-release-smoke-tests` is the next workflow-surface
> roadmap item. Use the current OpenSpec inventory for live status.

## Executive Finding

The unified content workflow refactoring is fully merged and green, but the active
OpenSpec inventory is not reconciled with implementation reality:

- Five proposals are implemented and should be verified, task-reconciled, and archived:
  `add-huggingface-papers-source`, `add-ingestion-filtering-prioritization`,
  `db-source-overrides`, `llm-router-evaluation`, and
  `use-paradedb-railway-langfuse-default` (the last still needs external deployment
  verification).
- `unify-mcp-ingest-envelope` is superseded by the canonical durable operation model and
  must not be implemented as written.
- Four ingestion-reliability proposals remain valuable, but all were written against the
  pre-refactor pipeline and queue model.
- `feynman-inspired-features` is analysis, not an implementable OpenSpec proposal.

The highest-value next action is to refine the real-ingestion CI proposal against the new
source fixture matrix and durable operation contract. Before implementation starts, a
parallel hygiene pass should close the implemented/superseded entries.

## Validation Status

`openspec validate --all` currently reports 51 passing and 15 failing entries. The
proposal failures reinforce the readiness assessment:

- `persisted-ingestion-run-results`,
  `production-telemetry-and-out-of-band-alerting`,
  `real-ingestion-test-tiers-in-ci`, `stuck-content-sweeper-and-requeue-cli`, and
  `unify-mcp-ingest-envelope` have no parseable delta specs.
- `add-huggingface-papers-source` and `llm-router-evaluation` contain spec files without
  the required ADDED/MODIFIED/REMOVED delta sections, despite their implementations being
  present.
- Other failing main-spec entries predate this report and are outside proposal
  prioritization scope.

The OpenSpec CLI also attempted to flush anonymous telemetry to `edge.openspec.dev`; that
network failure occurred after validation output and did not affect the results above.

## Refactoring Constraints for Every Remaining Proposal

Any proposal that creates or changes a long-running workflow must now:

1. Submit work through the shared workflow/application services and return a durable
   `OperationHandle`; it must not add a transport-specific execution path.
2. Extend `openspec/contracts/content-workflows/` when the executable OpenAPI, event, or
   database contract changes. Archived change contracts are historical snapshots only.
3. Use `SOURCE_REGISTRY` and the typed `IngestCommand` union for ingestion sources.
4. Preserve CLI, HTTP, MCP, worker, and frontend parity through the canonical contract
   models and generated clients.
5. Add or update the canonical source/workflow fixture matrix rather than creating an
   isolated adapter-only integration path.
6. Reuse `pgqueuer_jobs` operation state, parent/child relationships, checkpoints,
   idempotency, retry, cancellation, and persisted results before introducing a parallel
   run-state model.

## Priority Order

### 1. `real-ingestion-test-tiers-in-ci` — Real ingestion test tiers in CI

- **Relevance**: Needs Refinement, high value. CI still excludes `integration` and
  `hoverfly`, so the core gap remains, but the referenced
  `tests/cli/test_ingest_contract.py` no longer exists.
- **Readiness**: Needs Planning (0/10 generic checklist items; no design or delta spec).
- **Conflicts**: `add-obsidian-vault-ingest` on the source fixture matrix; otherwise
  isolated.
- **Required modification**: Replace the deleted CLI test with a canonical source command
  submitted through the workflow service. Assert the terminal operation's source result
  and `items_ingested` match the database row delta. Use the existing
  `tests/fixtures/sources/` harness and `test_source_workflow_matrix.py`. Define a curated
  PR-blocking suite instead of running every broadly marked integration test, and add the
  nightly behavior to the `e2e-testing` spec and durable workflow contract where needed.
- **Recommendation**: Refine, then implement first. It protects every later ingestion
  change and is small enough to land with low conflict risk.
- **Next Step**: `/iterate-on-plan real-ingestion-test-tiers-in-ci`

### 2. `persisted-ingestion-run-results` — Persisted ingestion run results

- **Relevance**: Needs Verification and Refinement. The refactor already persists pipeline
  operations, parent/child source operations, checkpoints, `source_results`, problems,
  resources, and terminal results in `pgqueuer_jobs`.
- **Readiness**: Needs Planning (0/10 generic checklist items; no design or delta spec).
- **Conflicts**: `stuck-content-sweeper-and-requeue-cli`,
  `production-telemetry-and-out-of-band-alerting`, and API versioning through operation
  query surfaces.
- **Required modification**: Do not create `IngestionRun` and `SourceRunResult` tables
  until a documented query or retention requirement proves the operation payload is
  insufficient. First map each acceptance outcome to existing pipeline operation results.
  Reframe the likely remainder as typed ingestion-run resource projection, operation list
  filtering, per-source history queries, and warning/non-zero CLI behavior. Update the
  `agentic-operations`, `job-management`, and `pipeline` specs plus the durable OpenAPI
  registry.
- **Recommendation**: Refine immediately because it defines the state model needed by
  telemetry and recovery proposals.
- **Next Step**: `/iterate-on-plan persisted-ingestion-run-results`

### 3. `stuck-content-sweeper-and-requeue-cli` — Stuck-content sweeper and requeue CLI

- **Relevance**: Needs Refinement. Queue-level stale detection, operation retry,
  cancellation, parent/child reconciliation, and checkpoint-preserving pipeline retry now
  exist. Content rows can still require domain-state reconciliation.
- **Readiness**: Needs Planning (0/10 generic checklist items; no design or delta spec).
- **Conflicts**: `persisted-ingestion-run-results` on operation state and CLI/API controls;
  production telemetry on worker/queue failure handling.
- **Required modification**: Narrow scope from generic job requeueing to reconciling
  content transitional states with terminal/stale operations. Define authoritative
  operation-to-resource rules, retry budgets, idempotency, and status transitions. Reuse
  `aca operations retry` where possible; add a narrowly scoped reconciliation command only
  for content state that cannot be recovered through operation retry. Replace stale
  `summarizer.py` assumptions with workflow and `OperationService` paths.
- **Recommendation**: Refine after or together with the persisted-results state decision;
  implement after that contract stabilizes.
- **Next Step**: `/iterate-on-plan stuck-content-sweeper-and-requeue-cli`

### 4. `add-obsidian-vault-ingest` — Add Obsidian Vault Ingestion Bridge

- **Relevance**: Still Relevant, but Needs Refinement after the workflow refactor.
- **Readiness**: Detailed plan exists (0/34 tasks, design and delta spec present), but its
  integration architecture is stale.
- **Conflicts**: Real-ingestion CI on source fixtures; future API versioning on OpenAPI/API
  surfaces. Existing Obsidian export/sync modules create naming and ownership overlap.
- **Required modification**: Add an Obsidian source descriptor to `SOURCE_REGISTRY`, a
  typed `IngestCommand` variant, capability metadata, and durable OpenAPI/generated model
  updates. MCP must use `src/mcp_tools/ingestion.py` and return an `OperationHandle`, not
  enqueue a private path. Add the adapter to the canonical source workflow matrix. Define
  how DB source overrides represent local filesystem-only sources and explicitly separate
  vault ingress from the existing Obsidian knowledge-base export/sync subsystem.
- **Recommendation**: Refine now; implementation can follow the real-ingestion test tier so
  the new adapter lands with real behavioral coverage.
- **Next Step**: `/iterate-on-plan add-obsidian-vault-ingest`

### 5. `use-paradedb-railway-langfuse-default` — ParadeDB on Railway and Langfuse defaults

- **Relevance**: Needs Verification; most implementation is already on `main` despite
  tasks showing 0/17. Profiles use Langfuse, Railway documents ParadeDB, and the feature
  landed in commit `d13dfa4e`.
- **Readiness**: Partially Ready/implemented. External GHCR and Railway state is not proven
  by repository evidence.
- **Conflicts**: Production telemetry on observability documentation/configuration only.
- **Required modification**: Reconcile task checkboxes with current files, verify the GHCR
  image and Railway deployment under explicit deployment authority, and resolve the image
  name mismatch (`aca-postgres:17-railway` in profiles/proposal versus
  `newsletter-postgres:17-railway` in `railway/postgres/README.md`). Separate any remaining
  operator cutover from already completed config work.
- **Recommendation**: Verify and close; do not reimplement profile changes.
- **Next Step**: `/iterate-on-plan use-paradedb-railway-langfuse-default`, then verify and
  archive. Production changes remain governed by issue #446.

### 6. `production-telemetry-and-out-of-band-alerting` — Production telemetry and alerts

- **Relevance**: Still Relevant, but Needs Refinement. Out-of-band failure notification is
  not provided by the canonical operation refactor.
- **Readiness**: Blocked and Needs Planning (0/10 generic checklist items). Its dependency
  names nonexistent `ingestion-run-persistence`; the actual change ID is
  `persisted-ingestion-run-results`.
- **Conflicts**: Persisted results and stuck-content recovery on operation/worker terminal
  state; ParadeDB/Langfuse work on observability configuration.
- **Required modification**: Instrument canonical workflow handlers and operation terminal
  transitions rather than old `src/tasks/content.py` paths. Derive zero-item/partial source
  alerts from typed terminal ingestion results and pipeline `source_results`. Specify an
  out-of-band sink interface, delivery retry/idempotency, secret handling, and the boundary
  between persisted in-app notifications, SSE delivery, email, and webhooks.
- **Recommendation**: Refine after the persisted-results decision; implement only after its
  dependency is resolved.
- **Next Step**: `/iterate-on-plan production-telemetry-and-out-of-band-alerting`

### 7. `llm-router-evaluation` — LLM Router Evaluation and Dynamic Routing

- **Relevance**: Needs Verification. The feature is implemented and has a passing
  validation report, but tasks incorrectly show 0/34.
- **Readiness**: Implemented foundation. Current production usage passes `ModelStep` only
  in limited call sites, while the refactor moved important generation behavior into
  workflow services.
- **Conflicts**: Future changes touch workflow services, evaluation APIs, provider routing,
  and review integration.
- **Required modification**: Mark implemented tasks accurately and verify the foundation
  against current `src/workflows/` and canonical operation paths. Archive the completed
  evaluation/routing foundation, then create a smaller follow-up for production reachability
  across each intended `ModelStep`, rather than reopening all 34 tasks.
- **Recommendation**: Verify and archive; extract reachability as a new proposal if still
  desired.
- **Next Step**: `/openspec-verify-change llm-router-evaluation`, then archive.

### 8. `add-huggingface-papers-source` — HuggingFace Papers ingestion

- **Relevance**: Likely Addressed. Declared progress is 11/15, but current code contains the
  MCP tool, registry descriptor, worker dispatch, API documentation, generated contract
  type, frontend type, and source configurator support. Its own validation report calls the
  feature complete.
- **Readiness**: Implementation complete; task state is stale.
- **Conflicts**: None after archival. Old design paths conflict conceptually with the new
  registry/MCP layout.
- **Required modification**: Mark integration tasks complete using current registry-based
  evidence, update design references from `src/mcp_server.py`/bespoke UI wiring to the
  canonical source registry and generated contract, run focused verification, and archive.
- **Recommendation**: Verify and archive; do not implement tasks 4.1–4.4 again.
- **Next Step**: `/openspec-verify-change add-huggingface-papers-source`, then archive.

### 9. `add-ingestion-filtering-prioritization` — Ingestion filtering and prioritization

- **Relevance**: Likely Addressed. All 38 tasks are checked and implementation is present,
  including migrations, filtering service, source overrides, CLI/API, and workflow edge
  coverage.
- **Readiness**: Complete.
- **Conflicts**: None after archival.
- **Required modification**: No plan modification. Verify refactor-era workflow integration
  and archive the completed change.
- **Recommendation**: Archive after verification.
- **Next Step**: `/openspec-verify-change add-ingestion-filtering-prioritization`

### 10. `db-source-overrides` — Database-backed source overrides

- **Relevance**: Likely Addressed. All 23 tasks are checked and the model, migration,
  service, merge path, API, CLI, frontend, and tests are present.
- **Readiness**: Complete.
- **Conflicts**: None after archival; remaining source proposals should consume this
  behavior instead of modifying it independently.
- **Required modification**: No plan modification. Verify and archive.
- **Recommendation**: Archive after verification.
- **Next Step**: `/openspec-verify-change db-source-overrides`

### 11. `unify-mcp-ingest-envelope` — Canonical MCP ingestion envelopes

- **Relevance**: Superseded by the refactor. MCP ingestion tools now live in
  `src/mcp_tools/ingestion.py`, submit canonical typed commands, and return durable
  `OperationHandle` objects; terminal results retain canonical ingestion responses.
- **Readiness**: Not applicable. Its 0/23 tasks prescribe the obsolete synchronous
  `IngestionResponse` return shape and modifications to the old monolithic
  `src/mcp_server.py`.
- **Conflicts**: Directly contradicts the durable operation contract.
- **Required modification**: Do not rewrite this proposal for implementation. Record it as
  superseded by `unify-content-workflows-agentic-surfaces`. If the external
  `agentic-assistant` consumer still needs compatibility work, create a focused consumer
  migration issue against `OperationHandle` plus wait/status/result tools.
- **Recommendation**: Archive as superseded.
- **Next Step**: `/openspec-archive-change unify-mcp-ingest-envelope`

### 12. `add-api-versioning` — Add API Versioning

- **Relevance**: Needs Refinement, low urgency. The proposal's statement that the unified
  content refactor is 75% complete is obsolete. The system now has a durable v1 OpenAPI
  registry and generated cross-interface models.
- **Readiness**: Tasks are detailed (0/42), but the proposed wholesale `src/api/v1/` move
  would create widespread conflicts without proving a v2 consumer need.
- **Conflicts**: Every proposal adding API or contract surfaces, especially operation
  history, Obsidian ingestion, evaluation, and notifications.
- **Required modification**: Start with contract lifecycle and deprecation policy, not a
  directory move. Define how `openspec/contracts/content-workflows/openapi/v1.yaml`,
  generated clients, shared workflow endpoints, and `OperationHandle` evolve across
  versions. Inventory existing `/api/v1` routers and external consumers, identify an actual
  breaking v2 change, and preserve version-independent operation status/result endpoints
  where possible.
- **Recommendation**: Defer until a real breaking change or external consumer requires v2;
  iterate the plan before any implementation.
- **Next Step**: `/iterate-on-plan add-api-versioning`

### 13. `feynman-inspired-features` — Analysis-only opportunity inventory

- **Relevance**: Needs Planning. This directory has only `analysis.md`; it is not an
  OpenSpec proposal and has no tasks, design, or delta specs.
- **Readiness**: Not ready.
- **Conflicts**: Potentially broad across agents, research workflows, ingestion sources,
  and verification, but no implementable scope exists yet.
- **Required modification**: Remove it from the active change inventory or select one
  bounded feature and create a real proposal using current workflow services, source
  registry, durable operations, provenance, and contract conventions. Do not implement the
  seven-feature roadmap as one change.
- **Recommendation**: Move analysis to discovery documentation or create one focused change
  candidate.
- **Next Step**: `/plan-feature <selected-feynman-capability>`

## Parallel Workstreams

### Hygiene Stream (start immediately, parallel)

- Verify and archive `add-ingestion-filtering-prioritization`.
- Verify and archive `db-source-overrides`.
- Verify, reconcile tasks, and archive `add-huggingface-papers-source`.
- Verify and archive the implemented `llm-router-evaluation` foundation; extract production
  reachability as a follow-up.
- Archive `unify-mcp-ingest-envelope` as superseded.
- Reconcile `use-paradedb-railway-langfuse-default`, leaving external deployment work under
  explicit rollout authority.

### Planning Stream A (parallel after hygiene starts)

- `real-ingestion-test-tiers-in-ci`
- `add-obsidian-vault-ingest`
- `stuck-content-sweeper-and-requeue-cli`

These plans can be refined concurrently, but the real-ingestion plan should define the
test harness that Obsidian will consume.

### Planning Stream B (sequential dependency)

1. Refine `persisted-ingestion-run-results` around the existing operation/checkpoint model.
2. Refine `production-telemetry-and-out-of-band-alerting` against that decision.

### Deferred

- `add-api-versioning`: wait for a concrete breaking API change or external consumer.
- `feynman-inspired-features`: select one feature and create a real proposal first.

## Conflict Matrix for Remaining Implementation Candidates

Archive/superseded entries are omitted because they should not produce implementation
diffs.

| | real CI | persisted results | stuck recovery | Obsidian ingest | prod telemetry | API versioning |
|---|---|---|---|---|---|---|
| **real CI** | — | operation-result assertions | queue integration tests | source fixture matrix | none | workflow OpenAPI tests |
| **persisted results** | operation-result assertions | — | operation service, CLI/API controls | result contract | direct dependency | operation routes/OpenAPI |
| **stuck recovery** | queue integration tests | operation service, CLI/API controls | — | none | worker failure state | operation routes |
| **Obsidian ingest** | source fixture matrix | result contract | none | — | ingestion metrics | ingestion API/OpenAPI |
| **prod telemetry** | none | direct dependency | worker failure state | ingestion metrics | — | notification API/OpenAPI |
| **API versioning** | workflow OpenAPI tests | operation routes/OpenAPI | operation routes | ingestion API/OpenAPI | notification API/OpenAPI | — |

## Recommended Sequence

1. Run the hygiene stream to shrink the active inventory and prevent duplicate work.
2. Refine and implement `real-ingestion-test-tiers-in-ci`.
3. Decide the persisted run/history model using existing operations and checkpoints.
4. Refine stuck-content recovery and production telemetry against that decision.
5. Refine and implement Obsidian ingestion using the stabilized source test harness.
6. Revisit API versioning only when a concrete v2 contract is required.

**Top recommendation**: `/iterate-on-plan real-ingestion-test-tiers-in-ci`
