# Implementation Findings: obsidian-knowledge-base

## Iteration 1 (2026-04-09)

Review of the implementation at commit `ab3cfa4` (post-initial implementation, pre-iteration) surfaced 14 findings. Threshold: medium.

### Addressed this iteration

| # | Type | Criticality | Description | Fix | Files |
|---|------|-------------|-------------|-----|-------|
| 1 | bug | high | `_run_compile` `try/finally` swallowed exceptions without rollback, leaving the session in a broken state | Added `except Exception` branch that rolls back before re-raising; `finally` still releases the lock | `src/services/knowledge_base.py` |
| 2 | bug | high | `_write_sentinel_lock` rolled back the outer transaction on insert failure | Wrapped the sentinel write in `begin_nested()` savepoint | `src/services/knowledge_base.py` |
| 4 | performance | medium | `_detect_merge_candidates` re-tokenized articles inside the O(N²) pairwise loop | Pre-tokenize each article once; added `_tokenize` + `_jaccard` helpers | `src/services/knowledge_base.py` |
| 5 | bug | medium | `TopicUpdate.relevance_score` had no bounds; clients could send `999999` | Added `Field(..., ge=0.0, le=1.0)` | `src/api/kb_routes.py` |
| 6 | bug | medium | `create_topic` / `update_topic` didn't validate `category` against `ThemeCategory` | Added Pydantic `field_validator`, returns 422 with a list of valid categories | `src/api/kb_routes.py` |
| 7 | bug | medium | `add_note` accepted arbitrary `note_type` strings, leading to opaque 500s on commit | Validate `note_type` via `TopicNoteType` enum at both API and service layer; 422 with valid list | `src/api/kb_routes.py`, `src/services/knowledge_base.py` |
| 8 | observability | medium | KB compile had no structured logging of run lifecycle | Added `run_id` (12-char hex UUID); log `kb_compile.start` + `kb_compile.finish` with structured fields | `src/services/knowledge_base.py` |
| 9 | resilience | medium | LLM call in `_render_article` had no timeout — a stuck upstream would hold the lock until stale-recovery | Wrap in `asyncio.wait_for` with per-topic budget = `kb_compile_lock_timeout_minutes * 60 / 3` (min 60s); timeouts raise `RuntimeError` and mark the topic failed | `src/services/knowledge_base.py` |
| 10 | edge-case | medium | `_find_coverage_gaps` only iterated enum, not actual categories | Seeds counts from enum AND buckets any legacy/non-enum category value under its own key | `src/services/kb_health.py` |
| 12 | test-gap | medium | No test for the rollback path, validation errors, or tokenization helpers | Added 7 new tests covering rollback, invalid category/relevance_score/note_type, and the `_jaccard`/`_tokenize` helpers | `tests/services/test_knowledge_base.py`, `tests/api/test_kb_routes.py` |

### Deferred to follow-up

| # | Type | Criticality | Description | Reason |
|---|------|-------------|-------------|--------|
| 3 | security | high | Unbounded LLM cost via `POST /api/v1/kb/compile` — any authenticated user can repeatedly trigger compiles | Advisory lock already prevents concurrent compiles, but doesn't cap sequential cost. Rate limiting requires integration with `src/api/rate_limiter.py` patterns — out of scope for this iteration; tracked in change-context.md "Deferred" section and should become its own issue. |
| 11 | UX | low | `aca kb show` dumps raw markdown to console | Below threshold (low). Rich Markdown rendering would be nice; defer. |
| 13 | workflow | low | `query_kb` and `compile_kb` CLI commands have duplicated asyncio.run + get_db pattern | DRY cost outweighs benefit; only 2 call sites. |
| 14 | observability | low | `_sync_to_graph` is a no-op; returns silently as if it synced | Added debug log in the stub (done as part of #8). |

### Test outcomes

- Before iteration 1: 98 tests passing
- After iteration 1: **105 tests passing** (+7 new tests, all green on first run)
- No regressions in pre-existing tests
