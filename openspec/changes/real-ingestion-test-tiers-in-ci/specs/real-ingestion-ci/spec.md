## ADDED Requirements

### Requirement: Real ingestion CI follows canonical source workflows

CI SHALL map every `SOURCE_REGISTRY` entry to a reviewed fixture, scheduled
live tier, or explicit exclusion and SHALL validate durable terminal results
against persisted database effects.

#### Scenario: Pull-request fixture ingestion completes

- **WHEN** a representative typed source command is submitted through the
  canonical workflow service
- **THEN** CI SHALL observe its operation to a terminal state
- **AND** claimed results SHALL match the expected database row delta

#### Scenario: A source requires credentials or live network access

- **WHEN** the scheduled tier evaluates that source
- **THEN** credential availability, skip, retry, and failure rules SHALL be
  explicit
- **AND** evidence SHALL distinguish adapter, queue, and persistence failures
