# mcp-http-client Specification

## Purpose
TBD - created by archiving change cloud-db-source-of-truth. Update Purpose after archive.
## Requirements
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

### Requirement: MCP HTTP transport resilience

When operating in HTTP mode, the MCP tools MUST use the shared `ApiClient` (`src/cli/api_client.py`) with a 30-second request timeout and one retry attempt (1-second backoff) for transient errors: `429 Too Many Requests`, `502 Bad Gateway`, `503 Service Unavailable`, `504 Gateway Timeout`, and connection-reset errors. Non-retryable errors (4xx except 429) MUST propagate back to the MCP client as tool-error responses with the HTTP status code and the server-provided `Problem` body.

#### Scenario: Transient 503 is retried once

- **WHEN** the HTTP API returns `503 Service Unavailable` on the first attempt
- **THEN** `ApiClient` waits 1 second and retries the request exactly once
- **AND** if the retry succeeds, the tool returns the success payload transparently
- **AND** if the retry also fails, the tool returns an error with the final status code

#### Scenario: Non-retryable 400 is surfaced directly

- **WHEN** the HTTP API returns `400 Bad Request` with a `Problem` body
- **THEN** the tool does NOT retry
- **AND** the MCP error response includes the HTTP status and the `Problem.detail` message

#### Scenario: HTTP timeout falls back to error, not to in-process

- **WHEN** the HTTP request exceeds the 30-second timeout
- **THEN** the tool returns an MCP error indicating the HTTP call timed out
- **AND** the tool does NOT silently fall back to in-process mode (avoids divergent behavior under failure)

### Requirement: MCP tool shapes align with OpenAPI contract (breaking change accepted)

The MCP tools `search_knowledge_base`, `search_knowledge_graph`, `extract_references`, and `resolve_references` SHALL return response shapes that match the OpenAPI schemas in `contracts/openapi/v1.yaml` exactly — both in HTTP mode and in in-process fallback mode.

This is a **breaking change** for the MCP tool return schemas. It is accepted because the sole MCP consumer set (@jankneumann's personal Claude Code / Codex / Gemini configs and the `agentic-assistant` project) is controlled and updates in lockstep with this change.

Before/after for each tool:

| Tool | Before (legacy) | After (OpenAPI-aligned) |
|------|-----------------|-------------------------|
| `search_knowledge_base` | list of `{name, category, summary, relevance_score, mention_count}` | `{topics: [{slug, title, score, excerpt, last_compiled_at}], total_count}` |
| `search_knowledge_graph` | ad-hoc text | `{entities: [{id, name, type, score}], relationships: [{source_id, target_id, type, score}]}` |
| `extract_references` | `{scanned, references_found, dry_run}` | `{references_extracted, content_processed, has_more, next_cursor?, per_content?: [{content_id, references_found}]}` — `has_more` is always present; `next_cursor` is present only when `has_more=true`; `per_content` is an optional enriched detail array |
| `resolve_references` | `{resolved, batch_size}` | `{resolved_count, still_unresolved_count, has_more}` |

#### Scenario: HTTP and in-process modes produce identical shapes

- **WHEN** the same MCP tool is called with identical arguments in HTTP mode and in-process mode against the same data
- **THEN** the returned JSON structures are identical (same keys, same types, same nesting)
- **AND** only list ordering MAY differ where unspecified by the OpenAPI contract

#### Scenario: Tool response validates against OpenAPI schema

- **WHEN** the `search_knowledge_base` tool returns a response in either mode
- **THEN** the response payload validates against `KBSearchResponse` in `contracts/openapi/v1.yaml`
- **AND** `last_compiled_at` is present on every result as an ISO-8601 timestamp

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
