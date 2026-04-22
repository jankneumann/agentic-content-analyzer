# mcp-http-client Specification

## ADDED Requirements

### Requirement: MCP tools route through HTTP API when configured

The system SHALL provide a mechanism where MCP tools (`search_knowledge_base`, `search_knowledge_graph`, `extract_references`, `resolve_references`) call the HTTP API when `ACA_API_BASE_URL` and `ACA_ADMIN_KEY` environment variables are set. When not set, the tools MUST fall back to in-process service calls to preserve backwards compatibility.

#### Scenario: MCP tool with HTTP config uses ApiClient

- **WHEN** the MCP server starts with `ACA_API_BASE_URL=https://api.aca.rotkohl.ai` and `ACA_ADMIN_KEY=...` set
- **AND** a client invokes the `search_knowledge_base` MCP tool
- **THEN** the tool issues a `GET /api/v1/kb/search` HTTP request to the configured base URL
- **AND** the request includes `X-Admin-Key: <ACA_ADMIN_KEY>` header
- **AND** the tool returns results parsed from the HTTP response

#### Scenario: MCP tool without HTTP config falls back to in-process

- **WHEN** neither `ACA_API_BASE_URL` nor `ACA_ADMIN_KEY` is set
- **AND** a client invokes an MCP tool that has been refactored for HTTP mode
- **THEN** the tool calls the in-process service directly (pre-refactor behavior)
- **AND** no HTTP requests are made

#### Scenario: MCP tool with partial config fails safely

- **WHEN** `ACA_API_BASE_URL` is set but `ACA_ADMIN_KEY` is unset
- **AND** `--strict-http` flag is NOT set
- **THEN** the tool falls back to in-process mode and logs a warning

#### Scenario: Strict HTTP mode rejects unconfigured tools

- **WHEN** the MCP server starts with `--strict-http` flag
- **AND** HTTP config is missing or incomplete
- **THEN** the server logs an error on startup
- **AND** affected tools return an error when invoked

### Requirement: MCP tool schemas remain stable across refactor

The MCP tool argument schemas and return shapes for `search_knowledge_base`, `search_knowledge_graph`, `extract_references`, and `resolve_references` MUST remain identical before and after the HTTP refactor. Consumers SHALL see no observable behavior change when HTTP config is unset.

#### Scenario: Tool signatures are unchanged

- **WHEN** comparing the MCP tool schema before and after the refactor
- **THEN** argument names, types, defaults, and return schemas are byte-identical

#### Scenario: In-process vs HTTP mode produce equivalent results

- **WHEN** the same MCP tool is called with identical arguments in in-process mode and in HTTP mode (against the same data)
- **THEN** the returned result structures are equivalent (modulo ordering of list fields where unspecified)
