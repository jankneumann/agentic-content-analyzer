# Plan Review ROUND 2 — cloud-db-source-of-truth

You are reviewing an OpenSpec proposal for the `cloud-db-source-of-truth` change after a PLAN_FIX pass that resolved round-1 findings. Your role is an **independent reviewer** — do not implement anything, do not modify any files. Produce only a JSON findings document.

## What changed since round 1 (context only — evaluate the CURRENT artifacts)

The PLAN_FIX pass locked in two owner policy decisions:

1. **Audit-everything**: every `/api/v1/*` request is logged (including 401/403 auth failures). OPTIONS preflight bypasses audit. Write failures are non-blocking (stderr only).
2. **MCP adopts OpenAPI shapes (breaking change accepted)**: the previous "byte-identical MCP schemas" requirement was replaced with "MCP conforms to OpenAPI shapes"; the sole consumer set (@jankneumann + `agentic-assistant`) will migrate in lockstep.

The work-packages DAG was also split: `wp-ops` is now its own parallel package; `src/api/app.py` write ownership moved to `wp-audit`.

## Context

- Change establishes Railway cloud Postgres as authoritative data store
- Closes MCP↔HTTP parity gaps so external consumer `agentic-assistant` can integrate via HTTP
- Coordinated tier: now 6 work packages (wp-contracts, wp-audit, wp-api, wp-mcp, wp-ops, wp-integration)

## Artifacts to read (all paths relative to CWD)

- `openspec/changes/cloud-db-source-of-truth/proposal.md`
- `openspec/changes/cloud-db-source-of-truth/design.md` (now D1–D11 + extended sections)
- `openspec/changes/cloud-db-source-of-truth/tasks.md` (~44 tasks)
- `openspec/changes/cloud-db-source-of-truth/work-packages.yaml` (6 packages)
- `openspec/changes/cloud-db-source-of-truth/specs/audit-log/spec.md`
- `openspec/changes/cloud-db-source-of-truth/specs/knowledge-base/spec.md`
- `openspec/changes/cloud-db-source-of-truth/specs/knowledge-graph/spec.md`
- `openspec/changes/cloud-db-source-of-truth/specs/content-references/spec.md`
- `openspec/changes/cloud-db-source-of-truth/specs/mcp-http-client/spec.md`
- `openspec/changes/cloud-db-source-of-truth/contracts/openapi/v1.yaml`
- `openspec/changes/cloud-db-source-of-truth/contracts/db/schema.sql`
- `openspec/changes/cloud-db-source-of-truth/contracts/db/seed.sql`

## Review Dimensions (same as round 1)

Evaluate against these dimensions. Cite specific file:line references when flagging issues.

1. **Specification Completeness** — SHALL/MUST language, testability, unambiguous terms
2. **Contract Consistency** — OpenAPI matches specs; DB schema supports all operations; required vs optional fields align
3. **Architecture Alignment** — follows existing patterns
4. **Security** — auth enforcement, input validation, middleware ordering (now with audit wrapping auth failures)
5. **Performance** — no unbounded queries; pagination; async where warranted; index coverage
6. **Observability** — structured logging, metrics, tracing (request_id in audit, OTel attrs)
7. **Compatibility** — MCP breaking change is accepted; flag any OTHER breaking changes not declared
8. **Resilience** — timeout/retry matrix in D11; 504 on graph timeouts; middleware non-blocking
9. **Work Package Validity** — DAG has no cycles; parallel packages have non-overlapping write scopes; verify wp-ops lane is genuinely parallel; verify `src/api/app.py` is owned by exactly one writer

## Specifically verify (round-1 findings)

Check whether each of the following round-1 findings has been resolved. For any unresolved or partially-resolved item, emit a finding citing file:line:

- Audit semantics are internally consistent across spec, OpenAPI, design, and seed data (all /api/v1/* logged)
- Middleware ordering is specified so audit rows exist for 401/403 and OPTIONS preflight bypasses audit
- pg_cron retention uses migration-time interpolation, NOT `current_setting()` GUCs
- Work-packages DAG has `wp-ops` as a separate parallel lane; `src/api/app.py` has a single writer
- MCP tool shape conformance is declared and testable against OpenAPI schemas; warning channel is stderr
- References endpoints are bounded (max content_ids, batch_size caps, has_more/cursor)
- OpenAPI declares Problem on 404/409/401/422; `last_compiled_at` required on TopicSearchResult; `score` required on GraphRelationship
- Graph endpoints declare 504 on backend timeouts
- MCP transport has a specified timeout and retry matrix
- Observability requirements tie request_id to audit rows and define OTel span attributes

## Output Format

Output **only** a JSON object matching this schema (no markdown, no prose commentary):

```json
{
  "review_type": "plan_r2",
  "target": "cloud-db-source-of-truth",
  "reviewer_vendor": "<your-model-name-and-version>",
  "round1_resolutions": {
    "audit_semantics_aligned": "resolved | partial | unresolved",
    "middleware_ordering_specified": "resolved | partial | unresolved",
    "pg_cron_migration_time_interpolation": "resolved | partial | unresolved",
    "wp_ops_split": "resolved | partial | unresolved",
    "app_py_single_writer": "resolved | partial | unresolved",
    "mcp_openapi_shape_conformance": "resolved | partial | unresolved",
    "references_bounded_batches": "resolved | partial | unresolved",
    "openapi_problem_refs_and_required_fields": "resolved | partial | unresolved",
    "graph_504_declared": "resolved | partial | unresolved",
    "mcp_transport_resilience": "resolved | partial | unresolved",
    "observability_requirements": "resolved | partial | unresolved"
  },
  "findings": [
    {
      "id": "PR-001",
      "type": "spec_gap | contract_mismatch | architecture | security | performance | correctness | observability | compatibility | resilience | style",
      "criticality": "low | medium | high | critical",
      "description": "<specific issue with file:line references>",
      "resolution": "<actionable fix>",
      "disposition": "fix | regenerate | accept | escalate"
    }
  ]
}
```

Empty `findings` array is acceptable if you find no new issues. Focus on issues INTRODUCED by PLAN_FIX or left unresolved from round 1.

## Important

- You are an **independent** reviewer. Do not coordinate with other reviewers.
- Focus on **substantive** issues.
- Be **specific**: cite file:line references.
- Your output is consumed by an automated synthesizer — deterministic JSON only.
