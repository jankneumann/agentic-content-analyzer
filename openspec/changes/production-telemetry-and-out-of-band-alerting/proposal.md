# Change: Add terminal-state telemetry and alerts

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `production-telemetry-and-out-of-band-alerting`
> Effort: L
> Priority: 9

## Summary

Instrument canonical workflow terminal transitions and deliver deduplicated
out-of-band alerts for failures, partial sources, zero-item outcomes, and
reconciliation events. Define a sink boundary with safe retries, idempotency,
diagnostic links, redaction, and secret handling.

## Dependencies

- `ri-07`
- `ri-08`

## Acceptance Outcomes

- All relevant terminal and reconciliation outcomes emit structured telemetry.
- At least one configured out-of-band sink receives deduplicated failure alerts
  and retries without duplicate notifications.
- Payloads identify operation, workflow, and affected resources only through
  opaque allowlisted identifiers, plus a stable same-origin diagnostic link
  stripped of query and fragment data.
- Deterministic tests cover classification; secret, PII, and user-content
  redaction; URL sanitization; retry; and idempotency.
- Staging proves terminal telemetry and external alert delivery.

## Rationale

Production reliability needs external notification derived from the same typed
durable results used for recovery.
