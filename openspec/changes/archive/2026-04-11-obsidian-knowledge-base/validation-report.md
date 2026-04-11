# Validation Report: obsidian-knowledge-base

**Date**: 2026-04-10
**Commit**: 1b508ce
**Branch**: openspec/obsidian-knowledge-base
**Iteration**: Post-iteration 3 (review remediation complete)

## Phase Results

| Phase | Status | Details |
|-------|--------|---------|
| Deploy | ✓ pass | Reused running Postgres (:5432); fresh uvicorn on :8001 from worktree |
| pytest | ✓ pass | 107/107 KB tests green in 2.03s |
| openspec validate | ✓ pass | `--strict` returns valid |
| Smoke | ✓ pass | 10/10 applicable smoke tests (health, ready, auth rejection x2, error sanitization x4, CORS x2) |
| Live Endpoints | ✓ pass | 16/16 probes: CRUD (6), auth (1), 404 (1), index (1), notes (2), validation fixes (3: bad_cat/bad_score/bad_note → 422), MERGED hidden from default list (1) |
| Spec Compliance | ✓ pass | 14/14 requirements verified with live evidence (change-context.md updated at d248a90, still accurate at 1b508ce) |
| Log Analysis | ✓ pass | Clean: 0 real errors, 0 stack traces (1 Pydantic deprecation from graphiti_core, 1 Postgres collation warning — both pre-existing infrastructure noise) |
| Gen-Eval | ○ skip | No gen-eval descriptors in project |
| Security | ○ skip | ZAP/OWASP DC not configured |
| E2E | ○ skip | No KB-specific Playwright tests |
| Architecture | ○ skip | No architecture.graph.json artifact |
| CI/CD | ⚠ infra | All 8 jobs fail in 2-3s (runner setup issue, not code). Same pattern on prior validation run. Railway: no deployment needed. |

## Changes Since Last Validation (d248a90 → 1b508ce)

Iteration 2 (`8f15fb2`):
- MERGED topics excluded from default API list
- Deprecated `.get()` replaced with `session.get()`

Iteration 3 (`1b508ce`) — review remediation:
- Q&A + MCP search exclude MERGED topics (consistency with API list)
- Q&A LLM call has 120s timeout via `asyncio.wait_for`
- Q&A prompt truncates articles to 300 words per topic
- Obsidian export batch-loads source content (N+1 → single query)
- Q&A structured logging (topics_matched, selected, elapsed)
- Health merge detection uses pre-tokenized word sets
- Obsidian topic body render accepts session parameter
- mypy override scope documented in pyproject.toml comment

## Warnings

1. **CI/CD infrastructure**: All jobs fail in 2-3 seconds — runner setup failure, not code regression. Verified same behavior on main branch and prior commits.
2. **HNSW embedding index**: Not created (unconstrained `vector` column). No functional impact below 1000 topics.
3. **Rate limiting**: `POST /compile` not rate-limited. Tracked in impl-findings.md.

## Result

**PASS (with CI warning)** — All code-level, live-service, and spec-compliance phases pass. CI infrastructure failures are pre-existing and not related to this PR.

Ready for:
```
/cleanup-feature obsidian-knowledge-base
```
