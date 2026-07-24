## ADDED Requirements

### Requirement: Source override request contract is singular

The source override OpenAPI, server models, generated clients, and examples SHALL
use one source-type discriminator location and one canonical PATCH mutation for
runtime updates.

#### Scenario: An administrator upserts and disables a source

- **WHEN** an authenticated client submits a valid source and later disables it
- **THEN** generated and runtime models SHALL accept the same payload shape
- **AND** the disable operation SHALL preserve the natural key and version rules

### Requirement: Source settings behavior has browser evidence

The settings UI SHALL have component and browser evidence for add, origin
display, enable/disable, and origin-aware deletion behavior.

#### Scenario: YAML and database sources render together

- **WHEN** the source settings surface loads mixed origins
- **THEN** both origins and enabled states SHALL be visible
- **AND** destructive controls SHALL reflect whether the row is YAML- or
  database-owned

### Requirement: Source override operations are reproducible

Setup documentation and migration tests SHALL demonstrate how the table is
created, how precedence works, and how operators recover or remove overrides.

#### Scenario: A fresh database is upgraded

- **WHEN** migrations run against a disposable supported PostgreSQL database
- **THEN** the source override schema and constraints SHALL be verified
- **AND** documented CLI/API operations SHALL match current behavior
