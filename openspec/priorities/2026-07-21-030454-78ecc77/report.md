# Proposal Prioritization Report

**Run ID**: 2026-07-21-030454-78ecc77
**Generated**: 2026-07-21T03:04:54Z
**Analyzed Range**: `HEAD~50..HEAD` (50 commits)
**Active Changes Found**: 14
**Proposals Analyzed**: 13 (plus one analysis-only directory)

## Executive Recommendation

Implement `add-gemini-batch-processing` next. In parallel, refresh the small and file-isolated `real-ingestion-test-tiers-in-ci` plan and verify whether `persisted-ingestion-run-results` was superseded by the recently landed durable operation/pipeline model.

Recent history is dominated by the canonical durable-workflow and MCP migration, source-registry work, contract hardening, and CI fixes. That history makes six older active changes look implemented or superseded even though their OpenSpec task state was never reconciled.

## Priority Order

### 1. `add-gemini-batch-processing` — Add Gemini Batch API Execution for Non-Latency-Sensitive Steps

- **Relevance**: Still Relevant — no `batch_jobs`/`batch_requests` persistence, batch collector, Gemini batch submit/poll API, or `PENDING_BATCH` content state exists.
- **Readiness**: Ready (0/33 tasks complete; proposal, design, tasks, and `gemini-batch-execution` spec present).
- **Scope**: Large but phased; Phase 0 is independently deployable with batching disabled by default.
- **Conflicts**: Direct overlap with the evaluation/filtering code on `src/services/llm_router.py`, `src/config/models.py`, and `settings/models.yaml`; with reliability work on queue/worker and content status; most of the former overlap is with changes recommended for archival.
- **Recommendation**: Implement next. Preserve the new durable-operation boundary when registering submit/poll work, and treat the proposal's `src/queue/worker.py` integration sketch as subject to the current canonical workflow registry.
- **Next Step**: `/implement-feature add-gemini-batch-processing`

### 2. `persisted-ingestion-run-results` — Persisted ingestion run results

- **Relevance**: Needs Verification — the last 50 commits added durable parent/child operations, per-source `source_results`, persisted canonical ingestion results, retry checkpoints, and CLI/API operation queries. Those structures appear to satisfy most acceptance outcomes without the proposed `IngestionRun` and `SourceRunResult` tables.
- **Readiness**: Needs Planning (0/10 generic tasks; no design or spec delta).
- **Conflicts**: Pipeline, operation, queue, CLI, and API surfaces overlap with telemetry, stuck-content recovery, MCP operation tools, and Gemini queue work.
- **Recommendation**: Reconcile the proposal against `src/workflows/pipeline.py`, `src/services/operation_service.py`, and `src/models/jobs.py`. Archive if durable operations cover the acceptance outcomes; otherwise re-scope only the missing reporting behavior.
- **Next Step**: `/iterate-on-plan persisted-ingestion-run-results`

### 3. `real-ingestion-test-tiers-in-ci` — Real ingestion test tiers in CI

- **Relevance**: Needs Refinement — CI still excludes `integration`, `hoverfly`, and `live_api`, so the quality gap remains. However, the cited `tests/cli/test_ingest_contract.py` no longer exists and recent workflow-contract tests changed the correct integration entry points.
- **Readiness**: Needs Planning (0/10 generic tasks; no design or spec delta).
- **Conflicts**: Low. Primarily `.github/workflows/ci.yml` and ingestion/integration tests; safe to plan alongside Gemini work.
- **Recommendation**: Refresh paths, marker counts, database setup, and the nightly live-smoke boundary, then implement as the first independent reliability stream.
- **Next Step**: `/iterate-on-plan real-ingestion-test-tiers-in-ci`

### 4. `stuck-content-sweeper-and-requeue-cli` — Stuck-content sweeper and requeue CLI

- **Relevance**: Still Relevant — operation/job retry exists, but no content-state sweeper was found for stale `PROCESSING`/`PARSING` rows, and failed content remains excluded by the resolver.
- **Readiness**: Needs Planning (0/10 generic tasks; no design or spec delta).
- **Conflicts**: Queue/worker, retry, content status, migrations, and CLI surfaces overlap with Gemini batch work and production telemetry.
- **Recommendation**: Refine around the current `OperationService` retry model and explicitly define atomic job/content-state recovery, timeout ownership, retry budgets, and idempotency.
- **Next Step**: `/iterate-on-plan stuck-content-sweeper-and-requeue-cli`

### 5. `production-telemetry-and-out-of-band-alerting` — Production telemetry and out-of-band alerting

- **Relevance**: Needs Refinement — the worker now emits persisted job notifications, but `NotificationDispatcher` still delivers only to connected SSE subscribers; no email/webhook out-of-band channel exists. The cited instrumentation and worker boundaries have changed.
- **Readiness**: Blocked (0/10 generic tasks) until the `ingestion-run-persistence` dependency is reconciled with `persisted-ingestion-run-results` and the canonical operation model.
- **Conflicts**: Direct overlap with Gemini and stuck-content work in worker/queue code, and with Langfuse/observability configuration.
- **Recommendation**: Resolve the dependency through #2, then rewrite the plan around operation events, severity policy, zero-item detection, and one durable email/webhook adapter.
- **Next Step**: `/iterate-on-plan production-telemetry-and-out-of-band-alerting`

### 6. `add-obsidian-vault-ingest` — Add Obsidian Vault Ingestion Bridge

- **Relevance**: Needs Refinement — the user value remains unaddressed, but the design assumes direct orchestrator/worker wiring. New sources now require canonical source descriptors, generated contracts, fixture registration, durable operation submission, and transport parity.
- **Readiness**: Needs Planning (0/34 tasks; detailed design and spec exist, but they predate the source-capability registry and canonical workflow cutover).
- **Conflicts**: `src/config/sources.py`, source specs/contracts, ingestion registration, worker/queue, and MCP source tools overlap with source overrides, HuggingFace, reliability, and Gemini work.
- **Recommendation**: Refresh the plan before implementation. Preserve the vault parser/stabilizer design, but replace legacy invocation wiring with current registry and operation contracts.
- **Next Step**: `/iterate-on-plan add-obsidian-vault-ingest`

### 7. `add-api-versioning` — Add API Versioning

- **Relevance**: Needs Refinement — URL versioning remains useful, but the proposal's unified-content status and route inventory are stale. The API already exposes `/api/v1`, while the proposal would reorganize a much larger current route surface than its design names.
- **Readiness**: Ready technically (0/42 tasks; design and spec present), but not ready strategically without a current client/compatibility inventory.
- **Conflicts**: Highest broad conflict risk: `src/api/app.py`, content/source/evaluation/operation routes, tests, generated OpenAPI, and migration documentation.
- **Recommendation**: Defer until source and reliability changes settle; then re-plan around compatibility policy and router factories instead of moving every route mechanically.
- **Next Step**: `/iterate-on-plan add-api-versioning`

### 8. `use-paradedb-railway-langfuse-default` — Use ParadeDB on Railway and Langfuse as Default Observability

- **Relevance**: Likely Addressed — profiles now default to Langfuse, local self-hosted and cloud settings exist, profile tests exist, Railway documents the GHCR ParadeDB image, and a PostgreSQL image build workflow exists.
- **Readiness**: Verification/cleanup (0/17 task boxes are stale relative to implementation).
- **Conflicts**: Only if reopened: observability configuration overlaps telemetry and model/docs surfaces overlap Gemini/evaluation.
- **Recommendation**: Verify success criteria and archive; separately correct any residual image-name documentation drift if verification finds it.
- **Next Step**: `/openspec-verify-change use-paradedb-railway-langfuse-default`

### 9. `llm-router-evaluation` — LLM Router Evaluation & Dynamic Routing

- **Relevance**: Likely Addressed — evaluation models, service, routes, CLI, tests, routing types, and a passing validation report are present. The report records 157 passing tests and recommends cleanup.
- **Readiness**: Verification/cleanup (0/34 task boxes are stale).
- **Conflicts**: If reopened, overlaps Gemini on `llm_router.py`, model config, settings, CLI, migrations, and docs.
- **Recommendation**: Verify against current workflows, reconcile task boxes, and archive. Treat production callers enabling dynamic routing as a separate follow-up if still desired.
- **Next Step**: `/openspec-verify-change llm-router-evaluation`

### 10. `add-huggingface-papers-source` — Add HuggingFace Papers Ingestion Source

- **Relevance**: Likely Addressed — the source model, client/service, migration, configuration, canonical workflow descriptor, MCP tool, queue path, fixtures, and tests exist. Its validation report says all five integration layers were complete.
- **Readiness**: Verification/cleanup (11/15 boxes; the four unchecked integration tasks are contradicted by the validation report and current code).
- **Conflicts**: If reopened, overlaps source registry/configuration, content enum/migrations, worker, MCP, and API route work.
- **Recommendation**: Update stale task state during verification, then archive.
- **Next Step**: `/openspec-verify-change add-huggingface-papers-source`

### 11. `add-ingestion-filtering-prioritization` — Add Ingestion-Time Filtering and Prioritization

- **Relevance**: Likely Addressed — all 38 tasks are checked; filter models/migrations/config/service/hooks, `FILTERED_OUT`, CLI/API behavior, and tests are present.
- **Readiness**: Verification/cleanup (38/38 tasks complete).
- **Conflicts**: If reopened, overlaps Gemini on filter/model configuration and reliability work on content-state handling.
- **Recommendation**: Verify and archive; do not reimplement.
- **Next Step**: `/openspec-verify-change add-ingestion-filtering-prioritization`

### 12. `db-source-overrides` — Database source overrides

- **Relevance**: Likely Addressed — all 23 tasks are checked and current code contains the model, service, fail-open merge, API, CLI, web settings surface, tests, and docs.
- **Readiness**: Verification/cleanup (23/23 tasks complete).
- **Conflicts**: If reopened, overlaps source configuration/registry work and API versioning.
- **Recommendation**: Verify and archive; do not leave a completed proposal active.
- **Next Step**: `/openspec-verify-change db-source-overrides`

### 13. `unify-mcp-ingest-envelope` — Unify MCP ingest envelope shapes

- **Relevance**: Likely Addressed / Superseded — recent commits replaced direct MCP ingestion execution with canonical durable operation handles in `src/mcp_tools/ingestion.py`, added transport/schema parity tests, and split the legacy `src/mcp_server.py` surface. The proposal's requested `IngestionResponse` return shape is no longer the governing contract.
- **Readiness**: Verification/cleanup (0/23 stale tasks; no design/spec delta).
- **Conflicts**: Reopening the old design would conflict with the newly archived canonical workflow and current MCP operation contracts.
- **Recommendation**: Verify the intent against the new `OperationHandle` contract, then archive as superseded rather than implementing the obsolete envelope projection.
- **Next Step**: `/openspec-verify-change unify-mcp-ingest-envelope`

## Parallel Workstreams

### Stream A — Start immediately

- `add-gemini-batch-processing`: implementation, beginning with inert Phase 0 infrastructure.
- `real-ingestion-test-tiers-in-ci`: plan refresh only; its files are isolated from Gemini implementation.
- `persisted-ingestion-run-results`: verification/reconciliation only; determine whether any residual scope remains.

### Stream B — After Stream A decisions

- Implement the refreshed CI tiers independently.
- Refine `stuck-content-sweeper-and-requeue-cli` around current operation retry semantics.
- Refresh `add-obsidian-vault-ingest`; start implementation only after Gemini's queue/worker integration points are stable.

### Sequential / Deferred

- `production-telemetry-and-out-of-band-alerting`: wait for the persistence reconciliation and avoid concurrent worker edits with Gemini/stuck-content work.
- `add-api-versioning`: wait until source/API changes settle because it reorganizes the broadest shared surface.
- Six likely-addressed changes: verify and archive before opening new implementation branches from them.

## Conflict Matrix

Legend: `●` direct planned file/spec overlap, `○` adjacent shared integration surface or documentation, `—` no material overlap. Addressed/superseded proposals remain in the matrix because reopening them would still create conflicts.

| | API | GEM | HF | FIL | OBS | DB | EVAL | RUN | TEL | CI | STK | MCP | INF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **API** | — | — | ● | ● | ● | ● | ● | ● | ○ | — | — | — | — |
| **GEM** | — | — | ● | ● | ● | ○ | ● | ● | ● | — | ● | ○ | ○ |
| **HF** | ● | ● | — | ● | ● | ● | — | ● | ● | ○ | ● | ● | — |
| **FIL** | ● | ● | ● | — | ● | ● | ● | ● | ● | ○ | ● | ○ | ○ |
| **OBS** | ● | ● | ● | ● | — | ● | — | ● | ● | ○ | ● | ● | ○ |
| **DB** | ● | ○ | ● | ● | ● | — | ● | ● | — | ○ | ○ | ● | ● |
| **EVAL** | ● | ● | — | ● | — | ● | — | ● | ● | ○ | — | — | ● |
| **RUN** | ● | ● | ● | ● | ● | ● | ● | — | ● | ● | ● | ● | — |
| **TEL** | ○ | ● | ● | ● | ● | — | ● | ● | — | ○ | ● | ○ | ● |
| **CI** | — | — | ○ | ○ | ○ | ○ | ○ | ● | ○ | — | ○ | — | ○ |
| **STK** | — | ● | ● | ● | ● | ○ | — | ● | ● | ○ | — | ● | — |
| **MCP** | — | ○ | ● | ○ | ● | ● | — | ● | ○ | — | ● | — | — |
| **INF** | — | ○ | — | ○ | ○ | ● | ● | — | ● | ○ | — | — | — |

Abbreviations: API=`add-api-versioning`, GEM=`add-gemini-batch-processing`, HF=`add-huggingface-papers-source`, FIL=`add-ingestion-filtering-prioritization`, OBS=`add-obsidian-vault-ingest`, DB=`db-source-overrides`, EVAL=`llm-router-evaluation`, RUN=`persisted-ingestion-run-results`, TEL=`production-telemetry-and-out-of-band-alerting`, CI=`real-ingestion-test-tiers-in-ci`, STK=`stuck-content-sweeper-and-requeue-cli`, MCP=`unify-mcp-ingest-envelope`, INF=`use-paradedb-railway-langfuse-default`.

### Highest-Risk Direct Overlaps

- Gemini ↔ evaluation/filtering: `src/services/llm_router.py`, `src/config/models.py`, `settings/models.yaml`, filter call paths.
- Gemini ↔ reliability: queue/worker scheduling, content status, migrations, retry/fallback behavior.
- Obsidian ↔ source work: `src/config/sources.py`, source-capability registry/specs/contracts, queue submission, MCP source tools.
- API versioning ↔ most API-bearing proposals: `src/api/app.py`, route modules, OpenAPI contracts, and API tests.
- Persistence ↔ telemetry/stuck-content/MCP: operation payloads, parent-child results, retry state, CLI/API/MCP operation queries.

## Proposals Needing Attention

### Likely Addressed or Superseded

- `db-source-overrides`: 23/23 tasks complete; verify and archive.
- `add-ingestion-filtering-prioritization`: 38/38 tasks complete; verify and archive.
- `add-huggingface-papers-source`: validation says complete; reconcile four stale boxes, verify, archive.
- `llm-router-evaluation`: validation says complete; reconcile stale task file, verify, archive.
- `use-paradedb-railway-langfuse-default`: implementation and tests are present; verify and archive.
- `unify-mcp-ingest-envelope`: superseded by canonical durable MCP operations; verify intent and archive.

### Needs Refinement or Dependency Reconciliation

- `persisted-ingestion-run-results`: compare acceptance outcomes with durable operation `source_results` before designing new tables.
- `real-ingestion-test-tiers-in-ci`: replace deleted test paths and recalculate marker coverage.
- `stuck-content-sweeper-and-requeue-cli`: align content recovery with operation retry/idempotency.
- `production-telemetry-and-out-of-band-alerting`: resolve dependency name/scope and target current operation events.
- `add-obsidian-vault-ingest`: adopt source registry, generated contracts, fixtures, and durable operation submission.
- `add-api-versioning`: inventory current routes and consumers before reorganizing the API tree.

### Analysis-Only Active Directory

- `feynman-inspired-features` was not scored as a proposal because it contains only `analysis.md`: no `proposal.md`, `tasks.md`, design, or spec delta. Convert one bounded idea (rather than the full P0–P6 analysis) into an OpenSpec proposal before prioritizing it.

## Recent-History Evidence

- Range: `HEAD~50..HEAD`, exactly 50 commits.
- Major themes: canonical workflow contracts and handlers, durable operation results/retry, MCP tool split and transport parity, source workflow matrices, contract fuzzing, and CI fixes.
- Particularly relevant current files: `src/workflows/pipeline.py`, `src/services/operation_service.py`, `src/mcp_tools/ingestion.py`, `src/queue/workflow_handlers.py`, `.github/workflows/ci.yml`, `src/api/source_write_routes.py`, and the source capability contracts.
- The working tree already contained untracked `.pnpm-store/`, `openspec/changes/add-gemini-batch-processing/`, and `openspec/schemas/`; this report did not modify or stage those user-owned paths.
