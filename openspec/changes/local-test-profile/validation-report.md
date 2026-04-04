# Validation Report: local-test-profile

**Date**: 2026-04-03
**Commit**: 82386b3
**Branch**: openspec/local-test-profile

## Phase Results

### ✓ Smoke: Profile Loading
- Profile `test` loads with auth disabled (admin_api_key="", app_secret_key="")
- Database URL points to `newsletters_e2e` (worktree-aware: `newsletters_e2e_<name>`)
- Observability provider: noop
- Log level: WARNING

### ✓ Smoke: Server Lifecycle
- Server starts automatically on port 9100 (or ephemeral fallback)
- Health check returns 200
- `/api/v1/contents` accessible without credentials (auth disabled)
- Readiness endpoint responds
- Port isolated from dev server (9100 != 8000)
- DB isolated from dev DB (`newsletters_e2e_*` vs `newsletters`)
- Clean shutdown on context exit

### ✓ Smoke: Crash Detection
- Process exit detected in <1s (not 30s timeout)
- stderr included in error message

### ✓ Smoke: Port Fallback
- Falls back to ephemeral port when 9100 is occupied

### ✓ Smoke: E2E_BASE_URL Override
- Setting `E2E_BASE_URL` skips managed server (backward compatible)

### ✓ Security: Credential Check
- No hardcoded secrets in `profiles/test.yaml`
- Auth keys are falsy empty strings — middleware bypassed correctly
- `newsletter_password` is the default Docker Compose password (not a secret)

### ✓ Spec Compliance: 8/8 in-scope requirements verified

| Req | Status | Evidence |
|-----|--------|----------|
| R1.1 Auth disabled | pass 82386b3 | GET /api/v1/contents -> 200 without credentials |
| R1.2 Dedicated test DB | pass 82386b3 | DB name: newsletters_e2e_local_test_profile |
| R1.3 Worker disabled | pass 82386b3 | WORKER_ENABLED=false in subprocess env |
| R1.4 Noop observability | pass 82386b3 | Profile flattens to observability_provider=noop |
| R2.1 Auto server start | pass 82386b3 | Server started on port 9100, health 200 |
| R2.2 E2E_BASE_URL skip | pass 82386b3 | managed_server yields None when env set |
| R2.3 Server teardown | pass 82386b3 | Process terminated on context exit |
| R3.3 Default port 9100 | pass 82386b3 | Port allocation prefers 9100 with fallback |

### Deferred (out of proposal scope)
- Vite subprocess (frontend E2E)
- Coordinator port allocation
- Hash-based worktree port offsets
- Test data seeding (seed_data.sql)
- Lazy Neo4j test instance
- Docker Compose test stack
- `test-e2e-docker` Makefile target

### ○ E2E: Skipped
- No ANTHROPIC_API_KEY configured — LLM evaluation tests would skip
- Test collection verified: 17 tests resolve correctly

### ○ CI/CD: Skipped
- No PR created yet for this branch

## Result

**PASS** — All in-scope requirements verified against live server. Ready for `/cleanup-feature local-test-profile`.

## Alembic Fix Note

Migration `b159ceaf9494` (create theme_analyses) was made idempotent — pre-existing bug on main where two migrations create the same table. This fix is included in the feature branch but should also be applied to main.
