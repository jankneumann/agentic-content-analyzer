# Tasks: Production telemetry and out-of-band alerting

> Change ID: `production-telemetry-and-out-of-band-alerting`
> Execution tier: coordinated
> Selected approach: transactional terminal-event outbox plus HTTPS webhook

## Status

- [x] Planning
- [ ] Implementation
- [ ] Testing
- [ ] Review
- [ ] Done

## 1. Closed contracts and policy

- [ ] 1.1 [S] Write contract tests for the alert envelope and staging-evidence schemas, including all bounds and forbidden extension fields
  **Spec scenarios**: Unexpected field is presented; Controlled staging alert arrives
  **Contracts**: `contracts/workflow-alert-envelope.schema.json`, `contracts/staging-evidence.schema.json`
  **Dependencies**: None
- [ ] 1.2 [M] Add strict terminal event, safe envelope, delivery, and staging-evidence models to canonical Python contracts
  **Dependencies**: 1.1
- [ ] 1.3 [S] Write settings tests for default-off sink policy, trusted diagnostic origin, endpoint/host safety, secret types, and retry/lease/retention bounds
  **Spec scenarios**: Webhook alerting is disabled; Webhook configuration is unsafe; Link input contains an untrusted component
  **Design decisions**: D4, D5, D8, D9
  **Dependencies**: None
- [ ] 1.4 [S] Implement validated alert policy settings without database-backed secret registration
  **Dependencies**: 1.3

- [ ] Checkpoint: run contract/settings tests and verify secret fields are absent from settings APIs

## 2. Additive terminal-event persistence

- [ ] 2.1 [M] Write migration/bootstrap tests for append-only event/delivery constraints, operation terminal trigger coverage, reconciliation action trigger coverage, retention indexes, and downgrade
  **Spec scenarios**: Terminal transition commits; Stale claim loses its terminal race; Apply commits an action; Apply action rolls back
  **Contracts**: `contracts/db/schema.sql`
  **Dependencies**: 1.2
- [ ] 2.2 [M] Add Alembic, ORM, and queue-bootstrap persistence for terminal events, deliveries, and trigger functions
  **Dependencies**: 2.1
- [ ] 2.3 [S] Write PostgreSQL tests proving duplicate terminal updates/actions cannot duplicate event intent and retained events survive operation cleanup
  **Spec scenarios**: Apply is repeated; Terminal intent cannot be persisted
  **Design decisions**: D1, D2, D9
  **Dependencies**: 2.2

- [ ] Checkpoint: inspect trigger SQL, upgrade/downgrade, uniqueness, and bounded due-delivery query plan

## 3. Classification, safe projection, and telemetry

- [ ] 3.1 [M] Write pure table tests for lifecycle/result precedence across success, partial, zero-item, failed, cancelled, unknown, pipeline aggregation, retries, and reconciliation
  **Spec scenarios**: all scenarios under Terminal outcomes use a closed classification policy and Alert routing bounds operation graph noise
  **Dependencies**: 1.2
- [ ] 3.2 [M] Implement the closed classifier from fresh persisted state and immutable reconciliation evidence
  **Dependencies**: 2.2, 3.1
- [ ] 3.3 [M] Write sentinel and property tests proving secrets, PII, user content, natural source keys, raw errors, arbitrary URLs, and extension fields cannot enter safe projection
  **Spec scenarios**: Typed ingestion evidence contains hostile diagnostics; Unexpected field is presented
  **Dependencies**: 1.2
- [ ] 3.4 [M] Implement allowlist-first envelope projection and strict same-origin diagnostic URL construction
  **Dependencies**: 3.2, 3.3
- [ ] 3.5 [S] Write telemetry tests for stable event names, low-cardinality dimensions, correlation fields, disabled OTel, and exporter failure
  **Spec scenarios**: Terminal telemetry is emitted; OTel is disabled or rejects export
  **Dependencies**: 3.2
- [ ] 3.6 [S] Implement structured terminal logs/OTel emission plus idempotent telemetry checkpoints
  **Dependencies**: 3.4, 3.5

- [ ] Checkpoint: run classifier/redaction/telemetry tests and inspect every emitted attribute

## 4. Leased webhook delivery

- [ ] 4.1 [M] Write repository tests for due-row `SKIP LOCKED` claims, lease recovery, concurrent workers, delivery uniqueness, and pending/exhausted retention
  **Spec scenarios**: Worker dies around an ambiguous response; Delivery reaches its retry ceiling
  **Dependencies**: 2.2
- [ ] 4.2 [M] Implement delivery repository claims, state transitions, retry schedule, and bounded cleanup
  **Dependencies**: 4.1
- [ ] 4.3 [M] Write HTTP adapter tests for 2xx, permanent 4xx, 408/429/5xx, bounded `Retry-After`, timeout, redirects, DNS/address policy, HMAC, response-size limits, and log redaction
  **Spec scenarios**: Transient delivery fails and then succeeds; Webhook configuration is unsafe
  **Dependencies**: 1.4
- [ ] 4.4 [M] Implement the `AlertSink` protocol and noop/webhook adapters with stable `Idempotency-Key`
  **Dependencies**: 3.4, 4.3
- [ ] 4.5 [M] Write drain-loop tests covering projection, telemetry-only events, graph suppression, crash windows, exhausted delivery, and graceful shutdown
  **Spec scenarios**: Multiple pipeline children fail; Retried operation fails again; Webhook alerting is disabled
  **Dependencies**: 3.6, 4.2, 4.4
- [ ] 4.6 [M] Integrate the bounded terminal-event/delivery drain into worker maintenance
  **Dependencies**: 4.5

- [ ] Checkpoint: run concurrent Postgres plus MockTransport suites and verify no transaction spans network I/O

## 5. Canonical transition and reconciliation integration

- [ ] 5.1 [M] Write end-to-end operation tests covering worker completion/failure, queued/running cancellation, handler-owned terminal state, maintenance failure, stale claims, and fresh persisted V2 result reads
  **Spec scenarios**: all scenarios under Canonical terminal transitions persist event intent and Terminal projection reads committed state
  **Dependencies**: 2.2, 3.2
- [ ] 5.2 [S] Reconcile legacy job notifications so external routing never consumes generic raw title/summary/payload fields
  **Spec scenarios**: Generic notification contains unsafe fields; No SSE subscriber is connected
  **Dependencies**: 5.1
- [ ] 5.3 [M] Write reconciliation integration tests for atomic action intent, apply rollback, bounded `apply_failed`, repeat/concurrent apply, and dry-run purity
  **Spec scenarios**: all scenarios under Reconciliation telemetry follows committed action evidence
  **Dependencies**: 2.2, 3.2
- [ ] 5.4 [M] Add safe post-rollback reconciliation failure intent while preserving transactional action-trigger evidence
  **Dependencies**: 5.3
- [ ] 5.5 [M] Run operation graph and reconciliation concurrency regressions with retention active
  **Dependencies**: 4.6, 5.2, 5.4

- [ ] Checkpoint: compare terminal/action rows to event and delivery identities under forced races

## 6. Verification, documentation, and closeout

- [ ] 6.1 [M] Write verifier tests for deadline, schema validation, receiver deduplication, receipt hashing, redaction assertions, and safe failure output
  **Spec scenarios**: Controlled staging alert arrives; Staging receipt is missing or duplicated
  **Dependencies**: 1.2, 4.6
- [ ] 6.2 [M] Implement the non-production idempotent receiver fixture and sanitized staging verification command/evidence path
  **Dependencies**: 6.1
- [ ] 6.3 [S] Document configuration, secret provisioning, receiver idempotency contract, retry/exhaustion operations, staging procedure, and rollback
  **Spec scenarios**: all
  **Design decisions**: D1-D10
  **Dependencies**: 5.5, 6.2
- [ ] 6.4 [M] Run strict OpenSpec, contract drift, migration, lint, full test, security, query-plan, and staging verification gates
  **Dependencies**: 6.3

- [ ] Checkpoint: review cumulative diff, verify task/spec traceability, and record sanitized staging evidence

## Dependency Summary

- Independent roots: 1.1, 1.3
- Sequential chains: contracts -> persistence -> classification/projection -> integration -> staging
- Parallel branches after persistence: classification/telemetry and delivery repository/transport
- Maximum package parallel width: 2
- Shared-file conflicts: contracts precede all consumers; worker drain follows classifier and delivery repository; reconciliation integration follows persistence/classifier
- Task sizes: S=9, M=19, L=0, XL=0
