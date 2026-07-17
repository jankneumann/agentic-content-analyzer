## ADDED Requirements

### Requirement: Executable source registry

The system SHALL maintain one executable `SourceRegistry` whose descriptor for every ingestion command defines its canonical key, aliases, typed command model, orchestrator, non-empty set of possible emitted `ContentSource` values, optional dynamic source resolver, configuration accessor when applicable, scheduling support, and option capabilities. The registry MUST reject duplicate keys, duplicate aliases, empty emitted-source sets, and incomplete descriptors during application startup.

#### Scenario: Registered source descriptor is complete
- **WHEN** the application validates a registered ingestion source
- **THEN** the descriptor contains every field required for dispatch and capability discovery
- **AND** its command discriminator is unique
- **AND** a dynamically routed command declares every source it may emit

#### Scenario: Invalid registry fails fast
- **WHEN** two descriptors claim the same key or alias
- **THEN** application startup fails with an error naming the conflicting descriptors

### Requirement: Typed ingestion service dispatch

`IngestionService.execute()` SHALL accept the registry's discriminated `IngestCommand` union and SHALL be the only application dispatch boundary for source ingestion. It MUST return the canonical `IngestionResponse` and MUST reject unknown sources or unsupported parameter combinations before a job is enqueued.

#### Scenario: Source-specific command executes
- **WHEN** a valid `arxiv_paper` command with an identifier is executed
- **THEN** the registry dispatches the command to the arXiv paper orchestrator
- **AND** every declared option reaches that orchestrator without loss
- **AND** the result is a canonical `IngestionResponse`
- **AND** a `url` command preserves `routing_mode` and reports its resolved route

#### Scenario: Invalid source command is rejected synchronously
- **WHEN** an ingestion request has an unknown discriminator or an option not allowed by its descriptor
- **THEN** validation fails before queue submission
- **AND** the error lists the applicable source contract

### Requirement: Registry-derived capability parity

The system SHALL derive CLI ingestion commands, HTTP command discriminators, MCP ingestion tools, pipeline scheduled sources, frontend source metadata, and end-to-end fixture coverage from the registry or generated registry contracts. CI MUST fail when their canonical key sets differ.

#### Scenario: New source requires complete surface coverage
- **WHEN** a descriptor is added to the registry
- **THEN** contract generation exposes it to every supported interface
- **AND** CI fails until a vertical fixture exists for that descriptor

#### Scenario: Capability discovery is consistent
- **WHEN** capabilities are requested through CLI, HTTP, MCP, and the frontend client
- **THEN** every interface observes the same source keys, fields, and capability flags for the same deployment
