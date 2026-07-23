## ADDED Requirements

### Requirement: Canonical filtering controls

The system SHALL define filtering controls through shared source configuration,
typed workflow commands, and capability metadata without transport-specific
execution or undocumented precedence.

#### Scenario: A source overrides the global filter policy

- **GIVEN** a resolved source has a filter policy different from the global
  default
- **WHEN** a canonical ingestion operation processes that source
- **THEN** the effective policy SHALL be deterministic and testable
- **AND** CLI, HTTP, MCP, worker, and frontend SHALL observe the same policy

#### Scenario: Historical language filtering is reconciled

- **WHEN** the refined plan evaluates the historical language-gate promise
- **THEN** it SHALL either define and test detection plus unknown-language
  fail-open semantics or explicitly retire the configuration and documentation
- **AND** the current runtime, contracts, and operator surfaces SHALL agree

### Requirement: Filtering operations have truthful semantics

Dry-run, rerun, explain, and content projection behavior SHALL agree across the
durable specification, runtime persistence, CLI/API output, and documentation.

#### Scenario: Operator uses a retained filtering operation

- **WHEN** an operator invokes dry-run, rerun, or explain behavior retained by
  the refined plan
- **THEN** persisted fields and status transitions SHALL match the documented
  contract
- **AND** unsupported historical flags or fields SHALL not be advertised

### Requirement: Filtering evidence is observable and safe

The system SHALL provide regression and telemetry evidence for retained filter
decisions without exposing content, secrets, or persona-private data.

#### Scenario: A filter decision completes

- **WHEN** a filter decision is recorded
- **THEN** the configured span and structured attributes SHALL identify the
  source, tier, decision, and score according to the refined contract
- **AND** any reviewer feedback integration SHALL have an explicit durable owner
