# Tasks: cloud-db-source-of-truth

Task IDs follow `<phase>.<seq>` convention. Test tasks precede their implementation counterparts (TDD). Each implementation task lists its dependency on the corresponding test task.

Phase → Work Package mapping:
- Phase 0 → `wp-contracts`
- Phase 1 → `wp-api`
- Phase 2 → `wp-audit`
- Phase 3 → `wp-mcp`
- Phase 4 → `wp-ops`
- Phase 5 → `wp-integration`

---

## Phase 0: Contracts (wp-contracts)

- [ ] 0.1 Validate OpenAPI spec against `openapi-spec-validator`
  **Contracts**: `contracts/openapi/v1.yaml`
  **Dependencies**: None

- [ ] 0.2 Generate Pydantic models from OpenAPI to `contracts/generated/models.py`
  **Contracts**: `contracts/openapi/v1.yaml`
  **Dependencies**: 0.1

- [ ] 0.3 Generate TypeScript types from OpenAPI to `contracts/generated/types.ts`
  **Contracts**: `contracts/openapi/v1.yaml`
  **Dependencies**: 0.1

- [ ] 0.4 Validate `contracts/db/schema.sql` parses cleanly against PG17 container
  **Contracts**: `contracts/db/schema.sql`
  **Dependencies**: None

- [ ] 0.5 Apply seed rows from `contracts/db/seed.sql` to fixture DB and assert row count = 5
  **Contracts**: `contracts/db/seed.sql`
  **Dependencies**: 0.4

---

## Phase 1: HTTP API Endpoints (wp-api)

### 1A: KB search + lint

- [ ] 1.1 Write route tests for `GET /api/v1/kb/search` — matching query, empty result, auth enforcement, limit parameter
  **Spec scenarios**: knowledge-base:Search with matching query, Search with no matches, Unauthenticated search, Search honors limit
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1kb~1search`
  **Dependencies**: 0.2

- [ ] 1.2 Implement `src/api/routes/kb_search_routes.py` — handler, Pydantic models from contracts, service wiring
  **Dependencies**: 1.1

- [ ] 1.3 Write route tests for `GET /api/v1/kb/lint` and `POST /api/v1/kb/lint/fix` — read-only vs mutation, audit trigger, zero-diff case
  **Spec scenarios**: knowledge-base:GET lint returns health report, POST lint/fix applies corrections, POST lint/fix when no corrections needed
  **Design decisions**: D3 (middleware + @audited)
  **Contracts**: `contracts/openapi/v1.yaml` (kb lint paths)
  **Dependencies**: 0.2

- [ ] 1.4 Implement KB lint routes (extend `src/api/routes/kb_routes.py`) with `@audited` on fix endpoint
  **Dependencies**: 1.3, 2.2

### 1B: Graph query + extract-entities

- [ ] 1.5 Write route tests for `POST /api/v1/graph/query` — entity/relationship shape, empty result, validation
  **Spec scenarios**: knowledge-graph:Graph query returns entities and relationships, Graph query with empty result, Graph query validates query field
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1graph~1query`
  **Dependencies**: 0.2

- [ ] 1.6 Implement `src/api/routes/graph_routes.py` — query handler, GraphitiClient wiring
  **Dependencies**: 1.5

- [ ] 1.7 Write route tests for `POST /api/v1/graph/extract-entities` — success, 404 missing content, 409 no summary, audit log entry
  **Spec scenarios**: knowledge-graph:Extract entities for existing content, Extract entities for missing content, Extract entities for content without summary
  **Design decisions**: D3 (audited decorator)
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1graph~1extract-entities`
  **Dependencies**: 0.2

- [ ] 1.8 Implement extract-entities handler with `@audited(operation="graph.extract_entities")`
  **Dependencies**: 1.7, 2.2

### 1C: References extract + resolve

- [ ] 1.9 Write route tests for `POST /api/v1/references/extract` — by IDs, by date range, conflicting filters
  **Spec scenarios**: content-references:Extract references for content batch by IDs, Extract references for content by date range, Extract references rejects conflicting filters
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1references~1extract`
  **Dependencies**: 0.2

- [ ] 1.10 Implement references/extract handler; extend or create `src/api/routes/reference_routes.py`; coordinate with `add-content-references` proposal for scope overlap
  **Dependencies**: 1.9, 2.2

- [ ] 1.11 Write route tests for `POST /api/v1/references/resolve` — all unresolved, batch_size clamp, has_more pagination
  **Spec scenarios**: content-references:Resolve all unresolved references, Resolve with batch limit
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1references~1resolve`
  **Dependencies**: 0.2

- [ ] 1.12 Implement references/resolve handler with `@audited(operation="references.resolve")`
  **Dependencies**: 1.11, 2.2

---

## Phase 2: Audit Logging (wp-audit)

- [ ] 2.1 Write tests for `AuditMiddleware` — minimal record, admin_key_fp fingerprinting, body_size capture, failed-request logging
  **Spec scenarios**: audit-log:Request to audited endpoint creates log entry, Request body is not stored, Failed request is still logged
  **Design decisions**: D3 (middleware + decorator), D4 (append-only schema)
  **Contracts**: `contracts/db/schema.sql`
  **Dependencies**: 0.4

- [ ] 2.2 Implement `src/api/middleware/audit.py` — middleware + `@audited` decorator; register in app factory
  **Dependencies**: 2.1

- [ ] 2.3 Write Alembic migration test — upgrade creates `audit_log` table with correct schema, downgrade removes it
  **Contracts**: `contracts/db/schema.sql`
  **Dependencies**: 0.4

- [ ] 2.4 Create Alembic migration `alembic/versions/<rev>_add_audit_log_table.py`
  **Dependencies**: 2.3

- [ ] 2.5 Write tests for `GET /api/v1/audit` — time range, operation filter, status_code filter, limit clamping
  **Spec scenarios**: audit-log:Query recent audit entries, Query by operation, Query respects max limit
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1audit`
  **Dependencies**: 0.2, 2.4

- [ ] 2.6 Implement `src/api/routes/audit_routes.py` — query endpoint with filters
  **Dependencies**: 2.5

- [ ] 2.7 Write test for pg_cron retention job — simulate old row, run retention, assert deletion
  **Spec scenarios**: audit-log:Retention job deletes old entries, Retention is configurable
  **Design decisions**: D4 (retention via pg_cron)
  **Dependencies**: 2.4

- [ ] 2.8 Create data migration registering pg_cron retention job (respects `AUDIT_LOG_RETENTION_DAYS`)
  **Dependencies**: 2.7

---

## Phase 3: MCP Refactor (wp-mcp)

- [ ] 3.1 Write test for `_get_api_client()` helper — returns ApiClient when config set, None when unset, None for localhost default
  **Spec scenarios**: mcp-http-client:MCP tool with HTTP config uses ApiClient, MCP tool without HTTP config falls back to in-process, MCP tool with partial config fails safely
  **Design decisions**: D2 (fallback semantics)
  **Dependencies**: None

- [ ] 3.2 Implement `_get_api_client()` helper in `src/mcp_server.py`
  **Dependencies**: 3.1

- [ ] 3.3 Write integration tests for `search_knowledge_base` MCP tool — HTTP mode hits mocked API, in-process mode calls service, returns equivalent result
  **Spec scenarios**: mcp-http-client:MCP tool with HTTP config uses ApiClient, In-process vs HTTP mode produce equivalent results
  **Dependencies**: 3.2, 1.2

- [ ] 3.4 Refactor `search_knowledge_base` MCP tool for HTTP mode
  **Dependencies**: 3.3

- [ ] 3.5 Write integration tests for `search_knowledge_graph` MCP tool
  **Dependencies**: 3.2, 1.6

- [ ] 3.6 Refactor `search_knowledge_graph` MCP tool
  **Dependencies**: 3.5

- [ ] 3.7 Write integration tests for `extract_references` MCP tool
  **Dependencies**: 3.2, 1.10

- [ ] 3.8 Refactor `extract_references` MCP tool
  **Dependencies**: 3.7

- [ ] 3.9 Write integration tests for `resolve_references` MCP tool
  **Dependencies**: 3.2, 1.12

- [ ] 3.10 Refactor `resolve_references` MCP tool
  **Dependencies**: 3.9

- [ ] 3.11 Write test asserting MCP tool schemas byte-identical before/after refactor
  **Spec scenarios**: mcp-http-client:Tool signatures are unchanged
  **Dependencies**: 3.4, 3.6, 3.8, 3.10

- [ ] 3.12 Add `--strict-http` flag to MCP server startup; test rejects unconfigured startup
  **Spec scenarios**: mcp-http-client:Strict HTTP mode rejects unconfigured tools
  **Dependencies**: 3.2

---

## Phase 4: Sync-Down UX (wp-ops)

- [ ] 4.1 Write unit tests for `restore-from-cloud` CLI — argument parsing, backup date resolution (latest vs specific), subprocess error handling
  **Design decisions**: D5 (thin wrapper, not reimplementation)
  **Dependencies**: None

- [ ] 4.2 Implement `aca manage restore-from-cloud` subcommand in `src/cli/manage_commands.py`
  **Dependencies**: 4.1

- [ ] 4.3 Write integration test against a local MinIO fixture (use docker compose MinIO) — full round-trip restore of a known dump
  **Dependencies**: 4.2

- [ ] 4.4 Write `docs/SYNC_DOWN.md` — prereqs, examples, PII caveats, freshness discussion
  **Dependencies**: 4.2

- [ ] 4.5 Update `docs/SETUP.md` backup section to cross-reference `SYNC_DOWN.md`
  **Dependencies**: 4.4

---

## Phase 5: Integration (wp-integration)

- [ ] 5.1 Write drift test `tests/contract/test_openapi_drift.py` — FastAPI runtime `/openapi.json` matches `contracts/openapi/v1.yaml` for new endpoints
  **Dependencies**: 1.2, 1.4, 1.6, 1.8, 1.10, 1.12, 2.6

- [ ] 5.2 Run full test suite: `pytest tests/ -v`
  **Dependencies**: 5.1, 3.11

- [ ] 5.3 Run contract tests: `pytest tests/contract/ -m contract --no-cov`
  **Dependencies**: 5.1

- [ ] 5.4 Smoke test against local stack: `make dev-bg` + `curl https://localhost:8000/api/v1/kb/search?q=test` + verify audit_log row
  **Dependencies**: 5.1, 2.4

- [ ] 5.5 MCP E2E test: start MCP server with HTTP config pointing at local API; verify tool returns result via HTTP path
  **Dependencies**: 5.4

- [ ] 5.6 Update `CLAUDE.md` gotchas table with any new patterns surfaced during implementation
  **Dependencies**: 5.5

- [ ] 5.7 Mark all tasks complete; run `openspec validate --strict cloud-db-source-of-truth`
  **Dependencies**: 5.6

---

## Acceptance Criteria

The change is complete when:

1. All 8 new HTTP endpoints respond with correct status codes and schemas matching the OpenAPI contract
2. All destructive endpoints produce `audit_log` entries with correct operation tagging
3. All 4 refactored MCP tools pass schema-identity test (pre/post refactor)
4. MCP tools work in both HTTP mode (with config) and in-process fallback (without config)
5. `aca manage restore-from-cloud` successfully restores a Railway MinIO backup to a local DB
6. OpenAPI drift test passes
7. Full test suite passes
8. `openspec validate --strict cloud-db-source-of-truth` exits 0
