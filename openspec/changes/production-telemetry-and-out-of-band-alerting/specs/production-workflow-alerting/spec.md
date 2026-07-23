## ADDED Requirements

### Requirement: Terminal workflow alerts are durable and deduplicated

Canonical success, partial, zero-item, cancelled, failed, and reconciliation outcomes SHALL
emit structured telemetry, and configured warning-or-higher events SHALL reach
an out-of-band sink with idempotent delivery.

#### Scenario: A durable operation fails

- **WHEN** an operation reaches a failed terminal state
- **THEN** telemetry SHALL identify the operation, workflow, and affected
  resources only through opaque allowlisted identifiers
- **AND** the stable diagnostic link SHALL be same-origin and stripped of query
  and fragment data
- **AND** an out-of-band alert SHALL retry safely without duplicate delivery
- **AND** payloads SHALL redact secrets, PII, natural source keys, and user
  content

#### Scenario: Staging verification completes

- **WHEN** a controlled staging operation produces a configured terminal
  outcome
- **THEN** repository evidence SHALL correlate persisted operation state,
  telemetry classification, and external alert arrival
