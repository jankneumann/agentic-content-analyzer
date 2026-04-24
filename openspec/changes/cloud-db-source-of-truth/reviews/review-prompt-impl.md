# Implementation Review — cloud-db-source-of-truth

You are reviewing the IMPLEMENTED code for OpenSpec change `cloud-db-source-of-truth`. Your role is an **independent reviewer** — do not modify any files. Produce only a JSON findings document.

## Scope

7 commits on branch `openspec/cloud-db-source-of-truth` (since main). Stat: 67 files changed, +9929 / -66 lines. Full test suite has 177 passing + 1 skipped.

```
8fc616e wp-contracts: validate OpenAPI + generate Pydantic/TS stubs
7905fdd wp-audit:     audit middleware + decorator + audit_log migration + /api/v1/audit
50b511b wp-ops:       aca manage restore-from-cloud + SYNC_DOWN.md
756a547 wp-api:       6 new HTTP endpoints (kb search/lint, graph query/extract, refs extract/resolve)
0d5af92 wp-api 1.13:  @audited retrofit on DELETE /topics/{slug}
fd4446f wp-mcp:       refactor 4 MCP tools to OpenAPI shapes + transport resilience
461ba55 wp-integration: drift test + MIGRATION.md + CLAUDE.md gotchas
```

## Context (round-2 PLAN_FIX policy decisions, baked into the spec)

- **Audit-everything**: every /api/v1/* request writes an audit_log row, including 401/403 auth failures. OPTIONS bypasses. Write failures are best-effort (stderr log, non-blocking).
- **MCP breaking change**: tools adopt OpenAPI response shapes in both HTTP and in-process modes. Sole consumer (`agentic-assistant`) migrates in lockstep.
- **Middleware order** (outermost first): Trace → Audit → Auth → CORS.
- **admin_key_fp**: always compute SHA-256 last-8 from raw X-Admin-Key header when present (including invalid keys). NULL only when header absent.
- **pg_cron retention**: interpolated at migration time (not current_setting GUC — Railway restricts custom GUCs).

## Artifacts to read

### Plan / spec (source of truth)

- `openspec/changes/cloud-db-source-of-truth/proposal.md`, `design.md`, `tasks.md`
- `openspec/changes/cloud-db-source-of-truth/specs/audit-log/spec.md`
- `openspec/changes/cloud-db-source-of-truth/specs/knowledge-base/spec.md`
- `openspec/changes/cloud-db-source-of-truth/specs/knowledge-graph/spec.md`
- `openspec/changes/cloud-db-source-of-truth/specs/content-references/spec.md`
- `openspec/changes/cloud-db-source-of-truth/specs/mcp-http-client/spec.md`
- `openspec/changes/cloud-db-source-of-truth/contracts/openapi/v1.yaml`
- `openspec/changes/cloud-db-source-of-truth/contracts/db/schema.sql`
- `openspec/changes/cloud-db-source-of-truth/contracts/db/seed.sql`
- `openspec/changes/cloud-db-source-of-truth/MIGRATION.md`

### Implementation code (what you're reviewing)

- `src/api/middleware/audit.py` — AuditMiddleware + `@audited` decorator
- `src/api/app.py` — middleware registration + router includes (check order!)
- `src/api/routes/audit_routes.py` — GET /api/v1/audit
- `src/api/routes/kb_search_routes.py` — GET /api/v1/kb/search
- `src/api/routes/kb_routes.py` — GET /api/v1/kb/lint, POST /api/v1/kb/lint/fix
- `src/api/routes/graph_routes.py` — POST /api/v1/graph/query, POST /api/v1/graph/extract-entities
- `src/api/routes/reference_routes.py` — POST /api/v1/references/extract, POST /api/v1/references/resolve
- `src/api/schemas/kb.py`, `graph.py`, `references.py` — Pydantic schemas
- `src/api/kb_routes.py` — retrofitted DELETE /topics/{slug}
- `alembic/versions/b7a1c9d5e2f0_add_audit_log_table.py`
- `src/cli/api_client.py` — extended with retry + MCP endpoint methods
- `src/cli/restore_commands.py` — restore-from-cloud CLI
- `src/cli/manage_commands.py` — wiring
- `src/mcp_server.py` — 4 refactored MCP tools (`search_knowledge_base`, `search_knowledge_graph`, `extract_references`, `resolve_references`) + `_get_api_client()` helper + strict-http flag
- `docs/SYNC_DOWN.md`, `docs/SETUP.md`

### Tests

- `tests/api/test_audit_*.py` (5 files)
- `tests/api/test_kb_*.py` (2 files), `test_graph_routes.py`, `test_reference_routes.py`, `test_destructive_endpoints_audited.py`
- `tests/unit/test_audit_decorator.py`
- `tests/mcp/test_mcp_*.py` (4 files)
- `tests/cli/test_restore_from_cloud.py`, `test_api_client_retry.py`
- `tests/contract/test_openapi_drift.py`

## Review Dimensions

Evaluate against:

1. **Spec compliance** — each MUST/SHALL in the spec files has a corresponding implementation AND test. Cite scenario + file:line.
2. **Contract conformance** — route handlers' response shapes match OpenAPI exactly. MCP tool outputs conform to OpenAPI shapes in BOTH HTTP and in-process modes.
3. **Middleware order** — `src/api/app.py` registers middleware in an order that produces runtime outer → inner: Trace → Audit → Auth → CORS. Verify by reading the registration code, not trusting the comment.
4. **Audit log semantics** — verify 401/403 paths actually write rows; OPTIONS is bypassed; admin_key_fp is always computed from raw header; write failures are non-blocking; client_ip uses the proxy chain.
5. **Alembic migration** — the migration creates the schema matching `contracts/db/schema.sql`; pg_cron retention is interpolated at migration time (no `current_setting`); upgrade+downgrade both work.
6. **Security** — no SQL injection (the audit routes build SQL dynamically — verify the where-clause vocabulary is closed); no credential leakage in logs (admin_key_fp is last-8 of sha256, not the raw key); rate-limit / DoS considerations on unbounded endpoints.
7. **Resilience** — D11 timeout/retry matrix faithfully implemented. Graph endpoints return 504 on timeout. References batches bounded. MCP transport retries on {429, 502, 503, 504}.
8. **Test coverage** — every spec scenario is covered by a test. Every defect the tests would catch should have a failing-first test.
9. **Code quality** — no obvious dead code, no scope creep beyond the proposal, no missing error handling at system boundaries.
10. **MIGRATION.md completeness** — is the agentic-assistant migration checklist concrete enough that the consumer side can actually follow it?

## Output Format

Output **only** a JSON object:

```json
{
  "review_type": "impl",
  "target": "cloud-db-source-of-truth",
  "reviewer_vendor": "<your-model-name-and-version>",
  "findings": [
    {
      "id": "IR-001",
      "type": "spec_gap | contract_mismatch | middleware_order | audit_semantics | migration | security | performance | resilience | test_coverage | correctness | observability | style",
      "criticality": "low | medium | high | critical",
      "description": "<specific issue with file:line references>",
      "resolution": "<actionable fix>",
      "disposition": "fix | accept | escalate"
    }
  ]
}
```

## Important

- You are an **independent** reviewer. Do not coordinate with other reviewers.
- Focus on **substantive** issues. Cite file:line where possible.
- If you find no substantive issues, return an empty `findings` array. Don't pad with style nits if the code is sound.
- Your output is consumed by an automated synthesizer — deterministic JSON only.
