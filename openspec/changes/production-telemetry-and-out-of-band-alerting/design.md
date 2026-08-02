# Design: Durable terminal telemetry and webhook alerts

## Context

`pgqueuer_jobs` is the canonical operation state machine. Its terminal writes
are generation-fenced, but they occur through worker success/failure,
cancellation, and maintenance paths. Handlers may attach a typed V2 result after
the worker's original payload snapshot was read. Reconciliation is atomic per
content action and already persists an immutable `(run_id, content_id)` action
record.

The current `NotificationDispatcher` creates an unrelated random event in a
separate transaction and pushes only to process-local SSE subscribers. External
alerting needs a different durability, classification, redaction, retry, and
secret boundary.

## Goals

- Capture every authoritative operation attempt terminal transition exactly
  once without requiring every caller to remember an application hook.
- Classify only from committed lifecycle state and strict persisted results.
- Emit safe structured telemetry for all supported outcomes.
- Deliver actionable outcomes through one durable idempotent webhook boundary.
- Preserve terminal-state progress when telemetry exporters or sinks fail.
- Correlate staging evidence without persisting or printing sensitive data.

## Non-Goals

- Replace in-app notification history or SSE.
- Promise network-level exactly-once delivery to a receiver that ignores
  idempotency keys.
- Add a user-configurable webhook API, UI, SendGrid email, APNs, or FCM.
- Export raw operation input, result, problem detail, errors, content, source
  locators, URLs, prompts, or sink responses.
- Emit events from reconciliation dry-run or create a reconciliation run state
  machine.

## Decisions

### D1: Database triggers capture minimal terminal intent

An additive trigger on `pgqueuer_jobs` inserts one `workflow_terminal_events`
row whenever status changes into `completed`, `failed`, or `cancelled`. Its
unique identity is `operation:{id}:claim:{claim_generation}:status:{status}`.
The trigger copies only numeric operation ID, claim generation, terminal status,
and timestamp. It does not classify JSON in SQL.

This covers worker transitions, queued and running cancellation, handler-owned
terminal transitions, and maintenance paths. Python later locks the event and
reads the committed operation payload/result to create the closed projection.
The unique key makes repeated updates and old-worker races harmless.

Alternative: call an emitter after each transition. Rejected because existing
terminal paths already demonstrate bypasses and a crash after commit loses the
event.

### D2: Reconciliation uses immutable action identity

A trigger on `content_reconciliation_actions` inserts terminal intent keyed by
`reconciliation-action:{action_id}` in the same transaction as the mutation and
action audit. Dry-run stays read-only. An `apply_failed` item rolls back first,
then records a bounded failure event keyed by `(run_id, content_id,
apply_failed)` in its own short transaction; it never records a false applied
action. Clean no-op/conflict preview rows remain report-only.

Alternative: emit one page summary after reconciliation returns. Rejected
because a process crash can commit actions but lose the page event.

### D3: One closed classifier owns outcome and routing

The classifier reads fresh persisted operation state. Lifecycle `failed` and
`cancelled` take precedence. Completed ingestion and pipeline operations accept
only strict V2 results; they preserve `success`, `partial`, `zero_items`, or
`unknown`. Other completed workflows classify as `success`. Reconciliation
actions classify as `reconciled`; `apply_failed` classifies as `failed`.

Severity and sink policy are closed:

| Outcome | Telemetry | Severity | External alert |
|---|---|---:|---|
| success | yes | info | no |
| cancelled | yes | info | no |
| unknown | yes | warning | yes |
| partial | yes | warning | yes |
| zero_items | yes | warning | yes |
| reconciled action | yes | warning | yes |
| failed / apply_failed | yes | error | yes |

For an operation graph, leaf events still produce telemetry. External routing is
suppressed for a leaf whose terminal pipeline root is expected to aggregate the
outcome; the root alert contains bounded opaque child/source summaries. A leaf
without a pipeline root remains independently alertable. Recovery success does
not send a second external alert.

Alternative: alert every failed child immediately. Rejected because a pipeline
fan-out can turn one incident into an unbounded alert storm.

### D4: Safe envelopes are allowlist-first and versioned

`WorkflowAlertEnvelopeV1` is `extra=forbid` and bounded by the checked-in JSON
Schema. It contains an event ID/key, occurrence time, severity, outcome,
operation type, attempt number, opaque operation/resource/source references,
safe counts and diagnostic codes, and one diagnostic URL. It never accepts a
generic payload mapping.

Diagnostic URLs are constructed from a configured public origin plus an
allowlisted route. The origin must be HTTPS in production and contain no
userinfo, path, query, or fragment. Operation links are exactly
`/api/v1/operations/{positive-id}`; reconciliation links are exactly an
authenticated terminal-event route. Query, fragment, traversal, encoded slash,
and caller-supplied URLs are rejected rather than cleaned in place.

Alternative: recursively redact the stored operation payload. Rejected because
denylist redaction cannot establish that unknown future fields are safe.

### D5: The first sink is a constrained HTTPS webhook

`AlertSink` receives an already-validated envelope and stable delivery key. The
initial webhook adapter sends JSON with `Idempotency-Key`; it may attach an HMAC
signature from a secret resolved only through settings environment/profile/
secret-provider sources. Redirects are disabled. Production endpoints must use
HTTPS, contain no credentials, and match configured outbound host policy;
loopback, private, link-local, and metadata addresses fail closed unless an
explicit development/test mode is active. Request/response bodies and auth
material are never logged.

Alternative: SendGrid email. Rejected for v1 because no sender/recipient model
or receiver idempotency contract exists despite the installed dependency.

### D6: Delivery is leased, bounded, and at-least-once

`workflow_alert_deliveries` has one row per `(event_id, sink_name)`. Workers
claim due rows with `FOR UPDATE SKIP LOCKED`, set a recoverable lease, perform
network I/O outside the claim transaction, then persist success or a closed
error code. A 2xx response succeeds; 408, 429, 5xx, timeouts, and connection
errors retry with bounded exponential backoff and optional bounded
`Retry-After`; other 4xx responses are permanent. Attempts and age are capped;
exhaustion remains queryable and emits local error telemetry without recursively
creating another alert.

If a worker loses an HTTP response, it retries with the same idempotency key.
The receiver must collapse that key; staging verifies one receiver receipt.

Alternative: hold a database transaction across the HTTP call. Rejected because
it consumes connections, prolongs locks, and still cannot resolve an ambiguous
response.

### D7: Telemetry is derived and never authoritative

Committed terminal events emit a structured log and OTel event/metrics using
only `workflow.operation_type`, `workflow.outcome`, `workflow.severity`, and
`workflow.source_kind`; event correlation IDs remain log fields, not metric
labels. OTel-disabled and exporter-failure paths retain outbox state and do not
change operation/reconciliation state. A `telemetry_emitted_at` checkpoint makes
normal replay idempotent; exporters may still observe a duplicate across the
crash window and correlate it by event key.

Alternative: emit current `record_pipeline_stage_failed(error=...)` metrics.
Rejected because raw errors are sensitive and high-cardinality.

### D8: Configuration is default-off and secrets are not database settings

Validated settings define sink selection (`noop|webhook`), endpoint, secret,
trusted diagnostic origin, host allowlist, timeout, lease, attempt, backoff, and
retention bounds. Alerting defaults to `noop`. Secrets use secret types and are
not registered with `SettingsService` or its override API. Enabling webhook
requires all trusted-origin and endpoint invariants at startup.

Alternative: allow runtime database overrides. Rejected because the generic
settings API stores and returns plaintext values.

### D9: Retention never destroys workflow authority

Terminal events and deliveries use copied identifiers without destructive
foreign keys. Delivered/permanent events are retained for 30 days and exhausted
events for 90 days by default; pending/leased records are never retention
candidates. Cleanup is bounded and leader-elected alongside existing worker
maintenance. Operation retention therefore cannot orphan or cascade-delete
alert evidence.

### D10: Staging evidence is a sanitized correlation manifest

A verification command creates controlled partial/zero/failed cases against a
non-production idempotent receiver, waits within a fixed deadline, and writes a
schema-validated manifest. The manifest includes revision, environment class,
opaque operation/attempt and event IDs, outcome/severity, persisted and receipt
timestamps, hashed receiver receipt ID, delivery count, and boolean redaction
assertions. It excludes endpoint, headers, body, operation inputs/results,
errors, source locators, and secrets.

Alternative: capture webhook request/response fixtures. Rejected because those
artifacts can expose credentials or user content.

## Risks and Trade-offs

- Trigger-backed intent adds migration complexity but closes otherwise
  untestable bypass/crash windows.
- At-least-once delivery relies on receiver idempotency for duplicate-free user
  experience; this is explicit and verified rather than overstated.
- Root aggregation delays some child alerts until the pipeline root terminates,
  trading immediacy for bounded operator noise.
- DNS rebinding cannot be eliminated by string validation alone; the adapter
  resolves and validates each connection target and disables redirects.

## Rollout

1. Apply additive tables/triggers with sink `noop`.
2. Deploy classifier, telemetry, and delivery drain; verify no raw values in
   structured logs and inspect bounded query plans.
3. Configure trusted origin, webhook endpoint, host allowlist, and secret in
   staging; run sanitized verification.
4. Enable production webhook and monitor pending/exhausted delivery gauges.
5. Roll back by selecting `noop`; retain durable evidence for diagnosis.
