# Classify session_expired in the terminal-event outbox

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-16`)
> Change ID: `classify-session-expired-in-the-terminal-event-outbox`
> Depends on: `ri-05`, `ri-06`, `ri-18`, and the landed
> `production-telemetry-and-out-of-band-alerting` outbox

## Why

A browser session (Substack `substack.sid`, X `auth_token`/`ct0`) expires about
once a year. When it does, the credential-gated source fails closed with
`session_expired` (or `credentials_missing`) and persists nothing. The
terminal-event outbox existed, but the alert it produced said only
`operation_failed`, so the operator learned that something broke and not what to
run. Four closed points dropped the information on the way:

1. `WorkflowAlertDiagnosticCode` did not admit `session_expired` or
   `credentials_missing`, so `_ingestion_codes()` silently discarded them.
2. The ingestion handler attaches the result and *then* fails the operation, and
   `classify_terminal_event` classified a failed operation from its lifecycle
   alone (`codes=("operation_failed",)`), never reading the attached result.
3. `_apply_pipeline_routing` suppresses a failed pipeline child in favour of the
   root's aggregate alert, which carries no codes. The scheduled daily pipeline
   is exactly where a yearly expiry happens.
4. The published envelope schema's `codes` enum lacked both codes.

The scheduled real-ingestion evidence artifact had the same blind spot: it
recorded the source as an anonymous `adapter` failure.

## What Changes

- `WorkflowAlertDiagnosticCode` and the envelope schema `codes` enum admit
  `session_expired` and `credentials_missing`.
- A failed `ingestion.execute` operation is classified with `operation_failed`
  followed by the safe codes of its attached durable result.
- `WorkflowAlertEnvelopeV1` gains an optional, closed `remediation_command`
  (`aca auth session substack` | `aca auth session x`), present only on an
  ingestion operation alert whose codes name a credential failure and omitted
  otherwise, so every other alert serializes exactly as before. It is derived
  from the persisted `command_key` through one table,
  `SESSION_REFRESH_COMMANDS` in `src/ingestion/credential_failures.py`, which
  the Substack adapter and the `aca auth status` rows now also read.
- A classification that carries a `remediation_command` is routed on its own
  instead of being deferred to or suppressed by its pipeline root.
- `SourceEvidence` records the result's diagnostic codes, and the rendered
  failure-class summary shows them, with the refresh command for a credential
  failure.

No DB CHECK constraint, telemetry grammar, or OpenAPI schema closes over
diagnostic codes, so there is no migration and no regenerated contract.

## Impact

- Code: `src/contracts/workflow_alert_models.py`,
  `src/services/workflow_terminal_event_service.py`,
  `src/ingestion/credential_failures.py`, `src/ingestion/real_ingest_evidence.py`,
  `src/ingestion/substack.py`, `src/cli/browser_session_status.py`.
- Contracts: `workflow-alert-envelope.schema.json` (two codes, one optional
  property, one conditional rule); `backup-freshness-alert.schema.json` declares
  `remediation_command` as never present.
- Behaviour: failed ingestion alerts now list their result codes after
  `operation_failed`. Credential failures under a pipeline produce a child alert
  in addition to the root's aggregate alert.
- Tests: real-emitter unit acceptance, a PostgreSQL end-to-end test from the real
  Substack adapter to a real webhook sink and the diagnostic routes, contract
  parity tests, and real-ingestion evidence tests.
