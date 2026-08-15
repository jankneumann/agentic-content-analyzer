# Workflow Surface Reliability and Ingestion Roadmap

## Motivation

The canonical durable workflow refactor is implemented in the repository, but the
operator-facing surfaces and the active planning inventory do not yet reflect that
reality. The Railway frontend is serving an older artifact that calls retired
ingestion routes, while the corrected frontend cannot deploy because its Railway
build environment infers npm even though the build invokes pnpm and repository-root
Python tooling. Separately, the shared CLI workflow client serializes absent cursor
values into requests, causing production capability, configured-source, and
operation-list commands to fail with HTTP 422 responses.

Local unit and contract coverage is strong but predominantly mocked. The repository
does not contain the remembered gen-eval descriptors, scenarios, runner dependency,
Make target, or reports. Several active ingestion-reliability proposals remain
valuable but predate the durable operation model, while other active proposals are
already implemented or superseded and should not be reimplemented.

Success means every supported operator surface uses the canonical durable workflow
contract in production, key CLI behavior is continuously evaluated end to end, real
ingestion tiers catch adapter and persistence failures, operation state supports
recovery and alerting without a parallel state model, and the OpenSpec inventory
accurately represents remaining work.

## Capabilities

### Capability: Restore the Railway frontend deployment contract

Make the frontend build reproducible in Railway and deploy the current
capability-driven ingestion UI. Resolve the mismatch between the `web/**` service
root/watch scope and the build's dependency on pnpm, uv, and repository-root
contract generation. Keep generated workflow-contract drift enforcement in a
location where the complete repository toolchain is available.

**Acceptance Outcomes:**
- A clean Railway build of the frontend succeeds from the documented configuration.
- The active production frontend revision contains the canonical ingestion client.
- The ingestion UI discovers source capabilities and submits `/api/v1/ingestions`;
  production traffic no longer calls retired `/api/v1/contents/ingest` or
  `/api/v1/content/save-url` mutations.
- The frontend production build and generated-contract check remain enforced in CI.

### Capability: Repair and stabilize canonical CLI HTTP behavior

Fix the shared workflow client so optional query parameters are omitted when absent,
starting with capability discovery, configured sources, and operation listing. Add
transport-level regression tests that assert the actual serialized query string.
Stabilize the environment-sensitive YouTube curation test, correct the unawaited
graph-test coroutine, and prevent dependency/deprecation warnings from contaminating
operator or JSON output.

**Acceptance Outcomes:**
- `aca capabilities --json`, `aca configured-sources --json`, and
  `aca --json operations list` succeed against a deployed API without an explicit
  cursor.
- Regression tests fail if an absent cursor is serialized as an empty or `None`
  query parameter.
- CLI tests do not select live YouTube API behavior based on developer-local
  credentials.
- The CLI suite completes without unawaited-coroutine warnings, and machine-readable
  stdout contains only the requested result.

### Capability: Add cross-surface release compatibility smoke tests

Add a deployment-boundary gate that verifies frontend, CLI, and API compatibility
against a deployed environment. The gate must detect stale frontend artifacts,
retired mutation calls, capability pagination failures, and failure to create or
observe a durable operation. Read-only checks may run against production; mutating
checks must run in staging or an ephemeral environment unless explicitly authorized.

**Acceptance Outcomes:**
- A smoke test fails when the deployed frontend calls a retired workflow mutation.
- A smoke test exercises capability discovery and cursor omission through both the
  frontend client contract and the real CLI transport.
- A staging or ephemeral smoke scenario submits a canonical ingestion request and
  observes its durable operation through a terminal state.
- Deployment documentation identifies the service revisions and evidence required
  before promotion.

### Capability: Implement real ingestion test tiers in CI

Refine and implement `real-ingestion-test-tiers-in-ci` against `SOURCE_REGISTRY`,
the typed `IngestCommand` union, the source fixture matrix, and durable operation
results. Establish a curated pull-request tier and a broader scheduled tier rather
than relying on every broadly marked integration test.

**Acceptance Outcomes:**
- The PR-blocking tier submits representative source commands through the canonical
  workflow service and verifies terminal operation results against database row
  deltas.
- The nightly tier covers credentialed or network-sensitive adapters with explicit
  skip/failure policy and durable reports.
- Every registered ingestion source is mapped to a fixture tier or an explicit,
  reviewed exclusion.
- CI publishes enough operation/result evidence to diagnose adapter, queue, and
  persistence failures.

### Capability: Establish gen-eval coverage for the CLI workflow contract

Create the missing gen-eval project integration: supported runner dependency,
CLI descriptor, scenarios, Make target, reports, and CI threshold. Cover
version/help, discovery, validation, each canonical submission surface, operation
wait/status/retry/cancel, credential errors, and terminal E2E behavior. Separate
read-only production-compatible scenarios from mutating staging/ephemeral scenarios.

**Acceptance Outcomes:**
- `make gen-eval` runs a checked-in descriptor and scenario suite and emits a
  validated report artifact.
- Scenarios cover every canonical workflow operation type and all operation-control
  commands, with explicit categories for discovery, validation, submission, and
  terminal behavior.
- CI enforces an agreed pass-rate threshold and publishes failures by command and
  category.
- Mutating scenarios cannot target production by default.

### Capability: Reconcile persisted ingestion result requirements

Refine `persisted-ingestion-run-results` around the state already stored in
`pgqueuer_jobs`, including parent/child operations, checkpoints, source results,
problems, resources, retries, and terminal results. Add only the typed projections,
filters, history queries, retention rules, and CLI behavior that are demonstrably
missing; do not introduce parallel run tables without a documented query or
retention requirement.

**Acceptance Outcomes:**
- Every original persisted-result acceptance case is mapped to existing operation
  state or a clearly specified remaining gap.
- Operators can query per-source ingestion history and partial/zero-item outcomes
  through canonical API and CLI surfaces.
- Retention and result-size behavior are documented and tested.
- No second authoritative ingestion-run state machine is introduced.

### Capability: Reconcile stuck content with durable operations

Refine `stuck-content-sweeper-and-requeue-cli` to address domain content rows whose
transitional state disagrees with terminal or stale durable operations. Reuse
operation retry, cancellation, retry budgets, checkpoints, and idempotency; add a
narrow reconciliation command only where operation retry cannot restore content
state.

**Acceptance Outcomes:**
- Authoritative operation-to-content reconciliation rules and retry budgets are
  specified and tested.
- Dry-run output identifies affected content and the corresponding operation without
  mutation.
- Apply mode is idempotent, auditable, and reuses `aca operations retry` whenever
  possible.
- Repeated reconciliation cannot duplicate ingested content or bypass checkpoints.

### Capability: Add production terminal-state telemetry and alerts

Refine `production-telemetry-and-out-of-band-alerting` to instrument canonical
workflow handlers and operation terminal transitions. Derive zero-item, partial
source, terminal failure, and reconciliation alerts from typed persisted results.
Define an out-of-band sink boundary, retry/idempotency behavior, and secret handling
without conflating in-app SSE notifications with external delivery.

**Acceptance Outcomes:**
- Canonical terminal transitions emit structured telemetry for success, partial,
  zero-item, cancelled, and failed outcomes.
- At least one configured out-of-band sink receives deduplicated failure alerts and
  retries delivery safely.
- Alert payloads identify operation, workflow type, affected sources/resources, and
  a stable diagnostic link without exposing secrets.
- Alert behavior is covered by deterministic tests and a staging verification.

### Capability: Add Obsidian vault ingestion through the source registry

Refine `add-obsidian-vault-ingest` to use a source descriptor, typed ingestion
command, capability metadata, durable operation handling, and the canonical source
workflow fixture matrix. Separate local vault ingress from the existing Obsidian
knowledge-base export/sync subsystem and define how database source overrides
represent filesystem-only configuration.

**Acceptance Outcomes:**
- Obsidian ingestion is represented in `SOURCE_REGISTRY`, generated contracts, CLI,
  HTTP, MCP, worker dispatch, and capability-driven UI.
- MCP and CLI submissions return the same durable operation shape as other sources.
- Fixture and real-ingestion tiers cover path validation, incremental ingestion,
  idempotency, and failure reporting.
- Vault ingress does not reuse or blur the ownership of knowledge-base export/sync.

### Capability: Reconcile and archive stale OpenSpec inventory

Verify current implementation evidence and close planning drift. Archive completed
`add-ingestion-filtering-prioritization` and `db-source-overrides`; verify and
reconcile `add-huggingface-papers-source`, `llm-router-evaluation`, and
`use-paradedb-railway-langfuse-default`; archive `unify-mcp-ingest-envelope` as
superseded by durable operations. Extract only genuine remaining work into focused
follow-up changes.

**Acceptance Outcomes:**
- Completed and superseded changes are verified, task states reconciled, and archived
  with no implementation work repeated.
- ParadeDB/Langfuse external deployment evidence and the container image-name mismatch
  are resolved or captured as a focused blocker.
- Any remaining LLM routing work is represented as a smaller production-reachability
  change rather than reopening all completed foundation tasks.
- The active OpenSpec list contains only actionable, schema-valid changes.

### Capability: Gate API versioning on a concrete compatibility need

Reassess `add-api-versioning` after the current canonical clients, release smoke
tests, and deprecation boundaries are stable. Refine it around an identified v2
contract or archive/defer it if no concrete compatibility requirement exists.

**Acceptance Outcomes:**
- A written decision identifies the first incompatible contract requiring a new API
  version, or records why versioning remains deferred.
- Any retained proposal describes migration, deprecation, generated-client, and
  cross-surface compatibility behavior against the durable workflow contract.
- No speculative 42-task implementation begins without an executable compatibility
  case.

## Constraints

- All long-running workflows must return and persist the canonical durable
  `OperationHandle`; no transport-specific execution path may be introduced.
- CLI, HTTP, MCP, worker, and frontend behavior must derive from the shared workflow
  contracts, `SOURCE_REGISTRY`, and typed request models.
- Generated contract files remain checked in, and drift validation must run where
  the complete generation toolchain is available.
- Tests must assert serialized network behavior at real transport boundaries rather
  than normalizing malformed requests in mocks.
- Mutating E2E and gen-eval scenarios must default to staging or ephemeral
  infrastructure, never production.
- Existing `pgqueuer_jobs` state, checkpoints, idempotency, retries, cancellation,
  and persisted results must be reused before adding storage or queue models.
- Each roadmap item must be independently reviewable as one OpenSpec change; large
  reliability proposals must be refined before implementation.
- Production deployments, alerts, and credentialed adapter tests require explicit
  environment evidence and must not expose secrets in logs or reports.

## Phases

### Phase 0: Restore operator surfaces and planning truth

- Repair canonical CLI HTTP behavior.
- Restore the Railway frontend deployment contract.
- Reconcile and archive stale OpenSpec inventory.

### Phase 1: Guard the release and real workflow boundaries

- Add cross-surface release compatibility smoke tests.
- Implement real ingestion test tiers in CI.
- Establish gen-eval coverage for the CLI workflow contract.

### Phase 2: Complete the ingestion reliability model

- Reconcile persisted ingestion result requirements.
- Reconcile stuck content with durable operations.
- Add production terminal-state telemetry and alerts.

### Phase 3: Expand sources and settle deferred compatibility work

- Add Obsidian vault ingestion through the source registry.
- Gate API versioning on a concrete compatibility need.

## Out of Scope

- Reintroducing retired synchronous ingestion, task-status, or transport-specific
  mutation endpoints.
- Reimplementing completed filtering, database source overrides, HuggingFace source,
  LLM routing foundation, ParadeDB/Langfuse configuration, or MCP ingestion envelope
  work.
- Adding new ingestion-run tables before existing durable operation persistence is
  shown to be insufficient.
- Running mutating verification against production without separate explicit
  authorization.
- Implementing speculative API versioning without a concrete incompatible contract.
