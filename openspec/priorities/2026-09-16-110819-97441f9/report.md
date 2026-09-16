# Proposal Prioritization Report

**Run ID**: 2026-09-16-110819-97441f9
**Generated**: 2026-09-16T11:08:19Z
**Analyzed Range**: `HEAD~50..HEAD` (50 commits)
**Proposals Analyzed**: 9
**Format**: Markdown
**Retention**: Keep 30 dated runs

## Executive Recommendation

Refine and implement `closeout-db-source-overrides-evidence` next. It is the
smallest still-relevant residual proposal, has no external authority blocker,
and closes contract, UI, migration, and operator-documentation evidence around
an already-shipped capability.

In parallel, verify and archive `establish-cli-gen-eval-coverage`: 47 of 48
checkboxes are complete, all implementation tasks are checked, the only open
box is the archive-time `Done` marker, and a recent commit updated its CLI
descriptor for the backup command group. Do not reopen its implementation.

The last 50 commits are dominated by backup/restore delivery, agent-skill
updates, logging/contract hardening, and RSS/blog ingestion fixes. They do not
implement the remaining source-override, filtering, production
ParadeDB/Langfuse, or deployable LLM-routing work.

## Priority Order

### 1. `closeout-db-source-overrides-evidence` — Close out database source override evidence

- **Relevance**: Still Relevant — the source override runtime exists, but the
  proposal's contract alignment, settings UI evidence, executable migration
  proof, and operator documentation remain unchecked. The only recent nearby
  edit was an unrelated JS-blog/RSS fallback in `src/config/sources.py`.
- **Readiness**: Needs Planning (0/6 tasks complete; proposal, design, tasks,
  and strict-valid spec delta present). The nested-versus-top-level source
  discriminator still needs a recorded decision before implementation.
- **Scope**: Small residual closeout.
- **Conflicts**: Direct overlap with
  `reconcile-ingestion-filtering-runtime-contract` on source configuration,
  command/API contracts, and source-facing UI; direct overlap with the already
  completed Obsidian proposal on source registry/UI fixtures.
- **Recommendation**: Refine first, then implement as the next delivery stream.
- **Next Step**: `/iterate-on-plan closeout-db-source-overrides-evidence`

### 2. `establish-cli-gen-eval-coverage` — Establish CLI gen-eval coverage

- **Relevance**: Likely Addressed — every implementation, test, review, and
  closeout task is checked; only the archive-time `Done` status remains open.
  Commit `1ca3f289` updated the descriptor inside the analyzed range, showing
  the landed capability is still being maintained.
- **Readiness**: Partially Ready (47/48 checkboxes complete). This is a
  verification/archive action, not an implementation stream.
- **Scope**: Very small closeout.
- **Conflicts**: Its descriptor and scenarios observe source, ingestion,
  operation, and reconciliation surfaces. Archive verification can run in
  parallel; implementation edits to those surfaces should update gen-eval
  coverage afterward.
- **Recommendation**: Confirm the merged CI result, check `Done`, verify, and
  archive.
- **Next Step**: `/openspec-verify-change establish-cli-gen-eval-coverage`

### 3. `reconcile-ingestion-filtering-runtime-contract` — Reconcile the ingestion filtering runtime contract

- **Relevance**: Still Relevant — no commits in the analyzed range touched
  `src/services/ingestion_filter.py`, `src/ingestion/filter_hook.py`, or
  `settings/filtering.yaml`; the unresolved source/persona/command precedence,
  language-gate, dry-run, feedback, projection, and observability decisions
  remain.
- **Readiness**: Needs Planning (0/7 tasks complete; strict-valid proposal,
  design, tasks, and spec delta present). The design explicitly requires
  product and contract decisions before implementation.
- **Scope**: Medium cross-surface reconciliation.
- **Conflicts**: Source contracts/UI with #1; routing/model configuration with
  `operationalize-llm-evaluation-routing`; canonical ingestion outcomes with
  `persisted-ingestion-run-results`; content-state rules with the completed
  reconciliation proposal.
- **Recommendation**: Resolve the planning decisions after #1 fixes the source
  request/response contract.
- **Next Step**: `/iterate-on-plan reconcile-ingestion-filtering-runtime-contract`

### 4. `operationalize-llm-evaluation-routing` — Operationalize LLM evaluation and routing

- **Relevance**: Still Relevant — none of `src/services/llm_router.py`,
  `src/services/evaluation_service.py`, or `settings/models.yaml` changed in
  the analyzed range. Production router injection, effective DB-backed config,
  safe classifier artifacts, provenance-backed datasets, and bootstrap-free
  enablement remain unimplemented.
- **Readiness**: Needs Planning (0/8 tasks complete; strict-valid proposal,
  design, tasks, and spec delta present). The task list is outcome-oriented but
  lacks a detailed implementation graph for the security-sensitive artifact
  lifecycle and durable training boundary.
- **Scope**: Large and security-sensitive.
- **Conflicts**: Filtering/model configuration with #3; CLI/API/durable
  operations with the completed ingestion-result and telemetry proposals;
  Langfuse trace/config surfaces with production verification.
- **Recommendation**: Refine after the smaller source/filter contract work, or
  plan in parallel but do not implement shared config/API surfaces concurrently.
- **Next Step**: `/iterate-on-plan operationalize-llm-evaluation-routing`

### 5. `verify-production-paradedb-langfuse` — Verify production ParadeDB and Langfuse

- **Relevance**: Still Relevant — recent deployment documentation changes were
  backup/capture related and provide none of the required immutable-image,
  extension-version, BM25, or revision-correlated Langfuse evidence.
- **Readiness**: Blocked (0/7 tasks complete) on explicit production deployment
  authority for any Railway mutation. Read-only inventory and documentation
  alignment may proceed without that mutation.
- **Scope**: Small repository change with high external operational risk.
- **Conflicts**: Documentation and observability surfaces overlap #4 and the
  completed telemetry proposal; no material file conflict with #1.
- **Recommendation**: Prepare the read-only preflight and authority packet, but
  do not schedule a production cutover until scoped approval exists.
- **Next Step**: `/iterate-on-plan verify-production-paradedb-langfuse`

### 6. `persisted-ingestion-run-results` — Reconcile persisted ingestion results

- **Relevance**: Likely Addressed — all 36 checkboxes are complete, strict
  validation passes, and July/August history contains the typed outcome,
  history, retention, and validation commits. Recent contract changes add
  backup behavior rather than reopening ingestion-result scope.
- **Readiness**: Verification/cleanup (36/36 tasks complete).
- **Conflicts**: If reopened, it overlaps filtering and LLM-routing work on
  canonical ingestion/operation results, API/CLI contracts, and durable
  execution.
- **Recommendation**: Verify current contract parity and archive; do not
  reimplement.
- **Next Step**: `/openspec-verify-change persisted-ingestion-run-results`

### 7. `stuck-content-sweeper-and-requeue-cli` — Reconcile stuck content states

- **Relevance**: Likely Addressed — all 43 checkboxes are complete, strict
  validation passes, and implementation history records durable ownership,
  fencing, recovery, API/CLI controls, and end-to-end evidence. Recent backup
  work touched reconciliation logging and alert integration, so a focused
  regression verification is warranted before archival.
- **Readiness**: Verification/cleanup (43/43 tasks complete).
- **Conflicts**: Direct overlap with telemetry on reconciliation terminal
  events and with filtering on `FILTERED_OUT`/content-state rules.
- **Recommendation**: Run focused verification against the post-backup alert
  changes, then archive.
- **Next Step**: `/openspec-verify-change stuck-content-sweeper-and-requeue-cli`

### 8. `production-telemetry-and-out-of-band-alerting` — Add terminal-state telemetry and alerts

- **Relevance**: Likely Addressed — all 41 checkboxes are complete, strict
  validation passes, and the implementation/staging evidence landed before the
  analyzed range. The recent backup feature widened `system_check` terminal
  events and touched alert contracts, models, persistence, and tests.
- **Readiness**: Verification/cleanup (41/41 tasks complete).
- **Conflicts**: Direct overlap with #4 on failure/cost/observability semantics,
  with #5 on observability documentation, and with #7 on reconciliation events.
- **Recommendation**: Verify the widened terminal-event contract, then archive.
- **Next Step**: `/openspec-verify-change production-telemetry-and-out-of-band-alerting`

### 9. `add-obsidian-vault-ingest` — Add Obsidian Vault Ingestion

- **Relevance**: Likely Addressed — all 38 checkboxes are complete, strict
  validation passes, and history records parser, scanner, durable adapter,
  canonical source vertical, end-to-end tests, and documentation. A recent
  source-registry change and Obsidian sync test are adjacent but do not appear
  to invalidate the implementation.
- **Readiness**: Verification/cleanup (38/38 tasks complete).
- **Conflicts**: If reopened, direct source-registry, source configuration, UI,
  fixture, ingestion-result, and workflow overlaps with #1, #3, and #6.
- **Recommendation**: Verify registry and source-fixture parity, then archive.
- **Next Step**: `/openspec-verify-change add-obsidian-vault-ingest`

## Parallel Workstreams

### Stream A — Start immediately

- `closeout-db-source-overrides-evidence`: refine the discriminator/PATCH
  contract and implementation plan.
- `establish-cli-gen-eval-coverage`: verification and archival only.
- `persisted-ingestion-run-results`: verification and archival only.

### Stream B — After source-override contract decisions

- `reconcile-ingestion-filtering-runtime-contract`: refine, then implement.
- `production-telemetry-and-out-of-band-alerting`: verify/archive independently.
- `stuck-content-sweeper-and-requeue-cli`: verify/archive after telemetry
  contract verification.

### Stream C — Later independent work

- `operationalize-llm-evaluation-routing`: refine its security and durable-work
  design; implementation should wait until filtering config/API boundaries are
  stable.
- `add-obsidian-vault-ingest`: verify/archive after source-registry parity is
  checked.

### Sequential / Blocked

- `verify-production-paradedb-langfuse`: production mutation waits for explicit
  authority; read-only preflight may run in parallel.
- `reconcile-ingestion-filtering-runtime-contract` implementation waits for the
  source contract decision in `closeout-db-source-overrides-evidence`.
- `operationalize-llm-evaluation-routing` shared config/API implementation waits
  for filtering contract decisions.

## Conflict Matrix

Legend: `●` direct planned file/spec overlap, `○` adjacent integration or
documentation surface, `—` no material overlap. Completed proposals remain in
the matrix because verification and any reopening still touch shared surfaces.

| | SRC | GEN | FIL | LLM | PROD | RUN | STK | TEL | OBS |
|---|---|---|---|---|---|---|---|---|---|
| **SRC** | — | ○ | ● | ○ | ○ | ○ | — | — | ● |
| **GEN** | ○ | — | ○ | ○ | — | ● | ● | ○ | ○ |
| **FIL** | ● | ○ | — | ● | ○ | ● | ● | ○ | ● |
| **LLM** | ○ | ○ | ● | — | ● | ● | — | ● | — |
| **PROD** | ○ | — | ○ | ● | — | — | — | ○ | — |
| **RUN** | ○ | ● | ● | ● | — | — | ● | ● | ● |
| **STK** | — | ● | ● | — | — | ● | — | ● | ● |
| **TEL** | — | ○ | ○ | ● | ○ | ● | ● | — | ○ |
| **OBS** | ● | ○ | ● | — | — | ● | ● | ○ | — |

Abbreviations: SRC=`closeout-db-source-overrides-evidence`,
GEN=`establish-cli-gen-eval-coverage`,
FIL=`reconcile-ingestion-filtering-runtime-contract`,
LLM=`operationalize-llm-evaluation-routing`,
PROD=`verify-production-paradedb-langfuse`,
RUN=`persisted-ingestion-run-results`,
STK=`stuck-content-sweeper-and-requeue-cli`,
TEL=`production-telemetry-and-out-of-band-alerting`,
OBS=`add-obsidian-vault-ingest`.

### Highest-Risk Direct Overlaps

- Source overrides ↔ filtering/Obsidian: `src/config/sources.py`, source
  request/response contracts, settings UI, CLI commands, and source fixtures.
- Filtering ↔ LLM routing: effective model/config resolution and LLM-backed
  filter behavior.
- LLM routing ↔ production proof/telemetry: Langfuse observability, selected
  model/cost/failure semantics, settings, API/CLI, and durable operations.
- Gen-eval ↔ operation/reconciliation changes: descriptor drift plus scenarios
  for ingestion history and reconciliation controls.
- Persisted results ↔ telemetry/reconciliation: operation results, terminal
  lifecycle, retry, API/CLI projections, and retention.

## Proposals Needing Attention

### Likely Addressed — Verify and Archive

- `establish-cli-gen-eval-coverage`: 47/48; only archive-time `Done` remains.
- `persisted-ingestion-run-results`: 36/36.
- `stuck-content-sweeper-and-requeue-cli`: 43/43.
- `production-telemetry-and-out-of-band-alerting`: 41/41.
- `add-obsidian-vault-ingest`: 38/38.

### Needs Refinement

- `closeout-db-source-overrides-evidence`: decide the discriminator contract
  and convert six outcome tasks into an implementation/test sequence.
- `reconcile-ingestion-filtering-runtime-contract`: resolve precedence,
  language-gate, dry-run, feedback, projection, and observability decisions.
- `operationalize-llm-evaluation-routing`: detail the safe artifact lifecycle,
  provenance dataset, atomic enablement/rollback, and durable-work graph.

### Blocked

- `verify-production-paradedb-langfuse`: requires explicit production authority
  before any Railway mutation.

## Recent-History Evidence

- Range: `HEAD~50..HEAD`, exactly 50 commits, from parent
  `574d970473f1891ea487bec1340595fd9331b4ef` through `97441f97`.
- Core incomplete-proposal files with no commits in range:
  `src/services/ingestion_filter.py`, `src/ingestion/filter_hook.py`,
  `settings/filtering.yaml`, `src/services/source_override_service.py`,
  `web/src/components/settings/SourcesConfigurator.tsx`,
  `src/services/llm_router.py`, `src/services/evaluation_service.py`,
  `settings/models.yaml`, and `src/telemetry/providers/langfuse.py`.
- Relevant changes in range: `src/config/sources.py` for JS-blog/RSS fallback;
  `evaluation/descriptors/aca-cli.yaml` for the backup command group; workflow
  contracts, queue/reconciliation, and alert models for backup freshness;
  deployment docs for backup/capture updates.
- All nine active changes pass `openspec validate <change-id> --strict`.
- The pre-existing untracked merge-status cache files were not modified:
  `.agents/skills/merge-pull-requests/scripts/.status-cache.json` and
  `.claude/skills/merge-pull-requests/scripts/.status-cache.json`.
