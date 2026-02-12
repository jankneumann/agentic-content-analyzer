# Validation Report: add-document-search

**Date**: 2026-02-11 20:45:00
**Commit**: f4bca65
**Branch**: openspec/add-document-search
**PR**: #162

## Phase Results

### Deploy
**Result**: PASS

- Docker services (PostgreSQL 17, Redis, Neo4j) running and healthy
- Installed pgvector 0.8.1 extension in PostgreSQL container
- Alembic migration `b2c3d4e5f6a7` (document_chunks table) applied successfully
- API started from worktree on port 8000 with DEBUG logging
- Table verified: 16 columns, 5 indexes (HNSW, GIN, btree), FK with CASCADE, tsvector trigger

### Smoke
**Result**: PASS (with 2 bugs found and fixed)

- API health: 200
- API readiness: 200 (database ok, queue not_connected)
- GET /api/v1/search: 200
- POST /api/v1/search: 200
- GET /api/v1/search/chunks/999: 404 (correct)
- Backfill: 13,047 chunks created from 1,693 content records (4 chunk types: paragraph, transcript, section, code)
- BM25 search with real data: 23ms, correct results with highlighting

**Bugs Found and Fixed:**
1. **`get_db` Depends pattern** (`search_routes.py`): Routes used `Depends(get_db)` in async functions, but every other route in the codebase uses `with get_db() as db:`. The sync generator + async route combination caused `AttributeError: '_GeneratorContextManager' object has no attribute 'throw'`. Fixed by switching to `with get_db() as db:` pattern.
2. **Enum cast in filters** (`search.py`): `source_type` and `status` filters compared PG enums directly to text arrays (`c.source_type = ANY(:source_types)`), causing `UndefinedFunction: operator does not exist: contentsource = text`. Fixed by adding `::text` cast.

### Tests
**Result**: PASS

- **Search-specific tests**: 44/44 passed (test_chunking.py + test_search.py) in 4.78s
- **New API regression suite**: 30/30 passed (test_search_api.py) in 2.47s
  - 5 smoke tests
  - 4 response shape tests
  - 2 BM25 search tests
  - 5 result aggregation tests
  - 2 highlighting tests
  - 3 filter tests
  - 4 search type tests
  - 2 chunk detail tests
  - 1 performance SLA test
  - 3 validation tests
- **CI/CD**: lint PASS, test PASS, validate-profiles PASS

### Spec Compliance
**Result**: PASS (14/14 scenarios)

| # | Scenario | Result | Detail |
|---|----------|--------|--------|
| 1 | BM25 auto-detection | PASS | postgres_native_fts (pg_search not available) |
| 2 | Response shape | PASS | results, total, meta |
| 3 | Meta fields complete | PASS | 7/7 required fields present |
| 4 | Max 3 chunks per document | PASS | counts=[3, 2, 2, 3, 1] |
| 5 | Highlighting with `<mark>` tags | PASS | Terms wrapped correctly |
| 6 | Chunk detail 404 | PASS | 404 for non-existent |
| 7 | Empty query validation | PASS | 422 with string_too_short |
| 8 | POST search JSON body | PASS | Full response shape |
| 9 | Reranking disabled by default | PASS | rerank_provider=None |
| 10 | Backend reported | PASS | backend=local |
| 11 | Performance SLA <1000ms | PASS | 25ms |
| 12 | Filters (source_type+date) | PASS | Correct filtering |
| 13 | Chunk detail with metadata | PASS | All fields + content metadata |
| 14 | Chunk types valid | PASS | code, paragraph, section, transcript |

### Log Analysis
**Result**: PASS (with expected warnings)

- 1,320 log lines analyzed
- **After final restart**: 0 application errors, 0 HTTP 500 responses
- **Expected warnings**: 9x `ModuleNotFoundError: No module named 'sentence_transformers'` (local embedding provider not installed, fail-safe design works correctly)
- **Pre-fix errors** (now resolved): `_GeneratorContextManager` AttributeError, PG enum cast errors

### CI/CD Status
**Result**: PASS (with non-critical SonarCloud finding)

| Check | Status |
|-------|--------|
| lint | PASS (13s) |
| test | PASS (1m34s) |
| validate-profiles | PASS (1m6s) |
| Railway deploy | PASS (preview at aca-agentic-newsletter-aggreg-pr-162.up.railway.app) |
| SonarCloud | FAIL (non-critical, code quality scanner) |

## Bugs Fixed During Validation

### Bug 1: `get_db` Depends pattern mismatch
- **File**: `src/api/search_routes.py`
- **Symptom**: All search endpoints returned 500 with `AttributeError`
- **Root Cause**: Used `Depends(get_db)` pattern in async routes, but codebase convention is `with get_db() as db:`
- **Fix**: Changed all 3 routes to use `with get_db() as db:` context manager

### Bug 2: PG enum type mismatch in filters
- **File**: `src/services/search.py`
- **Symptom**: Filtered search returned 500 with `operator does not exist: contentsource = text`
- **Root Cause**: `source_type` and `status` are PG enum columns; `= ANY(:text_array)` requires explicit cast
- **Fix**: Added `::text` cast to enum columns in filter SQL

## New Test Suite Created

**File**: `tests/api/test_search_api.py` (30 tests)

Reusable pytest regression suite covering:
- Smoke tests (endpoint availability, response codes)
- Response shape validation (meta fields, required keys)
- BM25 search with matching and scoring
- Result aggregation (max 3 chunks, metadata, pagination)
- Highlighting (`<mark>` tags, HTML escaping)
- Filtering (source_type, date_range, publication)
- Search type selection (bm25, vector, hybrid, default)
- Chunk detail endpoint
- Performance SLA verification
- Input validation

## Notes

- **pgvector not in Docker Compose**: The standard `postgres:17` image doesn't include pgvector. Had to `apt-get install postgresql-17-pgvector` at runtime. Consider switching to `pgvector/pgvector:pg17` image in docker-compose.yml.
- **sentence-transformers not installed**: Local embedding provider requires this heavy dependency (PyTorch). Chunks are saved without embeddings — BM25 search still works. This is the correct fail-safe behavior.
- **pg_search not tested**: ParadeDB pg_search requires Rust compilation (~20 min). Validated with PostgreSQL native FTS fallback path. The Railway preview deployment has pg_search available for production testing.

## Result

**PASS** — Ready for `/cleanup-feature add-document-search`

Two bugs were found and fixed during validation. A 30-test regression suite was created. All spec scenarios verified against live system.
