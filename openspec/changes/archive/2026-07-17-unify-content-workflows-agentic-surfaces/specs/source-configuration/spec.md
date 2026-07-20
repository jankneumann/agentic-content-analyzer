## ADDED Requirements

### Requirement: Heterogeneous source discovery

Source discovery SHALL serialize each configured source through its registered source descriptor and MUST NOT assume optional fields such as `url`, `query`, or `identifier` exist on every source model.

#### Scenario: Readwise source is listed
- **GIVEN** an enabled Readwise source has no URL field
- **WHEN** configured sources are listed through HTTP, CLI, MCP, or the frontend
- **THEN** the source is returned successfully with its canonical type and capability metadata
- **AND** no attribute error occurs

#### Scenario: All config source models are registered
- **WHEN** source configuration models are validated at startup
- **THEN** every enabled ingestion-capable config type maps to exactly one registry descriptor
- **AND** an unregistered type fails validation with its config key
