## MODIFIED Requirements

### Requirement: MCP capability discovery

The MCP server SHALL expose `get_capabilities` derived from the canonical capability document and SHALL divide tool registration into bounded modules without changing the generated tool contract. The canonical manifest SHALL contain one registry-driven `ingest` tool rather than one tool per source.

#### Scenario: Agent discovers next actions
- **WHEN** an agent requests capabilities
- **THEN** the response identifies supported tools, operation types, required fields, cancellability, and result resource types
- **AND** mutation tools identify the status and result lookup operations
- **AND** `supported_tools` contains exactly the 23 canonical tool names, including `ingest` and excluding every `ingest_*` name

#### Scenario: Manifest cannot drift from the source registry
- **WHEN** a source is added to `SOURCE_REGISTRY`
- **THEN** it is invocable through `ingest` without any change to the tool manifest
- **AND** the conformance test proves every registry key round-trips through `ingest` with its `COMMAND_FIELD_SCHEMAS` fields

### Requirement: MCP workflow tools use canonical operations

MCP mutation tools SHALL return structured `OperationHandle` objects and SHALL expose explicit tools for operation status, waiting, retry, and safe cancellation. Workflow completion results MUST include stable resource identifiers and URLs. Ingestion SHALL be invoked through one `ingest(source, params, idempotency_key)` tool, and `run_pipeline` SHALL support `dry_run`.

#### Scenario: MCP digest generation is durable
- **WHEN** an agent invokes digest creation
- **THEN** the tool returns a structured queued operation handle
- **AND** waiting for completion returns a persisted digest resource ID

#### Scenario: MCP ingestion supports every registered command
- **WHEN** an agent calls `ingest(source=<registry key>, params={...})`
- **THEN** `params` is validated against `COMMAND_FIELD_SCHEMAS[source]` with unknown keys rejected
- **AND** the call dispatches through the same submission path as HTTP ingestion
- **AND** the result retains the canonical ingestion response in the operation result

#### Scenario: MCP ingestion rejects unknown sources
- **WHEN** an agent calls `ingest` with a `source` that is not a registry key
- **THEN** the tool raises a typed validation protocol error naming the valid keys
- **AND** no operation is submitted

#### Scenario: MCP pipeline dry run
- **WHEN** an agent calls `run_pipeline(..., dry_run=True)`
- **THEN** the tool returns a `PipelinePlan` rather than an `OperationHandle`
- **AND** no operation is submitted

#### Scenario: MCP search pages with a cursor
- **WHEN** an agent calls `search_content` and the response carries `next_cursor`
- **THEN** a subsequent call with `cursor = next_cursor` and the same query returns the next page
- **AND** the response `meta.completeness` and `meta.omissions` are present on every page
