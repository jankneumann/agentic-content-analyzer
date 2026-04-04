# Proposal: Local Test Profile with Isolated Full-Stack Server

## Problem

E2E tests currently depend on the user's development server (`make dev-bg` on port 8000). This creates several issues:

1. **Auth conflicts**: If the dev server runs with a profile that enables auth (e.g., `local-opik` with `APP_SECRET_KEY` from `.secrets.yaml`), E2E tests fail with 401 because they don't know the configured key.
2. **Port conflicts**: Tests can't run while the user is actively developing — they share the same port 8000.
3. **Database contamination**: E2E tests write test data (ingested content, summaries, digests) to the same database the user is browsing in the frontend.
4. **Worktree isolation gap**: While `tests/helpers/test_db.py` provides worktree-aware DB naming for unit tests, E2E/live tests hit whatever database the dev server is connected to.
5. **No CI parity**: The `ci-neon` profile handles CI, but there's no equivalent for local E2E runs.
6. **Frontend isolation**: Playwright E2E tests reuse a running vite dev server if one exists (per `reuseExistingServer`), which may serve code from a different branch.

## Why Now

During the PR #362 validation session, E2E tests failed with 401 because a stale server process was running with `PROFILE=local-opik` (which activates `APP_SECRET_KEY`). Debugging took significant time. This is a recurring friction point that wastes developer time and produces false negatives in validation.

## What Changes

### 1. Test Profile (`profiles/test.yaml`)
- Extends `local`, disables auth, uses dedicated test DB, noop observability
- Explicitly empties `app_secret_key` and `admin_api_key` (overrides `.secrets.yaml` interpolation)
- Disables embedded worker to avoid background job interference

### 2. E2E Server Fixture (`tests/e2e/server_fixture.py`)
- Session-scoped pytest fixture that manages a full-stack test server lifecycle
- **Backend**: uvicorn subprocess with `PROFILE=test` on dynamically allocated port
- **Frontend**: vite subprocess on a separate dynamic port
- **Database**: Alembic migrations against a dedicated test DB (production-faithful schema)
- **Data seeding**: Uses existing DB export/import facilities to seed test data
- **Port allocation**: Coordinator `allocate_ports` when available, hash-based fallback from worktree name

### 3. Port Allocation Strategy
- **Coordinator available**: `mcp__coordination__allocate_ports(session_id)` returns conflict-free port block
- **Fallback**: `hash(worktree_name) % 1000 + 9000` for deterministic, parallel-safe ports per worktree
- Main repo (no worktree) uses base offset `9100`

### 4. E2E Conftest Updates
- `http_client` and `api_client` fixtures receive URL from server fixture instead of hardcoded `localhost:8000`
- `E2E_BASE_URL` env var still overrides for manual testing against a specific server

## Approaches Considered

### Approach A: Pytest-Managed Subprocess Server (Recommended)

A session-scoped pytest fixture spawns uvicorn and vite as subprocesses, manages their lifecycle, and passes connection info to test fixtures.

**Flow:**
```
pytest session start
  -> hash-based port allocation (or coordinator)
  -> ensure_test_db_exists(worktree-aware name)
  -> alembic upgrade head (subprocess, against test DB)
  -> seed test data via DB import
  -> start uvicorn subprocess (PROFILE=test, PORT=<api_port>)
  -> start vite subprocess (port=<frontend_port>)
  -> poll /health until 200
  -> yield TestServerInfo(api_url, frontend_url, db_name)
  -> on teardown: kill processes, release_ports()
```

**Pros:**
- Zero manual setup — `pytest tests/e2e/` just works
- Fully isolated from dev server (different port, DB, profile)
- Reuses existing `tests/helpers/test_db.py` for DB creation
- Contract tests already prove the Alembic-subprocess pattern works
- Coordinator integration gives enterprise-grade port management

**Cons:**
- ~5s startup overhead per session (DB migration + server boot)
- Two subprocesses to manage (uvicorn + vite)
- Need to handle startup failures gracefully (port in use, migration error)

**Effort:** M

### Approach B: Docker Compose Test Stack

Define a `docker-compose.test.yml` that starts a complete test stack (PostgreSQL, API, frontend) with the test profile baked in.

**Pros:**
- True environment isolation (containerized)
- Matches production topology more closely
- Can run in CI without any host-level dependencies

**Cons:**
- Much slower startup (~30s for container pull + boot)
- Requires Docker running (not always the case in lightweight dev setups)
- Harder to debug — logs are inside containers
- Duplicates the existing docker-compose.yml with minor changes
- Can't easily attach a debugger to the API server

**Effort:** L

### Approach C: In-Process ASGI TestClient (No Subprocess)

Use FastAPI's `TestClient` (like the API unit tests) but with a real DB and the test profile loaded in-process.

**Pros:**
- Fastest — no subprocess overhead
- Already used by API tests and contract tests
- Easy to debug (same process)

**Cons:**
- Not a true E2E test — skips HTTP layer, CORS, middleware ordering
- Can't test frontend against it (TestClient has no real HTTP port)
- Doesn't validate deployment configuration (profile loading, uvicorn config)
- API tests already do this — E2E should test a different layer

**Effort:** S

## Selected Approach

**Hybrid: A (default) + B (validation)** — Subprocess server for daily development (`pytest tests/e2e/`), Docker Compose stack for validation (`make test-e2e-docker` / `/validate-feature`). The test profile, port allocation, and data seeding logic are shared between both modes. This gives fast feedback for daily work and true container isolation for release validation.

## Scope

### In Scope
- `profiles/test.yaml` with auth disabled, dedicated DB, noop observability
- E2E server fixture: uvicorn + vite subprocess management
- Hash-based port allocation with coordinator fallback
- Test DB creation and Alembic migration
- Test data seeding via DB export/import
- Update existing E2E conftest to use managed server
- Makefile target: `make test-e2e` (convenience wrapper)

### Out of Scope
- CI integration changes (CI already has `ci-neon` profile)
- Parallel test execution within a single session (future)
- Custom test data factories for E2E (existing import facilities suffice)

## Risks

| Risk | Mitigation |
|------|-----------|
| Subprocess startup is slow (~5s) | Session scope — only once per test run. Alembic skips if schema exists. |
| Port collision without coordinator | Hash-based allocation is deterministic per worktree — only collides if same worktree runs tests twice simultaneously. |
| Vite startup adds complexity | Optional: if `--skip-frontend` flag or `web/` dir missing, skip vite. |
| `.secrets.yaml` leaks auth | Profile explicitly sets empty strings — overrides interpolation (verified: empty env vars win over defaults). |
| Test DB accumulates stale data | Session fixture can truncate tables before seeding, or use per-session DB names. |

## Success Criteria

1. `pytest tests/e2e/ -v --no-cov` works without a pre-running dev server
2. Tests pass regardless of whether the dev server is running on port 8000
3. No test data appears in the user's development database
4. Works in worktrees (parallel-safe DB naming and port allocation)
5. Frontend Playwright tests can target the test server's vite instance
