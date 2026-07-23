## ADDED Requirements

### Requirement: Release smoke separates read-only and mutating tiers

The release gate SHALL run production-safe read-only compatibility checks
separately from mutation scenarios that require an explicit staging or
ephemeral target.

#### Scenario: Default release smoke targets production

- **WHEN** the smoke gate runs with default configuration
- **THEN** it SHALL exercise deployed frontend, CLI, and API discovery behavior
- **AND** SHALL reject every mutating scenario

#### Scenario: Staging mutation is explicitly enabled

- **WHEN** an operator supplies an approved staging or ephemeral target
- **THEN** the gate SHALL submit a canonical ingestion command
- **AND** SHALL observe its durable operation to a terminal state
- **AND** SHALL retain the tested frontend and API revisions as evidence
