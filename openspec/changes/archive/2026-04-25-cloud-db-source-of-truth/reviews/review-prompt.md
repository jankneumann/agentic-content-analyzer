# Plan Review — cloud-db-source-of-truth

You are reviewing an OpenSpec proposal for the `cloud-db-source-of-truth` change. Your role is an **independent reviewer** — do not implement anything, do not modify any files. Produce only a JSON findings document.

## Context

- Change establishes Railway cloud Postgres as authoritative data store
- Closes MCP↔HTTP parity gaps so external consumer `agentic-assistant` can integrate via HTTP
- Coordinated tier: 5 work packages, contract-first parallel lanes intended

## Artifacts to read (all paths relative to CWD)

- `openspec/changes/cloud-db-source-of-truth/proposal.md` — motivation, approaches, selected approach
- `openspec/changes/cloud-db-source-of-truth/design.md` — 8 architectural decisions (D1–D8), data model, rollout
- `openspec/changes/cloud-db-source-of-truth/tasks.md` — 39 tasks across 5 phases (0: contracts, 1: API, 2: audit, 3: MCP, 4: ops, 5: integration)
- `openspec/changes/cloud-db-source-of-truth/work-packages.yaml` — 5 work packages (wp-contracts, wp-audit, wp-api, wp-mcp, wp-integration) with DAG, scopes, locks
- `openspec/changes/cloud-db-source-of-truth/specs/audit-log/spec.md` — audit-log capability (4 requirements)
- `openspec/changes/cloud-db-source-of-truth/specs/knowledge-base/spec.md` — KB HTTP endpoints (2 requirements)
- `openspec/changes/cloud-db-source-of-truth/specs/knowledge-graph/spec.md` — graph HTTP endpoints (2 requirements)
- `openspec/changes/cloud-db-source-of-truth/specs/content-references/spec.md` — reference HTTP endpoints (2 requirements)
- `openspec/changes/cloud-db-source-of-truth/specs/mcp-http-client/spec.md` — MCP refactor (2 requirements)
- `openspec/changes/cloud-db-source-of-truth/contracts/openapi/v1.yaml` — HTTP contract
- `openspec/changes/cloud-db-source-of-truth/contracts/db/schema.sql` — audit_log schema

## Review Dimensions

Evaluate against these dimensions. Cite specific file:line references when flagging issues.

1. **Specification Completeness** — SHALL/MUST language, testability, unambiguous terms
2. **Contract Consistency** — OpenAPI matches specs; DB schema supports all operations; required vs optional fields align
3. **Architecture Alignment** — follows existing patterns (FastAPI middleware chain, Alembic migrations, CLI Typer layout)
4. **Security** — auth enforcement, input validation, credential/PII handling, OWASP top 10, middleware ordering
5. **Performance** — no unbounded queries; pagination; async where warranted; index coverage
6. **Observability** — structured logging, metrics, tracing requirements (project uses Langfuse + OTel)
7. **Compatibility** — breaking changes to existing APIs; migration reversibility
8. **Resilience** — retry/timeout/fallback for external dependencies (Graphiti/Neo4j/FalkorDB, MinIO, HTTP); failure mode analysis
9. **Work Package Validity** — DAG has no cycles; parallel packages have non-overlapping write scopes; lock keys canonicalized; integration package depends on all implementation packages

## Output Format

Output **only** a JSON object matching this schema (no markdown, no prose commentary):

```json
{
  "review_type": "plan",
  "target": "cloud-db-source-of-truth",
  "reviewer_vendor": "<your-model-name-and-version>",
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

Empty `findings` array is acceptable if you find no issues.

## Important

- You are an **independent** reviewer. Do not coordinate with other reviewers; do not consult prior findings if they exist.
- Focus on **substantive** issues. Don't flag trivial style when real correctness/security issues exist.
- Be **specific**: "the spec is vague" → "spec §X says 'stale topics' but never defines a threshold".
- Include `file:line` references where practical so findings are actionable.
- Your output is consumed by an automated synthesizer that merges findings from multiple vendors — deterministic JSON only.
