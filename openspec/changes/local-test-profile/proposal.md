# Proposal: Local Test Profile with Isolated Server and Database

## Problem

E2E tests currently depend on the user's development server (`make dev-bg` on port 8000). This creates several issues:

1. **Auth conflicts**: If the dev server runs with a profile that enables auth (e.g., `local-opik` with `APP_SECRET_KEY`), E2E tests fail with 401 because they don't know the configured key.
2. **Port conflicts**: Tests can't run while the user is actively developing — they share the same port 8000.
3. **Database contamination**: E2E tests write test data (ingested content, summaries, digests) to the same database the user is browsing in the frontend.
4. **Worktree isolation gap**: While `tests/helpers/test_db.py` provides worktree-aware DB naming for unit tests, E2E/live tests hit whatever database the dev server is connected to.
5. **No CI parity**: The `ci-neon` profile handles CI, but there's no equivalent for local E2E runs.

## Solution

Create a `test` profile and E2E infrastructure that spins up an isolated backend on dynamically allocated ports with a dedicated test database.

### Components

1. **`profiles/test.yaml`** — Test profile that:
   - Extends `local`
   - Sets `environment: development` (no auth enforcement)
   - Explicitly nulls `app_secret_key` and `admin_api_key` (no auth even if `.secrets.yaml` has them)
   - Uses a dedicated test database (`newsletters_e2e` or worktree-aware variant)
   - Disables the embedded worker (`worker_enabled: false`)
   - Uses noop observability

2. **Coordinator port allocation** — E2E conftest uses `mcp__coordination__allocate_ports` (when available) to get a conflict-free port block, falling back to a deterministic offset (e.g., base port 9000) when the coordinator is unavailable.

3. **E2E server lifecycle** — A session-scoped pytest fixture that:
   - Allocates ports (coordinator or fallback)
   - Creates the test database if needed (reusing `tests/helpers/test_db.py` logic)
   - Runs `alembic upgrade head` against the test database
   - Starts a uvicorn subprocess with `PROFILE=test` and the allocated API port
   - Waits for health check
   - Yields the base URL and admin key to tests
   - Tears down the server and releases ports on session end

4. **E2E conftest updates** — The existing `http_client` and `api_client` fixtures use the dynamically allocated URL instead of hardcoded `localhost:8000`.

### Profile Design

```yaml
# profiles/test.yaml
name: test
extends: local
description: Isolated E2E test server — no auth, dedicated DB, dynamic ports

settings:
  environment: development
  log_level: WARNING
  worker_enabled: false

  api_keys:
    admin_api_key: ""      # Explicitly empty — no auth enforcement
    app_secret_key: ""     # Explicitly empty — no session cookies

  database:
    database_url: "${TEST_DATABASE_URL:-postgresql://newsletter_user:newsletter_password@localhost/newsletters_e2e}"

providers:
  observability: noop
```

### E2E Fixture Flow

```
pytest session start
  -> allocate_ports(session_id) or fallback to port 9100
  -> ensure_test_db_exists("newsletters_e2e")
  -> alembic upgrade head (against test DB)
  -> start uvicorn subprocess (PROFILE=test, PORT=<allocated>)
  -> wait for /health 200
  -> yield TestServerInfo(base_url, port, db_name)
  -> on teardown: kill uvicorn, release_ports()
```

## Scope

### In Scope
- `profiles/test.yaml` with auth disabled and dedicated DB
- E2E conftest fixture for server lifecycle (start/stop uvicorn subprocess)
- Port allocation via coordinator with deterministic fallback
- Test database creation and migration
- Update existing E2E tests to use the managed server

### Out of Scope
- Frontend E2E (Playwright) — remains against the dev server for now
- Test data seeding (existing URL ingestion pattern works)
- CI integration (CI already has `ci-neon` profile)
- Parallel test execution across multiple worktrees (future enhancement)

## Risks

| Risk | Mitigation |
|------|-----------|
| Subprocess uvicorn startup is slow | Health check polling with 15s timeout; cached DB (skip migration if tables exist) |
| Port conflict with user's dev server | Coordinator allocation or deterministic offset (9100+) |
| Test DB accumulates stale data | Session fixture can truncate tables on setup, or use per-session DB names |
| `.secrets.yaml` leaks auth into test profile | Profile explicitly sets empty strings for auth keys (overrides interpolation) |

## Success Criteria

1. `pytest tests/e2e/ -v --no-cov` works without a pre-running dev server
2. Tests pass regardless of whether the dev server is running on port 8000
3. No test data appears in the user's development database
4. Works in worktrees (parallel-safe DB naming)
