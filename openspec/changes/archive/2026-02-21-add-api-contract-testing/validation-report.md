# Validation Report: add-api-contract-testing

**Date**: 2026-02-21 17:30
**Commits**: ed26428, 83c19a1, 89c2dc0, ea91da0
**Branch**: openspec/add-api-contract-testing
**PR**: #201

## Phase Results

| Phase | Result | Details |
|-------|--------|---------|
| Prerequisites | ✓ Pass | 4 commits on branch, PR #201 open, Docker available |
| Deploy | ○ Skip | Services already running (postgres + neo4j) |
| Smoke: Database | ✓ Pass | PostgreSQL healthy on port 5432 |
| Local: contract tests | ✓ Pass | 7 passed, 13 skipped (209s) |
| Local: unit/CLI tests | ✓ Pass | 365 passed, 3 pre-existing failures (test_models.py) |
| Local: API tests | ⚠ Warn | 487 passed, 6 failed (3 auth-related from branch staleness, 3 pre-existing) |
| CI: lint | ✓ Pass | Ruff + mypy |
| CI: test | ✓ Pass | 365 passed |
| CI: contract-test (run 1) | ✓ Pass | All passed on ed26428 |
| CI: contract-test (run 2) | ✗ Fail | Hypothesis found edge cases on 83c19a1 — **fixed in 89c2dc0 + ea91da0 but CI never re-ran** |
| CI: SonarCloud | ✗ Fail | Quality Gate failed — branch divergence artifact (auth code on main missing from branch) |
| CI: Railway preview | ✗ Fail | Deployment failed — non-blocking (watched paths not modified) |
| Spec Compliance | ⚠ Partial | 2/3 requirements met, 1 deferred |

## CI Gap: Untested Commits

**Critical finding**: The fix commits need CI re-validation.

| Commit | CI Tested? | Content |
|--------|-----------|---------|
| ed26428 | ✓ Passed | Initial implementation |
| 83c19a1 | ✓ Failed | Iteration 1 (Hypothesis found negative limit, missing tables) |
| 89c2dc0 | ✗ **Not tested** | Iteration 2 (fixes: ge=1 bounds, Alembic DB, DataError handlers) |
| ea91da0 | ✗ **Not tested** | Iteration 3 (fixes: mutating fuzz, IntegrityError handler, savepoints) |

The fixes in iterations 2-3 address all CI failures but haven't been validated in CI. Local tests pass.

## Spec Compliance

| Requirement | Status | Notes |
|-------------|--------|-------|
| OpenAPI contract inventory | ✓ | Full endpoint coverage with explicit exclusions for SSE/binary/OTEL |
| Schema-driven fuzz testing | ✓ | GET + POST/PUT/PATCH/DELETE fuzz-tested with seeded DB |
| Contract broker workflow | ○ Deferred | Pact Broker deferred — single-producer system has no external consumers |

## Implementation Quality Assessment

### What's working well
- **Auto-savepoint isolation**: `after_transaction_end` event listener ensures mutating fuzz tests don't break the test transaction
- **Multi-layer get_db patching**: 18 patches across source, routes, and services for complete coverage
- **Alembic-based test DB**: Matches production schema exactly (includes raw SQL columns, triggers, migration-only tables)
- **Excluded endpoint patterns**: Well-documented regex exclusions for SSE, binary, OTEL, and side-effect endpoints
- **3 new exception handlers**: DataError→422, IntegrityError→409, AsyncpgDataError→422

### Branch staleness issues (NOT bugs in implementation)
- Branch forked from `6071e2a` (pre-auth). Main has since merged PR #202 (auth) and PR #203 (search auth fix)
- SonarCloud sees auth code as "deleted" → Quality Gate fails
- 3 API test failures (`test_script_auth`, `test_settings_security`, `test_upload_auth`) are from auth code not present on branch
- **Resolution**: Rebase onto main before merge, or merge main into branch

## Files Changed (implementation scope only)

16 files, 703 insertions across 4 commits:
- `tests/contract/` — 3 new test files (conftest.py, test_schema_conformance.py, test_fuzz.py)
- `src/api/middleware/error_handler.py` — 3 new exception handlers
- `src/api/digest_routes.py`, `podcast_routes.py`, `script_routes.py`, `job_routes.py` — Added ge=1/le bounds on query params
- `.github/workflows/ci.yml` — New `contract-test` job
- `docker-compose.yml` — Switched to pgvector/pgvector:pg17
- `pyproject.toml` — Added schemathesis dependency, contract marker

## Remaining Findings

| # | Type | Criticality | Description | Action |
|---|------|-------------|-------------|--------|
| 1 | CI | **medium** | Iterations 2-3 not CI-validated | Trigger CI re-run (push empty commit or re-push) |
| 2 | staleness | **medium** | Branch behind main (auth PR merged) | Rebase before merge |
| 3 | SonarCloud | low | Quality Gate failed (branch divergence) | Resolves after rebase |
| 4 | hardening | low | asyncpg connection errors return 500 not 503 | Separate PR |
| 5 | hardening | low | Error handler detail includes raw DB strings | Separate PR |

## Result

**CONDITIONAL PASS** — Implementation is solid and local tests pass. Two actions needed before merge:

1. **Rebase onto main** to resolve branch staleness and SonarCloud
2. **Verify CI passes** on latest commits (iterations 2-3 have never run in CI)

After those two items, ready for `/cleanup-feature add-api-contract-testing`.
