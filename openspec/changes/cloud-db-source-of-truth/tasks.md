# Tasks: cloud-db-source-of-truth

Task IDs follow `<phase>.<seq>` convention. Test tasks precede their implementation counterparts (TDD). Each implementation task lists its dependency on the corresponding test task.

Phase → Work Package mapping:
- Phase 0 → `wp-contracts`
- Phase 1 → `wp-api`
- Phase 2 → `wp-audit`
- Phase 3 → `wp-mcp`
- Phase 4 → `wp-ops` (parallel with wp-api/wp-audit/wp-mcp after wp-contracts)
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

- [ ] 0.5 Apply seed rows from `contracts/db/seed.sql` to fixture DB and assert row count = 6 (includes read, audited destructive, resolve, 500 error with notes, 401 no-credentials with `notes.auth_failure="missing_key"`, 403 invalid-key with `admin_key_fp` set and `notes.auth_failure="invalid_key"`)
  **Contracts**: `contracts/db/seed.sql`
  **Dependencies**: 0.4

---

## Phase 1: HTTP API Endpoints (wp-api)

### 1A: KB search + lint

- [ ] 1.1 Write route tests for `GET /api/v1/kb/search` — matching query, empty result, auth enforcement, limit parameter, `last_compiled_at` present on every result
  **Spec scenarios**: knowledge-base:Search with matching query, Search with no matches, Unauthenticated search, Search honors limit
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1kb~1search`
  **Dependencies**: 0.2

- [ ] 1.2 Implement `src/api/routes/kb_search_routes.py` — handler, Pydantic models from contracts, service wiring (must populate `last_compiled_at` on every result)
  **Dependencies**: 1.1

- [ ] 1.3 Write route tests for `GET /api/v1/kb/lint` and `POST /api/v1/kb/lint/fix` — read-only vs mutation, audit-row operation tagging, zero-diff case, quantitative thresholds (stale >30d, orphaned zero-refs-and-zero-degree, score anomaly >3σ with minimum-sample-size guard)
  **Spec scenarios**: knowledge-base:GET lint returns health report, POST lint/fix applies corrections, POST lint/fix when no corrections needed
  **Design decisions**: D3 (middleware + @audited)
  **Contracts**: `contracts/openapi/v1.yaml` (kb lint paths)
  **Dependencies**: 0.2

- [ ] 1.4 Implement KB lint routes (extend `src/api/routes/kb_routes.py`) with `@audited(operation="kb.lint.fix")` on fix endpoint
  **Dependencies**: 1.3, 2.2

### 1B: Graph query + extract-entities

- [ ] 1.5 Write route tests for `POST /api/v1/graph/query` — entity/relationship shape (incl. required `score` on relationships), empty result, validation, 504 on graph timeout
  **Spec scenarios**: knowledge-graph:Graph query returns entities and relationships, Graph query with empty result, Graph query validates query field
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1graph~1query`
  **Dependencies**: 0.2

- [ ] 1.6 Implement `src/api/routes/graph_routes.py` — query handler, `GraphitiClient` wiring with 10s read timeout; map timeout → 504 Problem response
  **Dependencies**: 1.5

- [ ] 1.7 Write route tests for `POST /api/v1/graph/extract-entities` — success, 404 missing content (Problem body), 409 no summary (Problem body), audit operation tag, 504 on graph timeout
  **Spec scenarios**: knowledge-graph:Extract entities for existing content, Extract entities for missing content, Extract entities for content without summary
  **Design decisions**: D3 (audited decorator)
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1graph~1extract-entities`
  **Dependencies**: 0.2

- [ ] 1.8 Implement extract-entities handler with `@audited(operation="graph.extract_entities")`; 30s write timeout; 404/409 return `application/problem+json`
  **Dependencies**: 1.7, 2.2

### 1C: References extract + resolve

- [ ] 1.9 Write route tests for `POST /api/v1/references/extract` — by IDs, by date range with bounded batch, `has_more`/`next_cursor` pagination, `per_content` is optional (may be omitted on large batches), conflicting-filter 422, oversized `content_ids` 422, 60s batch timeout → 504 Problem
  **Spec scenarios**: content-references:Extract references for content batch by IDs, Extract references for content by date range (bounded batch), Extract references rejects conflicting filters, Extract references rejects oversized content_ids, Extract references returns 504 on per-batch timeout
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1references~1extract`
  **Dependencies**: 0.2

- [ ] 1.10 Implement references/extract handler with `@audited(operation="references.extract")`; extend or create `src/api/routes/reference_routes.py`; coordinate with `add-content-references` proposal for scope overlap
  **Dependencies**: 1.9, 2.2

- [ ] 1.11 Write route tests for `POST /api/v1/references/resolve` — default batch, explicit batch_size, `has_more` pagination, oversized batch 422, 60s batch timeout → 504 Problem
  **Spec scenarios**: content-references:Resolve all unresolved references uses default batch, Resolve with explicit batch limit, Resolve rejects oversized batch_size, Resolve returns 504 on per-batch timeout
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1references~1resolve`
  **Dependencies**: 0.2

- [ ] 1.12 Implement references/resolve handler with `@audited(operation="references.resolve")`
  **Dependencies**: 1.11, 2.2

- [ ] 1.13 Retrofit `@audited` on existing destructive endpoints listed in proposal.md §2: `DELETE /topics/{slug}` (audit operation `topics.delete`), `POST /kb/purge` (`kb.purge`), `POST /manage/switch-embeddings` (`manage.switch_embeddings`). Write `tests/api/test_destructive_endpoints_audited.py` asserting each endpoint produces an audit row with the expected `operation` tag.
  **Spec scenarios**: audit-log:Operation tagging via @audited decorator:Decorated endpoint records operation name
  **Dependencies**: 2.2

---

## Phase 2: Audit Logging (wp-audit)

- [ ] 2.1 Write tests for `AuditMiddleware` — every `/api/v1/*` request logged (success AND failure), OPTIONS bypass, admin_key_fp fingerprinting (SHA-256 last 8 chars from raw `X-Admin-Key` header whenever present including invalid keys, NULL only when header absent), body_size capture, 401 no-credentials logging with `notes.auth_failure="missing_key"`, 403 invalid-key logging with `admin_key_fp` set AND `notes.auth_failure="invalid_key"`, client_ip from `Cf-Connecting-Ip`/`X-Forwarded-For`/`request.client.host` fallback chain, write-failure is non-blocking (stderr log, no exception propagation)
  **Spec scenarios**: audit-log:Request to any /api/v1/* endpoint creates log entry, No credentials (401) is logged, Invalid admin key (403) is logged with fingerprint, OPTIONS preflight requests are not logged, Request body is not stored, Failed request is still logged, Audit write failure does not block the response, Client IP is extracted via proxy-aware headers
  **Design decisions**: D3, D3a (middleware ordering + admin_key_fp always-compute-when-header-present policy), D4 (append-only schema), D4b (best-effort semantics)
  **Contracts**: `contracts/db/schema.sql`
  **Dependencies**: 0.4

- [ ] 2.2 Implement `src/api/middleware/audit.py` — middleware + `@audited` decorator; decorator adds `operation` to the row the middleware writes (decorator is NOT a gate, it is metadata enrichment)
  **Dependencies**: 2.1

- [ ] 2.3 Write middleware-ordering test — assert registration order in `src/api/app.py` is `[TraceMiddleware, AuditMiddleware, AuthMiddleware, CORSMiddleware]` (outermost-first) so audit wraps auth failures AND CORS/OPTIONS bypass still works
  **Design decisions**: D3a
  **Dependencies**: 2.2

- [ ] 2.4 Write Alembic migration test — upgrade creates `audit_log` table with correct schema, downgrade removes it
  **Contracts**: `contracts/db/schema.sql`
  **Dependencies**: 0.4

- [ ] 2.5 Create Alembic migration `alembic/versions/<rev>_add_audit_log_table.py`
  **Dependencies**: 2.4

- [ ] 2.6 Write tests for `GET /api/v1/audit` — time range, operation filter, status_code filter, exact-match path filter, invalid-path-pattern → 422, limit clamping
  **Spec scenarios**: audit-log:Query recent audit entries, Query by operation, Query by exact path, Invalid path filter is rejected, Query respects max limit
  **Contracts**: `contracts/openapi/v1.yaml#/paths/~1api~1v1~1audit`
  **Dependencies**: 0.2, 2.5

- [ ] 2.7 Implement `src/api/routes/audit_routes.py` — query endpoint with filters (exact-match path with pattern validation)
  **Dependencies**: 2.6

- [ ] 2.8 Write test for pg_cron retention job — simulate old row, run retention SQL with an interpolated interval value, assert deletion; test also asserts that the Alembic migration INTERPOLATES the retention-days value literally into the cron command (no `current_setting(...)` GUC call in the resulting SQL)
  **Spec scenarios**: audit-log:Retention job deletes old entries, Retention interval is fixed by migration, not runtime
  **Design decisions**: D4a (migration-time interpolation)
  **Dependencies**: 2.5

- [ ] 2.9 Create data migration registering pg_cron retention job — read `AUDIT_LOG_RETENTION_DAYS` at migration time, interpolate into cron SQL (NOT `current_setting`)
  **Dependencies**: 2.8

- [ ] 2.10 Write observability test — assert `AuditMiddleware` sets OTel span attributes (`audit.operation`, `audit.status_code`, `audit.write_failure` on error) and `TraceMiddleware`'s request_id flows into `audit_log.request_id`
  **Spec scenarios**: audit-log:Audit middleware observability attributes (all 3 scenarios — audit span populated on success, marks write failure, trace ID correlation)
  **Design decisions**: D10 (observability inherits FastAPI stack; audit span SHALL clauses)
  **Dependencies**: 2.2

---

## Phase 3: MCP Refactor (wp-mcp)

- [ ] 3.1 Write test for `_get_api_client()` helper — returns ApiClient when both env vars set, None when unset, None for localhost default, emits stderr warning (NOT tool-response text) on partial config
  **Spec scenarios**: mcp-http-client:MCP tool with HTTP config uses ApiClient, MCP tool without HTTP config falls back to in-process, MCP tool with partial config emits stderr warning and falls back
  **Design decisions**: D2 (fallback semantics), D9 (OpenAPI-aligned shapes)
  **Dependencies**: None

- [ ] 3.2 Implement `_get_api_client()` helper in `src/mcp_server.py`; warnings emit to stderr via `logging` configured to use `sys.stderr`
  **Dependencies**: 3.1

- [ ] 3.3 Write HTTP-transport resilience tests — 30s timeout, one retry on {429,502,503,504,connreset}, non-retryable 4xx propagates, timeout does NOT fall back to in-process
  **Spec scenarios**: mcp-http-client:Transient 503 is retried once, Non-retryable 400 is surfaced directly, HTTP timeout falls back to error, not to in-process
  **Design decisions**: D11 (timeout/retry matrix)
  **Dependencies**: 3.2

- [ ] 3.4 Update `src/cli/api_client.py` to support 30s timeout + one-shot retry for transient errors (or add a thin wrapper — whichever preserves CLI behavior)
  **Dependencies**: 3.3

- [ ] 3.5 Write integration tests for `search_knowledge_base` MCP tool — HTTP mode hits mocked API and returns `KBSearchResponse` shape; in-process mode returns the SAME shape (not legacy `{name, summary, relevance_score, mention_count}`)
  **Spec scenarios**: mcp-http-client:MCP tool with HTTP config uses ApiClient, HTTP and in-process modes produce identical shapes, Tool response validates against OpenAPI schema
  **Dependencies**: 3.4, 1.2

- [ ] 3.6 Refactor `search_knowledge_base` MCP tool — HTTP path + in-process path both return `{topics, total_count}` with `last_compiled_at`
  **Dependencies**: 3.5

- [ ] 3.7 Write integration tests for `search_knowledge_graph` MCP tool — both modes return `{entities, relationships}` with `score` on every relationship
  **Dependencies**: 3.4, 1.6

- [ ] 3.8 Refactor `search_knowledge_graph` MCP tool
  **Dependencies**: 3.7

- [ ] 3.9 Write integration tests for `extract_references` MCP tool — both modes return `{references_extracted, content_processed, has_more, per_content}` (NOT legacy `{scanned, references_found, dry_run}`)
  **Dependencies**: 3.4, 1.10

- [ ] 3.10 Refactor `extract_references` MCP tool
  **Dependencies**: 3.9

- [ ] 3.11 Write integration tests for `resolve_references` MCP tool — both modes return `{resolved_count, still_unresolved_count, has_more}` (NOT legacy `{resolved, batch_size}`)
  **Dependencies**: 3.4, 1.12

- [ ] 3.12 Refactor `resolve_references` MCP tool
  **Dependencies**: 3.11

- [ ] 3.13 Write OpenAPI-shape-conformance test — for each of the 4 refactored tools, validate its response payload (both HTTP and in-process modes) against the corresponding response schema in `contracts/openapi/v1.yaml` using `jsonschema`
  **Spec scenarios**: mcp-http-client:Tool response validates against OpenAPI schema
  **Dependencies**: 3.6, 3.8, 3.10, 3.12

- [ ] 3.14 Add `--strict-http` flag to MCP server startup; test rejects unconfigured startup (stderr error + tool-invocation errors)
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

- [ ] 5.1 Write drift test `tests/contract/test_openapi_drift.py` — FastAPI runtime `/openapi.json` matches `contracts/openapi/v1.yaml` for new endpoints (including Problem refs on 401/422/404/409/504)
  **Dependencies**: 1.2, 1.4, 1.6, 1.8, 1.10, 1.12, 2.7

- [ ] 5.2 Run full test suite: `pytest tests/ -v`
  **Dependencies**: 5.1, 3.13

- [ ] 5.3 Run contract tests: `pytest tests/contract/ -m contract --no-cov`
  **Dependencies**: 5.1

- [ ] 5.4 Smoke test against local stack: `make dev-bg` + `curl http://localhost:8000/api/v1/kb/search?q=test` + verify audit_log row written for the successful request AND a separate row for an unauthenticated attempt (401)
  **Dependencies**: 5.1, 2.5

- [ ] 5.5 MCP E2E test: start MCP server with HTTP config pointing at local API; verify tool returns result via HTTP path with OpenAPI-conformant shape
  **Dependencies**: 5.4

- [ ] 5.6 Update `CLAUDE.md` gotchas table with any new patterns surfaced during implementation (e.g., middleware ordering, pg_cron migration-time interpolation, MCP breaking-change migration for agentic-assistant)
  **Dependencies**: 5.5

- [ ] 5.7 Coordinate with `agentic-assistant` repo: confirm the consumer project has been updated to the new MCP response shapes before merging this change. Record the agentic-assistant commit SHA or PR link in the `MIGRATION.md` notes.
  **Dependencies**: 3.13

- [ ] 5.8 Mark all tasks complete; run `openspec validate --strict cloud-db-source-of-truth`
  **Dependencies**: 5.6, 5.7

---

## Acceptance Criteria

The change is complete when:

1. All 8 new HTTP endpoints respond with correct status codes and schemas matching the OpenAPI contract (including 401/422 Problem responses, and 504 on graph timeouts)
2. Every `/api/v1/*` request (including 401/403 auth failures) produces an `audit_log` row; OPTIONS preflight requests are excluded; audit write failures do not block responses
3. All 4 refactored MCP tools return responses that validate against the OpenAPI schemas in both HTTP mode and in-process fallback mode (breaking change migration for `agentic-assistant` confirmed)
4. MCP tools use 30s timeout + one retry for transient HTTP errors; timeouts produce errors rather than silent fallback
5. `aca manage restore-from-cloud` successfully restores a Railway MinIO backup to a local DB
6. pg_cron retention job has the retention days interpolated literally (no `current_setting` GUC call)
7. OpenAPI drift test passes
8. Full test suite passes
9. `openspec validate --strict cloud-db-source-of-truth` exits 0
