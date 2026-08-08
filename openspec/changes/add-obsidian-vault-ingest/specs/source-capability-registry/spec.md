# source-capability-registry Specification

## MODIFIED Requirements

### Requirement: Registry-derived capability parity

The system SHALL derive CLI ingestion commands, HTTP command discriminators, MCP
ingestion tools, pipeline scheduled sources, frontend source metadata, and end-to-end
fixture coverage from the registry or generated registry contracts. CI MUST fail when
their canonical key sets differ. Filesystem-backed descriptors MUST additionally keep
private paths outside generated public commands and capability metadata while exposing
an opaque configured-source key and readiness state.

#### Scenario: New source requires complete surface coverage

- **WHEN** an `obsidian_vault` descriptor is added to the registry
- **THEN** its typed command and safe options SHALL appear in generated Python and
  TypeScript contracts, CLI, HTTP, MCP, worker dispatch, scheduling, and the
  capability-driven frontend
- **AND** CI SHALL fail until the MCP function/map/manifest and deterministic vertical
  fixture are complete

#### Scenario: Equivalent Obsidian submissions use one durable contract

- **WHEN** equivalent Obsidian commands are submitted through CLI, HTTP, MCP, and the
  frontend
- **THEN** each SHALL enqueue the same `ingestion.execute` operation with the same
  normalized command schema
- **AND** CLI and MCP SHALL return the same canonical `OperationHandle` fields as HTTP
- **AND** no interface SHALL accept or return a vault path or note path

#### Scenario: Filesystem source capability is discovered

- **WHEN** capabilities are requested for an Obsidian source
- **THEN** every interface SHALL observe the same source key, public fields, scan
  options, capability flags, and readiness state
- **AND** private vault configuration SHALL be absent from all discovery projections

#### Scenario: Database override is projected safely

- **GIVEN** an Obsidian source override contains its private server path
- **WHEN** source configuration is listed, resolved for a command, or serialized into
  an operation
- **THEN** trusted server-side resolution MAY use the path
- **AND** public/admin responses, operation input/result, telemetry, and logs SHALL use
  only the opaque HMAC configured-source key and safe allowlisted fields
- **AND** the override SHALL NOT widen deployment-owned allowed roots
