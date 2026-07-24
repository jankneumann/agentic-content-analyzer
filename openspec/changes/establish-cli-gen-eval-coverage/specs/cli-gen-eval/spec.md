## ADDED Requirements

### Requirement: CLI gen-eval is reproducible and environment-safe

The repository SHALL provide a checked-in CLI gen-eval descriptor, scenarios,
report schema, Make target, and CI threshold while preventing mutating scenarios
from targeting production by default.

#### Scenario: CI executes the CLI evaluation suite

- **WHEN** `make gen-eval` runs in CI
- **THEN** it SHALL emit a schema-valid report grouped by command and category
- **AND** SHALL enforce the documented pass-rate threshold

#### Scenario: A mutation scenario is selected

- **WHEN** an evaluation scenario submits or controls durable work
- **THEN** it SHALL require an explicit staging or ephemeral target
- **AND** SHALL cover the canonical operation handle and control commands
