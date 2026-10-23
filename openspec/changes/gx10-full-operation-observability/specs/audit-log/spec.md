## ADDED Requirements

### Requirement: Audit rows persist actual trace correlation

Audit middleware SHALL persist request ID, trace ID, request span ID, optional operation ID, service identity, and release revision using validated fixed-width representations. Request ID SHALL NOT be described as a trace ID, and high-cardinality correlation identifiers SHALL not become metric labels.

#### Scenario: [AUDIT-001] Audited submission joins to operation

- **WHEN** an audited API request submits a durable operation
- **THEN** the audit row contains the request trace/span and submitted operation ID
- **AND** the active span contains the audit record identifier after persistence

#### Scenario: [AUDIT-002] Request has no valid inbound context

- **WHEN** an audited request arrives without valid W3C context
- **THEN** middleware creates a local trace and persists its actual trace ID
- **AND** the request ID remains a separate identifier
