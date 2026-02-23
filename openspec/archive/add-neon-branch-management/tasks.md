# Implementation Tasks

## File Overlap Notes (Critical for Parallel Execution)

**MUST sequence these sections to avoid conflicts:**

| File | Sections Modifying | Resolution |
|------|-------------------|------------|
| `agentic-coding-tools` skills (separate repo) | 1 only | No conflict |
| `tests/integration/conftest.py` | 2 only | No conflict |
| `.github/workflows/neon-pr.yml` (NEW) | 3 only | No conflict |
| `.github/workflows/ci.yml` | 3 only (comment) | No conflict |
| `profiles/ci-neon.yaml` (NEW) | 3 only | No conflict |

**Independent streams (can run in parallel):**
- Stream A: Section 1 (skill integration) — independent of all others
- Stream B: Section 2 (test infrastructure) — independent of Section 1
- Stream C: Section 3 (CI/CD + Neon GitHub Actions) — depends on Section 2 (needs fixtures to exist)
- Stream D: Section 4 (CLI verification) — depends on existing CLI code
- Stream E: Section 5 (documentation) — after all implementation

---

## 1. Neon Branch Skill (in agentic-coding-tools repo)

**Depends on:** Nothing (CLI commands in this repo already exist)
**Repo:** `agentic-coding-tools` (NOT this repo — skills are managed there)
**Note:** The skill definitions below should be created as a `neon-branch` skill in the
agentic-coding-tools repo alongside the existing OpenSpec skills.
**Status:** OUT OF SCOPE for this PR — tracked separately for the external repo.

- [ ] 1.1 Create `neon-branch` skill in `agentic-coding-tools` with create/verify/cleanup actions
  - create: `aca neon create claude/<change-name>` + `alembic upgrade head`
  - verify: `aca neon connection <name>` + run pytest against branch
  - cleanup: `aca neon delete <name> --force`
  - Prerequisite check: `aca neon list --json` to verify credentials
  - Graceful fallback: if Neon unavailable, skip silently

- [ ] 1.2 Update `openspec-apply-change` skill to invoke `neon-branch create` before implementation
  - Add optional step between "Select the change" and "Read context files":
    "If Neon credentials are available, create branch `claude/<change-name>`"
  - Include fallback: "If Neon is unavailable, skip silently and use local database"

- [ ] 1.3 Update `openspec-verify-change` skill to invoke `neon-branch verify` during validation
  - Add step after "Verify Completeness" and before "Generate Report":
    "If a Neon branch `claude/<change-name>` exists, run tests against it"
  - Add branch test results to the verification report under a new "Branch Testing" section

- [ ] 1.4 Update `openspec-archive-change` skill to invoke `neon-branch cleanup` after archiving
  - Add step after "Perform the archive":
    "If a Neon branch `claude/<change-name>` exists, delete it"
  - Cleanup failure should not block archive

## 2. Test Infrastructure

**Depends on:** Nothing (builds on existing `tests/integration/fixtures/neon.py`)
**Files:** `tests/integration/conftest.py`, `pyproject.toml`

- [x] 2.1 Register `neon` pytest marker in `pyproject.toml`
  - Added to `[tool.pytest.ini_options]` markers list

- [x] 2.2 Add `neon_available` session fixture to `tests/integration/conftest.py`
  - Already existed in `tests/integration/fixtures/neon.py` and imported in conftest

- [x] 2.3 Add `neon_session_branch` session-scoped fixture to `tests/integration/conftest.py`
  - Already existed in `tests/integration/fixtures/neon.py` and imported in conftest

- [x] 2.4 Add `neon_engine` session-scoped fixture
  - Already existed as part of the Neon fixture module

- [x] 2.5 Verify existing Neon fixtures in `tests/integration/fixtures/neon.py` are importable from conftest
  - All 6 fixtures confirmed importable: `neon_manager`, `neon_test_branch`,
    `neon_isolated_branch`, `neon_session_branch`, `neon_default_branch`, `neon_available`

## 3. CI/CD Integration — Neon GitHub Actions

**Depends on:** Section 2 (fixtures must exist for tests to run)
**Files:** `.github/workflows/neon-pr.yml` (new), `.github/workflows/ci.yml`, `profiles/ci-neon.yaml` (new)

**Uses:** Neon's official GitHub Actions for branch lifecycle management:
- [`neondatabase/create-branch-action@v6`](https://github.com/neondatabase/create-branch-action)
- [`neondatabase/delete-branch-action@v3`](https://github.com/neondatabase/delete-branch-action)
- [`neondatabase/schema-diff-action@v1`](https://github.com/neondatabase/schema-diff-action)

### 3a. CI Profile

- [x] 3.1 Create `profiles/ci-neon.yaml` profile for CI Neon integration tests
  - Already exists with `extends: base`, `database: neon`, and proper env var interpolation

### 3b. PR Branch Lifecycle Workflow

- [x] 3.2 Create `.github/workflows/neon-pr.yml` — full PR-based Neon branch lifecycle
  - Already exists with all 4 jobs: create-branch, test-neon, schema-diff, delete-branch

### 3c. Existing CI Updates

- [x] 3.3 Update `.github/workflows/ci.yml` with profile-aware test job (optional)
  - ci-neon.yaml is validated automatically by existing `validate-profiles` job

### 3d. Repository Setup Documentation

- [x] 3.4 Document required GitHub repository configuration
  - Already documented in docs/SETUP.md Neon section

## 4. CLI Verification and Hardening

**Depends on:** Existing `src/cli/neon_commands.py` (already created)
**Files:** `tests/cli/test_neon_commands.py` (new), `src/cli/neon_commands.py`

- [x] 4.1 Add unit tests for `aca neon` CLI commands
  - Created `tests/cli/test_neon_commands.py` with 30 tests covering all 5 commands
  - Tests mock `NeonBranchManager` via `_get_manager` (async context manager pattern)
  - Covers: list, create, delete, connection, clean + missing credentials

- [x] 4.2 Add `--json` output validation to CLI tests
  - JSON output validated for all commands: list, create, delete, connection, clean
  - Verified JSON schema structure matches expected shapes

- [x] 4.3 Handle edge case: `aca neon create` when branch already exists
  - Added `--force/-f` flag to `create` command: delete existing + recreate
  - Gracefully ignores 404 (branch doesn't exist yet)
  - Re-raises non-404 errors (e.g., server errors)
  - 4 tests cover force scenarios (delete+create, 404 ignore, error propagation, success)

## 5. Documentation

**Depends on:** Sections 1-4 (document after implementation)

- [x] 5.1 Update `CLAUDE.md` "Critical Gotchas" table with Neon branching gotchas
  - Already documented: slow first connection, DATABASE_PROVIDER requirement, empty cloud DBs

- [x] 5.2 Update `docs/SETUP.md` Neon section with agent workflow instructions
  - Already has "Neon Serverless PostgreSQL" section with setup, branching, and testing

- [x] 5.3 Add Neon branch management to `docs/DEVELOPMENT.md` development workflow section
  - Already has integration test examples and fixture documentation
