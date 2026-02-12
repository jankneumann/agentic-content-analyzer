# Change: Add parallel-safe test database infrastructure

## Why
Running `pytest tests/api/` or `pytest tests/integration/` currently fails unless
`newsletters_test` has been manually created via `make test-setup` or
`scripts/setup_test_db.py`. Worse, all worktrees share the same test database and
Neo4j test instance, so two concurrent test runs (e.g., from different OpenSpec
feature branches) stomp each other's schema via session-scoped `drop_all`/`create_all`.

## What Changes
- **Docker init script**: Auto-create `newsletters_test` when the postgres container
  first starts, eliminating the need for a manual `make test-setup` step for PG.
- **Shared test DB helper** (`tests/helpers/test_db.py`): Centralize `TEST_DATABASE_URL`
  resolution, worktree detection, and auto-creation logic in one place.
- **Worktree-aware DB naming**: Derive unique database names per worktree
  (e.g., `newsletters_test_add_document_search`) so parallel runs don't collide.
- **Auto-create in conftest**: Session-scoped fixtures auto-create the test database
  if it doesn't exist, removing the hard dependency on external setup scripts.
- **Consolidate conftest duplication**: Three conftest files independently define
  `TEST_DATABASE_URL` and engine fixtures — extract into shared helper.
- **Neo4j port allocation**: Support per-worktree Neo4j test ports via environment
  variables with graceful fallback when no test Neo4j is available.
- **Makefile updates**: Make `test-setup`/`test-clean` worktree-aware.

## Impact
- Affected specs: `test-infrastructure`
- Affected code:
  - `docker-compose.yml` (postgres init script mount)
  - `docker/init/01-create-test-db.sh` (new)
  - `tests/helpers/test_db.py` (new)
  - `tests/conftest.py`
  - `tests/api/conftest.py`
  - `tests/integration/conftest.py`
  - `scripts/setup_test_db.py`
  - `Makefile`
