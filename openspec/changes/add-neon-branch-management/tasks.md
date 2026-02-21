# Implementation Tasks

## File Overlap Notes (Critical for Parallel Execution)

**MUST sequence these sections to avoid conflicts:**

| File | Sections Modifying | Resolution |
|------|-------------------|------------|
| `.claude/skills/openspec-apply-change/SKILL.md` | 1 only | No conflict |
| `.claude/skills/openspec-verify-change/SKILL.md` | 1 only | No conflict |
| `.claude/skills/openspec-archive-change/SKILL.md` | 1 only | No conflict |
| `tests/integration/conftest.py` | 2 only | No conflict |
| `.github/workflows/ci.yml` | 3 only | No conflict |

**Independent streams (can run in parallel):**
- Stream A: Section 1 (skill integration) — independent of all others
- Stream B: Section 2 (test infrastructure) — independent of Section 1
- Stream C: Section 3 (CI/CD) — depends on Section 2 (needs fixtures to exist)
- Stream D: Section 4 (CLI verification) — depends on existing CLI code
- Stream E: Section 5 (documentation) — after all implementation

---

## 1. OpenSpec Skill Integration

**Depends on:** Nothing (existing `neon-branch` skill is already created)
**Files:** `.claude/skills/openspec-*/SKILL.md`

- [x] 1.1 Update `openspec-apply-change/SKILL.md` to include optional Neon branch creation
  - Add step between "Select the change" and "Read context files":
    "If Neon credentials are available (`aca neon list` succeeds), create branch `claude/<change-name>` via the `neon-branch` skill (create action)"
  - Include fallback: "If Neon is unavailable, skip silently and use local database"
  - Note: branch creation includes running `alembic upgrade head`

- [ ] 1.2 Update `openspec-verify-change/SKILL.md` to include optional branch verification
  - Add step after "Verify Completeness" and before "Generate Report":
    "If a Neon branch `claude/<change-name>` exists, run tests against it via the `neon-branch` skill (verify action)"
  - Add branch test results to the verification report under a new "Branch Testing" section
  - If no branch exists, note "No Neon branch found — tests ran against local database"

- [ ] 1.3 Update `openspec-archive-change/SKILL.md` to include branch cleanup
  - Add step after "Perform the archive":
    "If a Neon branch `claude/<change-name>` exists, delete it via the `neon-branch` skill (cleanup action)"
  - This is cleanup, not validation — proceed with archive even if branch deletion fails
  - Log: "Cleaned up Neon branch: claude/<change-name>" or "No Neon branch to clean up"

## 2. Test Infrastructure

**Depends on:** Nothing (builds on existing `tests/integration/fixtures/neon.py`)
**Files:** `tests/integration/conftest.py`, `pyproject.toml`

- [ ] 2.1 Register `neon` pytest marker in `pyproject.toml`
  - Add to `[tool.pytest.ini_options]` markers list:
    `"neon: marks tests that require Neon database credentials (deselect with '-m not neon')"`

- [ ] 2.2 Add `neon_available` session fixture to `tests/integration/conftest.py`
  - Check `settings.neon_api_key` and `settings.neon_project_id` are both set
  - Return boolean, don't skip — let individual tests decide
  - Import from Settings with `_env_file=None` to isolate from local `.env`

- [ ] 2.3 Add `neon_session_branch` session-scoped fixture to `tests/integration/conftest.py`
  - **Depends on:** 2.2
  - Create branch `claude/test-session-{timestamp}` on setup
  - Run `alembic upgrade head` against the branch connection string
  - Yield the connection string
  - Delete the branch on teardown (ignore 404 errors)
  - Skip if `neon_available` is False

- [ ] 2.4 Add `neon_engine` session-scoped fixture
  - **Depends on:** 2.3
  - Create SQLAlchemy engine from `neon_session_branch` connection string
  - Apply Neon-appropriate engine options (SSL, pool settings)
  - Dispose engine on teardown

- [ ] 2.5 Verify existing Neon fixtures in `tests/integration/fixtures/neon.py` are importable from conftest
  - Ensure `neon_isolated_branch` (function-scoped) fixture is registered
  - Add `conftest_plugins` import if needed

## 3. CI/CD Integration

**Depends on:** Section 2 (fixtures must exist for tests to run)
**Files:** `.github/workflows/ci.yml`

- [ ] 3.1 Add `test-neon` job to `.github/workflows/ci.yml`
  - Condition: `if: ${{ secrets.NEON_API_KEY != '' }}`
  - Environment variables: `NEON_API_KEY`, `NEON_PROJECT_ID`
  - Runs: `pytest tests/integration/test_neon_integration.py -v`
  - Uses same Python version and setup steps as existing test job

- [ ] 3.2 Add branch cleanup as post-job step in the `test-neon` job
  - After tests: `aca neon clean --prefix "claude/test-" --older-than 1 --force`
  - This catches orphaned branches from failed test runs
  - `continue-on-error: true` — cleanup failure shouldn't fail the job

- [ ] 3.3 Document required repository secrets in a comment block in the CI workflow
  - `NEON_API_KEY`: "Neon API key for branch management (optional — job skipped if not set)"
  - `NEON_PROJECT_ID`: "Neon project ID (required with NEON_API_KEY)"

## 4. CLI Verification and Hardening

**Depends on:** Existing `src/cli/neon_commands.py` (already created)
**Files:** `tests/test_cli/` (new), `src/cli/neon_commands.py`

- [ ] 4.1 Add unit tests for `aca neon` CLI commands
  - Test `list` command with mocked `NeonBranchManager` (mock httpx responses)
  - Test `create` command success and error paths
  - Test `delete` command with `--force` flag
  - Test `connection` command with `--pooled` and `--direct` flags
  - Test `clean` command with stale branch filtering logic
  - Test missing credentials error message

- [ ] 4.2 Add `--json` output validation to CLI tests
  - **Depends on:** 4.1
  - Verify JSON output structure matches expected schema for each command
  - Test `list --json` returns `{"branches": [...]}`
  - Test `create --json` returns `{"id": ..., "connection_string": ...}`

- [ ] 4.3 Handle edge case: `aca neon create` when branch already exists
  - **Depends on:** 4.1
  - Currently raises `NeonAPIError` — should catch and suggest `--force` recreate
  - Add `--force` flag to `create` command: delete existing + recreate

## 5. Documentation

**Depends on:** Sections 1-4 (document after implementation)

- [ ] 5.1 Update `CLAUDE.md` "Critical Gotchas" table with Neon branching gotchas
  - "Neon branch cleanup is manual" → "Run `aca neon clean` or let archive skill handle it"
  - "Neon free tier: 10 branches max" → "Use `aca neon clean --older-than 24` aggressively"
  - "Agent branches need `alembic upgrade head`" → "The neon-branch skill handles this"

- [ ] 5.2 Update `docs/SETUP.md` Neon section with agent workflow instructions
  - Add subsection: "Neon Branching for Agent Workflows"
  - Document the skill lifecycle: create → implement → verify → cleanup
  - Add CLI quick-reference for `aca neon` commands

- [ ] 5.3 Add Neon branch management to `docs/DEVELOPMENT.md` development workflow section
  - Add workflow diagram: "Start feature → Create branch → Implement → Test on branch → Archive → Delete branch"
  - Reference the `neon-branch` skill for Claude Code users
