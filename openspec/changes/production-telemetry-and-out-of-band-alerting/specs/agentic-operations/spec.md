# agentic-operations Specification Delta

## ADDED Requirements

### Requirement: Canonical terminal transitions persist event intent

The system SHALL atomically insert one minimal terminal-event intent for every
authoritative transition of an operation attempt into `completed`, `failed`, or
`cancelled`. The intent SHALL be identified by operation ID, claim generation,
and terminal status. The
intent SHALL be committed by the same database transaction as the state change
and SHALL remain valid after operation retention.

#### Scenario: A terminal transition commits

- **WHEN** a current claim commits a supported terminal status
- **THEN** exactly one matching minimal event intent SHALL commit atomically
- **AND** a later duplicate update SHALL NOT insert another intent

#### Scenario: A stale claim loses its terminal race

- **WHEN** a superseded claim attempts a terminal update that affects no row
- **THEN** it SHALL NOT create terminal-event intent or external delivery

#### Scenario: Terminal intent cannot be persisted

- **WHEN** the terminal-event insert violates persistence invariants
- **THEN** the terminal status mutation SHALL roll back
- **AND** the still-current operation MAY be retried by the canonical worker

### Requirement: Terminal projection reads committed state

The system SHALL re-read the committed operation payload/result for terminal classification
rather than reuse a pre-handler payload snapshot. Operation state SHALL remain
authoritative when telemetry projection or export fails.

#### Scenario: A handler attaches a result before completion

- **WHEN** a handler persists a partial or zero-item V2 result and the worker
  then completes the operation
- **THEN** projection SHALL observe and classify that committed result

#### Scenario: Telemetry export fails

- **WHEN** OTel or an external sink is unavailable after terminal commit
- **THEN** the operation SHALL remain terminal
- **AND** durable event/delivery state SHALL remain available for recovery
