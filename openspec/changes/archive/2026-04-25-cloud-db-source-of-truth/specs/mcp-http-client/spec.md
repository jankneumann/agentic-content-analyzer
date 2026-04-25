# mcp-http-client Specification

## ADDED Requirements

### Requirement: MCP tools route through HTTP API when configured

The system SHALL provide a mechanism where MCP tools (`search_knowledge_base`, `search_knowledge_graph`, `extract_references`, `resolve_references`) call the HTTP API when `ACA_API_BASE_URL` and `ACA_ADMIN_KEY` environment variables are set. When not set, the tools MUST fall back to in-process service calls; the fallback path SHALL also return the new shapes defined by the OpenAPI contract (see "MCP tool shapes align with OpenAPI" below).

#### Scenario: MCP tool with HTTP config uses ApiClient

- **WHEN** the MCP server starts with `ACA_API_BASE_URL=https://api.aca.rotkohl.ai` and `ACA_ADMIN_KEY=...` set
- **AND** a client invokes the `search_knowledge_base` MCP tool
- **THEN** the tool issues a `GET /api/v1/kb/search` HTTP request to the configured base URL
- **AND** the request includes `X-Admin-Key: <ACA_ADMIN_KEY>` header
- **AND** the tool returns results parsed from the HTTP response

#### Scenario: MCP tool without HTTP config falls back to in-process

- **WHEN** neither `ACA_API_BASE_URL` nor `ACA_ADMIN_KEY` is set
- **AND** a client invokes an MCP tool that has been refactored
- **THEN** the tool calls the in-process service directly
- **AND** no HTTP requests are made
- **AND** the return shape matches what the HTTP endpoint would have returned (OpenAPI-aligned)

#### Scenario: MCP tool with partial config emits stderr warning and falls back

- **WHEN** `ACA_API_BASE_URL` is set but `ACA_ADMIN_KEY` is unset
- **AND** the `--strict-http` flag is NOT set
- **THEN** the tool falls back to in-process mode
- **AND** a warning is emitted to stderr (NOT the tool response) with a clear message pointing to the missing env var

Rationale: MCP tool stdout/stderr split — stdout is the JSON-RPC channel, stderr is for host-side diagnostics. Polluting the JSON response with warning strings would break client parsers.

#### Scenario: Strict HTTP mode rejects unconfigured tools

- **WHEN** the MCP server starts with `--strict-http` flag
- **AND** HTTP config is missing or incomplete
- **THEN** the server logs an error to stderr on startup
- **AND** affected tools return an error payload when invoked (no silent fallback)

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
