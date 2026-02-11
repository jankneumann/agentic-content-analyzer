## 1. Docker Init Script
- [x]1.1 Create `docker/init/01-create-test-db.sh` that creates `newsletters_test` database owned by `newsletter_user` (shell wrapper for `\gexec`)
- [x]1.2 Update `docker-compose.yml` postgres service to mount `./docker/init/` into `/docker-entrypoint-initdb.d/`

## 2. Shared Test DB Helper (with unit tests)
> All functions live in `tests/helpers/test_db.py`; unit tests in `tests/test_helpers/test_test_db.py`.

- [x]2.1 Create `tests/helpers/test_db.py` with all helper functions:
  - `get_worktree_name()` — detect git worktree from `.git` file (returns `None` on parse failure)
  - `get_test_db_name()` — worktree-aware DB name with sanitization and 63-char PG identifier truncation
  - `get_test_database_url()` — resolve full URL; `TEST_DATABASE_URL` env var overrides worktree detection
  - `ensure_test_db_exists()` — auto-create via admin connection to `postgres` DB with `AUTOCOMMIT`; clear error message on failure
  - `create_test_engine()` — safety check (`"test" in db_name`), auto-create, engine creation, `drop_all`/`create_all`
- [x]2.2 Write unit tests covering: worktree detection (main repo, worktree, corrupted `.git`), DB name sanitization, 63-char truncation, `TEST_DATABASE_URL` override, safety check rejection, admin connection failure error message

> **Dependency:** Tasks 3.x and 5.x depend on 2.1 being complete.

## 3. Consolidate Conftest Files
- [x]3.1 Refactor `tests/conftest.py` to import `get_test_database_url` and `create_test_engine` from `tests.helpers.test_db`
- [x]3.2 Refactor `tests/api/conftest.py` to import `create_test_engine` and reuse shared `db_session` pattern
- [x]3.3 Refactor `tests/integration/conftest.py` to import shared PG helpers AND add Neo4j worktree warning (log warning when worktree detected and `TEST_NEO4J_URI` is not set, indicating shared port)
- [x]3.4 Verify all existing tests still pass after refactor (`pytest tests/test_config/ tests/test_cli/ tests/api/ -v`)

> **Note:** Task 3.3 also covers Neo4j parallel safety (warning log). Task 4.x verifies existing behavior only.

## 4. Neo4j Parallel Safety (verification only)
- [x]4.1 Verify `tests/integration/conftest.py` reads `TEST_NEO4J_URI` with env var override (already exists)
- [x]4.2 Verify `neo4j_driver` fixture gracefully yields `None` when connection fails (already exists)

> **Dependency:** Task 4.x can run in parallel with tasks 1.x and 2.x (verification only, no code changes).

## 5. Makefile & Script Updates
- [x]5.1 Update `make test-setup` to use worktree-aware database name (invoke shared helper or pass name from shell)
- [x]5.2 Update `make test-clean` to drop all `newsletters_test*` databases via pattern-based `SELECT datname FROM pg_database WHERE datname LIKE 'newsletters_test%'` query
- [x]5.3 Update `scripts/setup_test_db.py` to import and use `get_test_db_name()` from shared helper

> **Note:** `test-clean` is now the single cleanup target for all worktree DBs (no separate `test-clean-all` needed since the pattern already covers all variants).

## 6. Documentation & Validation
- [x]6.1 Update CLAUDE.md gotchas table with worktree test DB naming convention and 63-char limit
- [x]6.2 Run full test suite to verify no regressions
- [x]6.3 Test from a worktree to verify parallel DB creation works

> **Note:** Parallel execution safety (#9) is verified by architectural design (unique DB names per worktree), not a runtime integration test. Task 6.3 serves as a manual smoke test.
