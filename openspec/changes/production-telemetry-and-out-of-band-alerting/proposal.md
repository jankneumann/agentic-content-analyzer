# Change: Add terminal-state telemetry and alerts

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `production-telemetry-and-out-of-band-alerting`
> Execution tier: coordinated

## Why

Durable operations and reconciliation now preserve typed outcome evidence, but
production failures can still remain invisible unless an operator is watching
the in-process SSE feed. The current notification dispatcher commits in a
separate session, has no deduplication or retry state, and accepts raw titles,
errors, URLs, and payloads. It therefore cannot be the reliability or security
boundary for external alerts.

RI-09 makes each authoritative terminal transition leave durable, attempt-aware
evidence, emits bounded low-cardinality telemetry from that evidence, and sends
selected warning/error outcomes to one idempotent out-of-band sink.

## What Changes

- Add an append-only terminal-event outbox populated atomically from canonical
  operation terminal transitions and committed reconciliation actions.
- Add a closed classifier for success, partial, zero-item, cancelled, failed,
  unknown, and reconciliation outcomes. Typed V2 results take precedence over
  legacy inference; pipeline roots suppress redundant child alerts.
- Add a versioned, size-bounded external alert envelope containing only opaque
  identifiers, safe counters/codes, and a trusted same-origin diagnostic URL.
- Add a provider-neutral alert sink boundary and one configured HTTPS webhook
  implementation with stable idempotency keys, optional HMAC signing, bounded
  timeouts, no redirects, SSRF-safe destination validation, retry/backoff, and
  exhausted-delivery evidence.
- Drain outbox records with recoverable leases and `SKIP LOCKED`, while emitting
  structured logs and OTel telemetry that never affects workflow state.
- Keep generic in-app notification/SSE delivery separate and stop projecting raw
  operation errors or natural source identifiers into external alerts.
- Add authenticated diagnostic reads and sanitized staging evidence correlating
  persisted state, terminal event, telemetry classification, and one receiver
  receipt.

## Explicit Scope Decisions

- The first sink is an operator-configured HTTPS webhook. SendGrid remains
  outside this change because the repository has only an API-key dependency and
  no sender, recipient, delivery, or idempotency contract.
- Delivery is durable at-least-once. Duplicate-free retry across an ambiguous
  network response requires the receiver to honor the stable
  `Idempotency-Key`; staging must prove that behavior.
- Terminal-state persistence never depends on OTel or sink availability. The
  atomic obligation is durable outbox intent, not successful export.
- Dry-run reconciliation remains strictly read-only and emits no event. Apply
  actions use their append-only action identity; `apply_failed` is recorded only
  after the failed item transaction rolls back.
- No operator UI, arbitrary runtime webhook registration, email/push adapter, or
  second workflow state machine is introduced.

## Impact

- **Affected specs**: `production-workflow-alerting`, `agentic-operations`,
  `observability`, `content-state-reconciliation`, `notification-events`
- **Affected code**: queue terminal transitions and bootstrap, operation
  cancellation, reconciliation action persistence, terminal classifier/outbox,
  alert delivery worker, settings/secret validation, OTel/log projection,
  authenticated diagnostic routing, and staging verification
- **Persistence**: additive append-only terminal events and per-sink delivery
  attempts; no destructive foreign keys to retained operations/actions
- **Security**: allowlist-first payload construction; sink secrets remain in the
  environment/secret-provider chain and never enter database settings, logs,
  exceptions, evidence, or API responses
- **Compatibility**: existing operation, reconciliation, notification, and SSE
  response shapes remain compatible; disabled alerting is the default

## Acceptance Outcomes

- Success, partial, zero-item, cancelled, failed, and committed reconciliation
  outcomes emit durable structured terminal evidence and bounded telemetry.
- A configured webhook receives deduplicated warning/error alerts and retries
  transient delivery without multiple receiver-side notifications.
- Payloads identify workflow and affected resources only through opaque
  allowlisted identifiers and a trusted diagnostic link without secrets, PII,
  natural source keys, user content, raw errors, or arbitrary URLs.
- Deterministic tests cover classification, graph aggregation, redaction, URL and
  sink validation, concurrency, crash recovery, retry, exhaustion, and
  idempotency.
- Sanitized staging evidence proves persisted terminal state, telemetry
  classification, and one external alert receipt.
