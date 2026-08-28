## ADDED Requirements

### Requirement: Canonical operations carry observability correlation

Submission and child-submission SHALL store the canonical operation context before queue visibility. Exact OperationHandle reads SHALL include a bounded observability summary; OperationSummary collection rows SHALL remain bounded and SHALL not embed attempt arrays or detailed evidence.

#### Scenario: [OPS-001] Child operation preserves operation graph and trace

- **WHEN** a parent operation submits a child operation
- **THEN** the child receives a new operation ID and retains parent/root operation IDs
- **AND** its submission context continues the parent trace

#### Scenario: [OPS-002] Legacy operation remains readable

- **WHEN** an operation created before observability fields were introduced is read
- **THEN** the canonical handle remains valid with absent correlation fields
- **AND** no fabricated trace identifier is returned

### Requirement: Terminal operation evidence identifies its attempt

Every terminal result, problem, and alert event SHALL retain operation ID and claim generation and SHOULD retain trace ID when an attempt started. A retry SHALL create new attempt evidence rather than replacing the terminal evidence of an earlier claim.

#### Scenario: [OPS-003] Failure problem locates detailed evidence

- **WHEN** an operation terminates with a domain or infrastructure problem
- **THEN** its exact handle exposes bounded problem and attempt codes
- **AND** an authorized operator can use its trace ID to locate detailed evidence
