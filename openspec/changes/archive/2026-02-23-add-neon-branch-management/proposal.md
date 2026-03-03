# Change: Add Neon Branch Management for Agent Workflows

## Why

The `NeonBranchManager` is fully implemented and tested (30 tests, async API, context managers, rate limiting) but **completely isolated** — nothing in the application activates it. The infrastructure is ready, the wiring is missing.

Six specific gaps prevent agents from using Neon branching:

1. **No CLI commands** — `aca neon` subcommand exists (just added) but needs integration testing and the OpenSpec skills don't invoke it
2. **No Makefile targets** — `neon-list`, `neon-create`, `neon-clean`, `test-neon` exist (just added) but lack verification
3. **No agent skill integration** — The `neon-branch` skill exists but the OpenSpec workflow skills (`/opsx:apply`, `/opsx:verify`, `/opsx:archive`) don't reference it
4. **No SessionStart hook** — No automatic branch creation when a Claude Code session starts
5. **No test infrastructure wiring** — Neon test fixtures exist but `conftest.py` doesn't auto-select Neon when credentials are present
6. **No CI/CD integration** — GitHub Actions doesn't have Neon secrets, so all Neon integration tests are auto-skipped

## What Changes

### Core Changes
- Wire the `neon-branch` skill into OpenSpec workflow skills as an optional phase
- Add a SessionStart hook that creates an ephemeral branch per agent session
- Integrate Neon branch fixtures into the test conftest for automatic DB selection
- Add CI/CD workflow for Neon integration tests

### Skill Changes (in agentic-coding-tools repo)
- Create `neon-branch` skill with create/verify/cleanup actions
- Update `openspec-apply-change` to optionally invoke `neon-branch create` before implementation
- Update `openspec-verify-change` to invoke `neon-branch verify` against branch data
- Update `openspec-archive-change` to invoke `neon-branch cleanup` after archiving

### Test Infrastructure Changes
- Auto-detect Neon credentials in conftest and use branch-per-test isolation
- Add `@pytest.mark.neon` marker for tests requiring real Neon
- Add GitHub Actions job for Neon integration tests

## Impact

### Affected Specs
- `database-provider` — Neon branch lifecycle (new capability)

### Affected Code
- `agentic-coding-tools` repo: `neon-branch` skill (new)
- `agentic-coding-tools` repo: `openspec-apply-change` skill (branch creation hook)
- `agentic-coding-tools` repo: `openspec-verify-change` skill (branch verification hook)
- `agentic-coding-tools` repo: `openspec-archive-change` skill (branch cleanup hook)
- `tests/conftest.py` — Auto-select Neon when available
- `tests/integration/conftest.py` — Branch-per-session fixture
- `.github/workflows/ci.yml` — Neon test job

### Expected Outcomes
| Metric | Current | After |
|--------|---------|-------|
| Agent DB isolation | None (shared local DB) | Full copy-on-write per session |
| Test data realism | Synthetic fixtures | Production data via branch |
| Branch cleanup | Manual | Automatic via skill + clean |
| CI Neon coverage | 0 tests (all skipped) | 14+ integration tests |

## Non-Goals
- Mandatory Neon usage (always optional, graceful fallback to local)
- Neon branching for non-agent workflows (manual users use local DB)
- Distributed branch management across multiple projects
- Automatic schema migration on branch creation in CI (manual for now)
