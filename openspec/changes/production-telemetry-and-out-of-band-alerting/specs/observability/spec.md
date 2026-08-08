# observability Specification Delta

## ADDED Requirements

### Requirement: Workflow terminal telemetry is bounded and low-cardinality

Committed terminal events SHALL emit a structured log and OTel telemetry using
only stable outcome, severity, operation-type, and source-kind dimensions.
Identifiers MAY be correlation fields in logs/events but SHALL NOT be metric
labels. Raw errors, messages, source keys, resource IDs, URLs, inputs, results,
and secrets SHALL NOT be telemetry attributes.

#### Scenario: Terminal telemetry is emitted

- **WHEN** a pending terminal event is classified
- **THEN** its stable event name and closed dimensions SHALL be emitted
- **AND** the event SHALL record a best-effort telemetry checkpoint

#### Scenario: OTel is disabled or rejects export

- **WHEN** the configured OTel provider is disabled or export fails
- **THEN** workflow and delivery state SHALL be unchanged
- **AND** the system SHALL retain safe local terminal evidence
