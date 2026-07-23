# openspec-inventory-governance Specification

## Purpose
TBD - created by archiving change reconcile-openspec-inventory. Update Purpose after archive.
## Requirements
### Requirement: Evidence-backed change disposition

The repository SHALL assign every reconciled OpenSpec entry an explicit
disposition supported by current implementation, test, specification, and
external-state evidence.

#### Scenario: Completed implementation has stale tasks

- **GIVEN** a change has unchecked tasks
- **AND** current code and focused tests prove the acceptance behavior exists
- **WHEN** the inventory is reconciled
- **THEN** task state and verification evidence SHALL be updated
- **AND** the completed foundation SHALL be archived rather than reimplemented

#### Scenario: Required external proof is absent

- **GIVEN** repository evidence proves configuration or implementation
- **BUT** cannot prove image pullability, production deployment, or model access
- **WHEN** the broad change is reconciled
- **THEN** the implemented foundation SHALL be archived only after its current
  behavior is specified and the unproven work is extracted
- **AND** the unproven operation SHALL remain as a focused actionable change

### Requirement: Superseded contracts remain historical

A change whose target behavior conflicts with the canonical durable workflow contract SHALL
be archived as superseded without synchronizing its obsolete contract into the
durable main specifications.

#### Scenario: Synchronous MCP response was replaced

- **GIVEN** an old change requires MCP ingestion to return a synchronous
  ingestion response
- **AND** current MCP ingestion submits a typed command and returns an
  `OperationHandle`
- **WHEN** the old change is reconciled
- **THEN** it SHALL be archived with a supersession record
- **AND** no synchronous transport-specific execution path SHALL be restored

### Requirement: Active inventory is actionable

The active OpenSpec inventory SHALL contain only entries that identify a
bounded next action and are schema-valid for their lifecycle stage.

#### Scenario: Analysis-only directory is discovered

- **GIVEN** an active directory contains only an opportunity analysis
- **AND** has no bounded proposal, tasks, or specification delta
- **WHEN** the inventory validator runs
- **THEN** the directory SHALL be rejected as an active change
- **AND** its analysis MAY be retained in historical archive or discovery
  documentation

#### Scenario: Approved future roadmap item remains active

- **GIVEN** a change is mapped to a later approved roadmap item
- **WHEN** the current inventory item completes
- **THEN** that change SHALL remain active
- **AND** its next lifecycle action SHALL be recorded in the disposition
  manifest

### Requirement: Extracted gaps are traceable

Every focused change extracted from a broader archived change SHALL identify
its source change, excluded completed scope, authority boundary, and executable
acceptance evidence.

#### Scenario: Production verification is extracted

- **GIVEN** a broad change has completed repository implementation
- **AND** only external production verification remains
- **WHEN** a focused follow-up is created
- **THEN** it SHALL reference the archived source change
- **AND** SHALL exclude repetition of completed foundation work
- **AND** SHALL define sanitized evidence and rollback requirements for any
  external mutation
