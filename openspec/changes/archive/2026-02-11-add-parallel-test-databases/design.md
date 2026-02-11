## Context

The project uses git worktrees for parallel OpenSpec feature development. Each worktree
shares the same Docker Compose services (postgres on 5432, neo4j-test on 7688).
Currently, all test runs target a single hardcoded `newsletters_test` database, which
means:

1. Tests fail if the DB doesn't exist (no auto-provisioning).
2. Two worktrees running `pytest tests/api/` simultaneously corrupt each other's state.
3. Neo4j Community Edition supports only one database per instance, so parallel Neo4j
   integration tests require separate containers.

Three conftest files (`tests/conftest.py`, `tests/api/conftest.py`,
`tests/integration/conftest.py`) each independently define `TEST_DATABASE_URL`,
`test_engine`/`test_db_engine`, and `db_session` with identical logic. This duplication
makes changes error-prone.

## Goals / Non-Goals

**Goals:**
- Zero-setup test execution: `pytest tests/api/` works without prior `make test-setup`
- Parallel-safe: Two worktrees can run full test suites concurrently without collision
- Backwards-compatible: Main repo (no worktree) works identically to today
- Explicit override: `TEST_DATABASE_URL` env var always wins (escape hatch)

**Non-Goals:**
- Parallel test execution *within* a single pytest session (already handled by
  per-test transaction rollback)
- Auto-provisioning Neo4j containers per worktree (too heavy; graceful skip is enough)
- Changes to CI/CD pipeline (already isolated via GitHub Actions service containers)
- Changes to E2E Playwright tests (they use API mocks, not real databases)

## Decisions

### Decision 1: Worktree detection via `.git` file

In a git worktree, `.git` is a text file (not a directory) containing
`gitdir: /path/to/.git/worktrees/<branch-name>`. We parse this to extract the
worktree name and derive a unique DB suffix.

**Detection logic (`tests/helpers/test_db.py`):**
```python
def get_worktree_name() -> str | None:
    """Detect if running from a git worktree, return its name.

    Returns None for main repo or if .git file cannot be parsed.
    """
    git_path = Path.cwd() / ".git"
    if git_path.is_file():
        # .git is a file in worktrees: "gitdir: /path/to/.git/worktrees/<name>"
        try:
            content = git_path.read_text().strip()
        except OSError:
            return None
        if content.startswith("gitdir:"):
            parts = content.split("/worktrees/")
            if len(parts) == 2:
                return parts[1].rstrip("/")
    return None

_MAX_PG_IDENTIFIER = 63
_PREFIX = "newsletters_test_"

def get_test_db_name() -> str:
    """Return worktree-aware test database name.

    PostgreSQL identifiers are limited to 63 characters.
    Long worktree names are truncated to fit within this limit.
    """
    worktree = get_worktree_name()
    if worktree:
        # Sanitize: replace non-alphanumeric with underscore, lowercase
        suffix = re.sub(r"[^a-z0-9]", "_", worktree.lower()).strip("_")
        max_suffix = _MAX_PG_IDENTIFIER - len(_PREFIX)
        suffix = suffix[:max_suffix]
        return f"{_PREFIX}{suffix}"
    return "newsletters_test"
```

**Assumption:** `Path.cwd()` is the repository root. This holds for all standard
invocations (`pytest`, `make test`, IDE test runners) because they use the project
root as working directory. If tests are run from a subdirectory (e.g., `cd tests &&
python -m pytest`), worktree detection silently falls back to the default
`newsletters_test` name — which is safe but loses parallel isolation.

**Alternatives considered:**
- Branch name from `git rev-parse --abbrev-ref HEAD`: Requires subprocess call, slower,
  and branch names can collide across repos. Worktree directory name is already unique.
- UUID per test run: Would create unbounded databases requiring cleanup.
- CWD hash: Not human-readable, harder to debug.
- Walk up directories to find `.git`: Would fix the subdirectory case but adds complexity
  for a scenario that doesn't occur in practice.

### Decision 2: Auto-create via admin DB connection

PostgreSQL requires connecting to an existing database to issue `CREATE DATABASE`.
We connect to the default `postgres` database, set `AUTOCOMMIT` isolation (DDL can't
run inside a transaction), and create the test DB if it doesn't exist.

```python
def ensure_test_db_exists(db_name: str, base_url: str) -> None:
    """Create the test database if it doesn't exist."""
    admin_url = base_url.rsplit("/", 1)[0] + "/postgres"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": db_name},
        ).scalar()
        if not exists:
            # Use text() with no parameters — DB names can't be parameterized
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin_engine.dispose()
```

**Safety:** The `"test" in db_name` check remains as a guard against accidental
production DB creation.

### Decision 3: Docker init script for base `newsletters_test`

Add `docker/init/01-create-test-db.sh` mounted into postgres via
`/docker-entrypoint-initdb.d/`. This creates the default `newsletters_test` database
on first container start. Worktree-specific databases are still created dynamically
by conftest auto-provisioning.

```bash
#!/bin/bash
# docker/init/01-create-test-db.sh
# Create the default test database.
# Worktree-specific databases are created dynamically by pytest fixtures.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE newsletters_test OWNER newsletter_user'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'newsletters_test')
\gexec
EOSQL
```

**Note:** Using a `.sh` wrapper instead of raw `.sql` because the `\gexec`
metacommand is a psql feature, not standard SQL. Docker entrypoint runs `.sh`
files via `bash` and `.sql` files via `psql -f`, but `\gexec` only works in
interactive psql mode. The shell script invokes psql directly with the
metacommand intact.

**Why both Docker init AND conftest auto-create?**
- Docker init handles the common case (main repo) without any Python dependency.
- Conftest auto-create handles worktree-specific databases and environments where
  Docker init didn't run (e.g., pre-existing container, CI).

### Decision 4: Neo4j — graceful skip, not parallel containers

Neo4j Community Edition supports only one database per instance. Spinning up additional
containers per worktree is resource-heavy and most worktrees don't test knowledge graph
features.

**Approach:**
- Keep the existing `neo4j_driver` fixture that yields `None` when connection fails.
- Support `TEST_NEO4J_URI` env var for override (already exists).
- Document that parallel Neo4j integration tests require manually starting additional
  containers on different ports.
- Add a `conftest.py` warning when two worktrees share the same Neo4j test port.

### Decision 5: Consolidate conftest duplication

Extract shared logic into `tests/helpers/test_db.py`:
- `get_test_database_url()` — resolves URL with worktree awareness
- `ensure_test_db_exists()` — auto-creates if missing
- `create_test_engine()` — creates engine with safety checks + table setup
- `create_test_session()` — wraps transaction-rollback session pattern

All three conftest files import from this helper instead of duplicating logic.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Orphaned worktree databases accumulate | `make test-clean` drops all `newsletters_test*` databases; document periodic cleanup |
| Admin DB connection fails (permissions) | Raise clear error message suggesting `make test-setup` as manual fallback |
| Worktree name collision (very unlikely) | Names are directory-based, already unique within a repo |
| Long worktree names exceed PG 63-char limit | `get_test_db_name()` truncates suffix; prefix `newsletters_test_` is 17 chars, leaving 46 chars for suffix |
| Docker init script only runs on first start | Existing containers won't get the script; `make test-setup` or conftest auto-create covers this |
| `.git` file corrupted or unreadable | `get_worktree_name()` catches `OSError` and falls back to default name |

## Migration Plan

1. **Non-breaking**: All changes are additive. Existing `make test-setup` workflow continues to work.
2. **Gradual adoption**: Worktree users get parallel safety automatically. Main repo users see no change.
3. **Existing containers**: Won't get Docker init script until `docker compose down -v && docker compose up -d`. Conftest auto-create covers the gap.

## Open Questions

- None — the design is straightforward and backwards-compatible.
