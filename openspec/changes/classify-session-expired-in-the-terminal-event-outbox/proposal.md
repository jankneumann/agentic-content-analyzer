# Classify session_expired in the terminal-event outbox

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `classify-session-expired-in-the-terminal-event-outbox`
> Effort: S
> Priority: 5

## Summary

Once the terminal-event outbox from production-telemetry-and-out-of-band-alerting exists, classify the session_expired readiness failure there so the alert names the exact aca auth session refresh command; until then, surface it through aca auth status and the scheduled real-ingestion evidence artifact.

## Dependencies

- `ri-05`
- `ri-06`

## Acceptance Outcomes

- The alert body for a session_expired failure contains the refresh command and no cookie value, proven with the real emitter rather than a stubbed telemetry_emitter.
- Before the outbox lands, the scheduled real-ingestion evidence artifact records the session_expired code for the affected source.

## Rationale

The proposal's end state is a yearly expiry announced by an alert that names the command to run; this item is gated on an external change and must not build the outbox itself.
