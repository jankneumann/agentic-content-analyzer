## ADDED Requirements

### Requirement: Ingestion history derives from durable operations

Per-source ingestion history SHALL derive from canonical operations,
parent-child relationships, checkpoints, results, resources, retries, and
terminal problems unless a documented query or retention gap proves an
additional projection is necessary.

#### Scenario: A pipeline has mixed source outcomes

- **WHEN** an operator queries the run through canonical CLI or API surfaces
- **THEN** successful, partial, zero-item, and failed source outcomes SHALL be
  distinguishable
- **AND** retry and checkpoint identity SHALL remain attached to the
  authoritative operations

#### Scenario: A new persistence projection is proposed

- **WHEN** existing operation payloads cannot satisfy a documented query or
  retention rule
- **THEN** the new projection SHALL retain operation identity and idempotency
- **AND** SHALL not create a parallel workflow state machine
