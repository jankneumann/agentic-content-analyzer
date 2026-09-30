# Tasks: Classify session_expired in the terminal-event outbox

> Change ID: `classify-session-expired-in-the-terminal-event-outbox`

## 1. Closed code surfaces

- [x] 1.1 Admit `credentials_missing` and `session_expired` in `WorkflowAlertDiagnosticCode`
- [x] 1.2 Add both codes to the envelope schema `codes` enum
- [x] 1.3 Confirm no DB CHECK, telemetry grammar, or OpenAPI schema closes over codes (no migration, no regeneration)

## 2. Classification and projection

- [x] 2.1 Classify a failed `ingestion.execute` with `operation_failed` plus its attached result's codes
- [x] 2.2 Add the closed optional `remediation_command` to `WorkflowAlertEnvelopeV1` and the schema, omitted when absent
- [x] 2.3 Derive the command from `command_key` via `SESSION_REFRESH_COMMANDS`; point the Substack adapter and `BROWSER_SESSIONS` at the same table
- [x] 2.4 Route credential-remediation classifications past pipeline aggregation

## 3. Evidence artifact

- [x] 3.1 Record result diagnostic codes on `SourceEvidence` and render them with the refresh command
- [x] 3.2 Add `RealIngestionHarness.submit_with_orchestrator` for fail-closed adapters

## 4. Tests

- [x] 4.1 Real-emitter unit acceptance (`tests/unit/test_credential_failure_alert_emission.py`)
- [x] 4.2 PostgreSQL end to end: real Substack adapter, trigger, tick, webhook sink, one delivery, diagnostic routes (`tests/integration/test_credential_failure_alert_end_to_end.py`)
- [x] 4.3 Contract parity: codes, command literal, schema, `BROWSER_SESSIONS`
- [x] 4.4 Real-ingestion evidence records `session_expired` for substack

## 5. Validation

- [x] 5.1 ruff 0.15.15, mypy, alert/outbox/contract/integration/real-ingest suites, `generate_workflow_contracts.py --check`
- [x] 5.2 `openspec validate --strict`
