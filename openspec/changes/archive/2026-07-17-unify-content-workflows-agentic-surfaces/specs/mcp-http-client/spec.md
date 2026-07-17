## MODIFIED Requirements

### Requirement: MCP tools route through HTTP API when configured

Every MCP tool with an HTTP API capability SHALL use the shared HTTP client when `ACA_API_BASE_URL` and `ACA_ADMIN_KEY` are configured. In-process mode SHALL call the same application service and MUST return the same structured contract. Strict HTTP mode MUST fail closed for every tool rather than allowing selected tools to access a local database.

#### Scenario: Any workflow tool in HTTP mode uses API client
- **WHEN** the MCP server has complete HTTP configuration
- **AND** a client invokes an ingestion, summarization, digest, pipeline, podcast, audio, content, review, graph, reference, or knowledge tool
- **THEN** the tool calls its declared HTTP operation through the shared client
- **AND** it does not access local persistence or instantiate local workflow services

#### Scenario: In-process mode uses application service
- **WHEN** HTTP configuration is absent and strict mode is disabled
- **AND** a client invokes a tool
- **THEN** the tool calls the canonical in-process application service
- **AND** its structured result conforms to the same schema as HTTP mode

#### Scenario: Partial HTTP config is diagnostic
- **WHEN** only part of the required HTTP configuration is present
- **AND** strict mode is disabled
- **THEN** the server emits a diagnostic to stderr
- **AND** tools use the declared in-process mode without polluting protocol output

#### Scenario: Strict HTTP mode fails closed
- **WHEN** strict HTTP mode is enabled with missing configuration or an unmapped tool
- **THEN** server startup or tool invocation returns a protocol-level configuration error
- **AND** no tool silently falls back to local data

## ADDED Requirements

### Requirement: MCP workflow tools use canonical operations

MCP mutation tools SHALL return structured `OperationHandle` objects and SHALL expose explicit tools for operation status, waiting, retry, and safe cancellation. Workflow completion results MUST include stable resource identifiers and URLs.

#### Scenario: MCP digest generation is durable
- **WHEN** an agent invokes digest creation
- **THEN** the tool returns a structured queued operation handle
- **AND** waiting for completion returns a persisted digest resource ID

#### Scenario: MCP ingestion supports every registered command
- **WHEN** an agent inspects MCP capabilities
- **THEN** every registry ingestion discriminator is invocable with its source-specific fields
- **AND** the result retains the canonical ingestion response in the operation result

### Requirement: MCP structured result and error contracts

MCP tools SHALL return native structured results matching generated schemas rather than JSON-encoded strings. Validation, authentication, conflict, timeout, and workflow failures MUST be MCP errors containing stable code and structured problem data.

#### Scenario: Success is not double encoded
- **WHEN** an MCP tool succeeds
- **THEN** the client receives an object matching the declared output schema
- **AND** parsing a JSON string is not required

#### Scenario: HTTP problem becomes MCP error
- **WHEN** HTTP mode receives an RFC 7807 response
- **THEN** the MCP tool raises an error preserving problem type, title, status, detail, and instance

### Requirement: MCP capability discovery

The MCP server SHALL expose `get_capabilities` derived from the canonical capability document and SHALL divide tool registration into bounded modules without changing the generated tool contract.

#### Scenario: Agent discovers next actions
- **WHEN** an agent requests capabilities
- **THEN** the response identifies supported tools, operation types, required fields, cancellability, and result resource types
- **AND** mutation tools identify the status and result lookup operations
