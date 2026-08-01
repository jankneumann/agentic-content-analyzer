# Tasks: Stuck-content sweeper and requeue CLI

> Change ID: `stuck-content-sweeper-and-requeue-cli`
> Execution tier: coordinated
> Selected approach: persisted-owner bounded reconciliation

## Status

- [x] Planning
- [ ] Implementation
- [ ] Testing
- [ ] Review
- [ ] Done

## 1. Wire contracts plus policy

- [x] 1.1 [S] Write reconciliation contract equivalence tests covering requests, reports, safe fields, closed counters, response semantics
  **Spec scenarios**: Scanning and reports are strictly bounded; Dry-run is reconciliation-read-only; Canonical remote controls expose reconciliation
  **Contracts**: `contracts/reconciliation-report.schema.json`, canonical content-workflow OpenAPI
  **Design decisions**: D8, D9, D10
  **Dependencies**: None
- [x] 1.2 [M] Extend canonical OpenAPI plus generated reconciliation models
  **Dependencies**: 1.1
- [ ] 1.3 [S] Write reconciliation policy setting tests covering defaults, bounds, cross-field validation, default-off apply
  **Spec scenarios**: Retry is canonical and atomically budgeted; Stale apply is locked and protocol-gated
  **Design decisions**: D7, D11
  **Dependencies**: None
- [ ] 1.4 [S] Implement validated reconciliation policy settings
  **Dependencies**: 1.3

- [ ] Checkpoint: run contract/settings tests, review diff, verify package scope

## 2. Additive persistence foundation

- [ ] 2.1 [M] Write migration/bootstrap tests covering generation/protocol triggers, owner versions, compatible phase checks, Summary provenance, append-only action constraints, downgrade
  **Spec scenarios**: Supported transitions persist exact ownership; Claim generations fence every attempt; Apply action evidence is atomic
  **Contracts**: `contracts/db/schema.sql`
  **Design decisions**: D1, D2, D3, D9
  **Dependencies**: 1.1
- [ ] 2.2 [M] Add ownership/provenance/action schema through Alembic, ORM models, queue bootstrap
  **Dependencies**: 2.1

- [ ] Checkpoint: run migration/bootstrap tests, inspect upgrade/downgrade, verify no destructive foreign keys

## 3. Durable execution fencing

- [ ] 3.1 [M] Write queue lifecycle tests covering trigger generations, every requeue/defer protocol reset, old-worker claims, stale heartbeat/progress writes, late terminal writes
  **Spec scenarios**: all scenarios under Claim generations fence every attempt
  **Design decisions**: D2
  **Dependencies**: 2.2
- [ ] 3.2 [M] Implement shared claim context plus generation-guarded queue lifecycle writes
  **Dependencies**: 3.1
- [ ] 3.3 [M] Write transition-writer tests covering initial acquisition, N-to-N+1 renewal, validated/missing/ambiguous URL resume, legacy extraction, Summary provenance, unsupported-writer trigger clearing, cancellation outcomes, superseded commits
  **Spec scenarios**: Canonical URL extraction records parsing ownership; Initial phase ownership is acquired; Retried claim renews same-operation ownership; Canonical URL extraction failure is checkpointed; Canonical URL retry resumes exact Content; Canonical URL resume checkpoint is validated; Worker dies before attaching URL checkpoint; URL resume evidence is ambiguous; Summary leaf records processing ownership; Unsupported writer leaves owner fields unchanged; Old computation outlives its claim; Cancellation exists before handler dispatch; Cancellation races ongoing computation
  **Design decisions**: D1, D3, D4, D5
  **Dependencies**: 2.2
- [ ] 3.4 [M] Add guarded domain acquisition/commit primitives, typed claim outcomes, ownership-clearing parity hook
  **Dependencies**: 3.3
- [ ] 3.5 [M] Guard URL extraction transitions plus exact-content resume checkpoints
  **Dependencies**: 3.4
- [ ] 3.6 [M] Guard summarization transitions plus Summary provenance
  **Dependencies**: 3.4
- [ ] 3.7 [M] Serialize guarded domain commits with the content transaction lock
  **Dependencies**: 3.2, 3.4

- [ ] Checkpoint: run worker/domain concurrency tests, force reclaim during computation, verify superseded attempts cannot commit

## 4. Atomic retry primitive

- [ ] 4.1 [M] Write retry tests covering atomic ceiling, public compatibility, closed URL checkpoint validation/preservation, malformed result clearing, transactional notification, graph lock order, concurrent callers
  **Spec scenarios**: all scenarios under Retry is canonical and atomically budgeted; Internal retry supports an optional atomic ceiling; Retry preserves a resumable operation result
  **Design decisions**: D6, D7
  **Dependencies**: 2.2
- [ ] 4.2 [M] Refactor canonical retry around the connection-scoped locked primitive plus conditional URL checkpoint preservation
  **Dependencies**: 4.1

- [ ] Checkpoint: run operation retry/retention tests, review lock order, verify checkpoint preservation

## 5. Reconciliation core

- [ ] 5.1 [M] Write classifier tests covering every matrix row, precedence, ownership conflicts, force, cancellation, protocol mismatch
  **Spec scenarios**: all content-state-reconciliation classification scenarios
  **Contracts**: `contracts/reconciliation-report.schema.json`, `contracts/db/schema.sql`
  **Design decisions**: D1-D5, D10, D11
  **Dependencies**: 2.2
- [ ] 5.2 [M] Implement the fail-closed reconciliation classifier
  **Dependencies**: 5.1
- [ ] 5.3 [M] Write PostgreSQL service tests covering dry-run purity, single-connection apply, row revalidation, stale parsing/processing recovery, audit rollback, per-item continuation, repeated apply
  **Spec scenarios**: Dry-run observes a repairable row; Apply commits one action; Abandoned stale owner is recovered; Retried stale parsing owner resumes; Retried stale processing owner resumes; Action audit insertion fails; One item fails within a page; Apply is repeated
  **Design decisions**: D6, D8, D9
  **Dependencies**: 3.7, 4.2, 5.1
- [ ] 5.4 [M] Implement bounded read-only reconciliation scanning
  **Dependencies**: 5.2, 5.3
- [ ] 5.5 [M] Implement locked protocol-gated reconciliation apply
  **Dependencies**: 3.7, 4.2, 5.3, 5.4
- [ ] 5.6 [M] Write the 10,001-row ownership query-plan regression
  **Spec scenarios**: Candidate tables contain 10,001 irrelevant rows
  **Design decisions**: D10
  **Dependencies**: 5.4
- [ ] 5.7 [S] Add only ownership indexes justified by the measured plan
  **Dependencies**: 5.6

- [ ] Checkpoint: run service/query-plan tests, compare dry-run state snapshots, inspect action-audit constraints

## 6. Canonical API plus CLI

- [ ] 6.1 [S] Write API tests covering authentication, validation, default preview, disabled apply, bounded reports, request audit notes
  **Spec scenarios**: all scenarios under Stale apply is locked and protocol-gated; Canonical remote controls expose reconciliation
  **Contracts**: canonical content-workflow OpenAPI
  **Dependencies**: 1.2, 5.5
- [ ] 6.2 [S] Add the authenticated audited reconciliation endpoint
  **Dependencies**: 6.1
- [ ] 6.3 [S] Write client/CLI tests covering one-page transport, apply, continuation, safe JSON, exact exit policy
  **Spec scenarios**: CLI pagination is requested; Default CLI invocation previews; CLI apply contains item failures
  **Contracts**: canonical content-workflow OpenAPI
  **Dependencies**: 6.2
- [ ] 6.4 [S] Add WorkflowApiClient reconciliation plus the operations CLI command
  **Dependencies**: 6.3

- [ ] Checkpoint: run API/client/CLI tests, verify remote-only behavior, inspect problem responses

## 7. Integration evidence

- [ ] 7.1 [S] Write CLI gen-eval scenarios covering preview, disabled apply, guarded apply, safe JSON
  **Spec scenarios**: Default CLI invocation previews; CLI apply contains item failures
  **Dependencies**: 6.4
- [ ] 7.2 [S] Add the checked-in reconciliation gen-eval cases
  **Dependencies**: 7.1
- [ ] 7.3 [M] Run canonical URL recovery end-to-end regression
  **Spec scenarios**: Canonical URL extraction failure is checkpointed; Canonical URL retry resumes exact Content; Failed exact owner remains within budget
  **Dependencies**: 5.5, 6.2
- [ ] 7.4 [S] Update operator documentation plus canonical specification reconciliation notes
  **Spec scenarios**: all
  **Design decisions**: D1-D11
  **Dependencies**: 5.7, 7.2, 7.3
- [ ] 7.5 [M] Run final quality gates plus independent security/concurrency review
  **Dependencies**: 7.4

- [ ] Checkpoint: review cumulative diff, confirm task/spec traceability, record final validation evidence

## Dependency Summary

- Independent roots: 1.1, 1.3
- Sequential chains: contracts -> schema -> fence/core -> surfaces -> integration
- Parallel branches: none; shared OperationService and worker lifecycle changes are intentionally sequenced
- Maximum package parallel width: 1
- Shared-file conflicts: operation lifecycle/retry precedes domain fencing; migration owners precede all consumers
- Task sizes: S=11, M=20, L=0, XL=0
