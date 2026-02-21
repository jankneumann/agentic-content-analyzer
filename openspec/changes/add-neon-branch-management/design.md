# Design: Neon Branch Management for Agent Workflows

## Context

Neon's copy-on-write branching creates isolated database copies in milliseconds, regardless of database size. This is the key capability that makes agent-driven development practical — each agent session gets its own database without the overhead of provisioning, seeding, or cleaning up.

The `NeonBranchManager` class (`src/storage/providers/neon_branch.py`) is fully implemented with:
- `create_branch()`, `delete_branch()`, `list_branches()`, `get_connection_string()`
- `branch_context()` async context manager for auto-cleanup
- Exponential backoff retry on rate limits
- Endpoint readiness polling

The `aca neon` CLI commands and `neon-branch` skill are already created. What remains is wiring them into the agent workflow lifecycle and test infrastructure.

### Stakeholders
- **Agent sessions** (Claude Code): Need isolated DB per session, automatic cleanup
- **CI/CD**: Need Neon integration tests to run, not be skipped
- **Developers**: Need branch-per-test option for realistic integration tests

### Constraints
- Neon is always optional — no hard dependency (graceful fallback to local)
- Free tier limits: 10 branches, 100 CU-hours — `clean` must be aggressive
- Branch creation adds 2-5s cold start (endpoint wake-up)
- The `claude/` branch naming prefix is reserved for agent-managed branches

## Goals / Non-Goals

### Goals
- Agent sessions automatically get isolated database branches when Neon credentials are available
- OpenSpec skills invoke `neon-branch` at the right lifecycle points
- Test infrastructure auto-selects Neon branches when credentials are present
- CI runs Neon integration tests when secrets are configured

### Non-Goals
- Mandatory Neon usage (always optional)
- Multi-project Neon management
- Custom branch retention policies beyond time-based cleanup
- Branch-level access control or read-only branches

## Decisions

### Decision 1: Optional Integration via Credential Detection

**What**: All Neon integration is gated on `NEON_API_KEY` and `NEON_PROJECT_ID` being set. When missing, everything falls back to the current behavior silently.

**Why**:
- Agents running locally without Neon credentials must not break
- No configuration changes needed for existing setups
- Detection is already implemented in `NeonBranchManager._validate_config()`

**Pattern**:
```python
# In conftest.py or skill
neon_available = bool(settings.neon_api_key and settings.neon_project_id)
if neon_available:
    # Use Neon branch
else:
    # Fall back to local database
```

### Decision 2: Skill Integration via Documented Convention (Not Hard Wiring)

**What**: Update the OpenSpec skill SKILL.md files to include optional Neon branch steps, rather than creating a middleware or hook system.

**Why**:
- Skills are markdown instructions interpreted by Claude Code — there's no runtime to hook into
- Adding "If Neon credentials are available, invoke neon-branch create" to the skill text is the correct integration mechanism
- The `neon-branch` skill already documents the contract: create → verify → cleanup
- Claude Code can read both skills and compose them

**Alternative considered**: A `.claude/settings.json` SessionStart hook that auto-creates branches. Rejected because:
- SessionStart hooks run shell commands, not skills
- Branch creation is async (2-5s) and may fail — shouldn't block session start
- Better to create branches on-demand when work actually starts

### Decision 3: Branch Naming Convention

**What**: All agent-managed branches use the pattern `claude/<change-name>` or `claude/<session-id>`.

**Why**:
- The `clean` command uses prefix matching to identify deletable branches
- Prevents accidental deletion of production branches
- Consistent with git branch naming (`claude/feature-xyz`)
- `main` and any non-`claude/` branches are protected

**Examples**:
```
claude/add-neon-branch-management    # For OpenSpec changes
claude/session-abc123                # For ad-hoc sessions
claude/test-run-456                  # For CI test runs
```

### Decision 4: Test Infrastructure — Session-Scoped Branch Fixture

**What**: Add a `neon_session_branch` fixture to `tests/integration/conftest.py` that creates one branch per test session and shares it across all tests.

**Why**:
- Creating a branch per test would exhaust the 10-branch free tier limit
- Session scope means one branch for the entire `pytest` run
- The existing `neon_isolated_branch` (function-scoped) fixture is available for tests needing per-test isolation
- Tests can opt in via `@pytest.mark.neon` marker

**Pattern**:
```python
@pytest.fixture(scope="session")
def neon_session_branch(neon_available):
    """Create one branch per test session, shared across all tests."""
    if not neon_available:
        pytest.skip("Neon credentials not available")
    # Create branch, yield connection string, delete on teardown
```

### Decision 5: CI/CD — Conditional Job with Repository Secrets

**What**: Add a `test-neon` job to `.github/workflows/ci.yml` that runs only when `NEON_API_KEY` secret exists.

**Why**:
- Forks and PRs from external contributors won't have the secret — job is skipped
- The project maintainer adds `NEON_API_KEY` and `NEON_PROJECT_ID` to repository secrets
- Uses a dedicated Neon branch `ci/<run-id>` that's cleaned up after the job

**Pattern**:
```yaml
test-neon:
  if: ${{ secrets.NEON_API_KEY != '' }}
  env:
    NEON_API_KEY: ${{ secrets.NEON_API_KEY }}
    NEON_PROJECT_ID: ${{ secrets.NEON_PROJECT_ID }}
```

## Risks / Trade-offs

### Risk: Neon Free Tier Branch Limits
- **Issue**: 10 branches max; concurrent agents could exhaust this
- **Mitigation**: `aca neon clean` runs aggressively (24h default); CI creates and deletes in the same job; agents share session branches when possible

### Risk: Branch Creation Latency
- **Issue**: 2-5s endpoint wake-up adds delay to skill invocation
- **Mitigation**: Branch creation is a one-time cost per session, not per task; `_wait_for_endpoint_ready()` already polls with 2s interval

### Risk: Orphaned Branches from Crashed Sessions
- **Issue**: If an agent session crashes, the cleanup step never runs
- **Mitigation**: `aca neon clean --prefix claude/ --older-than 24` is idempotent and safe to run on a schedule or manually

### Trade-off: Convention Over Enforcement
- **Trade-off**: Relying on skill text conventions rather than runtime hooks means agents might skip branch steps
- **Accepted**: This is how Claude Code skills work — markdown instructions. A runtime hook would require a custom framework that doesn't exist.

## Migration Plan

### Phase 1: Skill Integration (No Code Changes)
1. Update `openspec-apply-change/SKILL.md` with optional Neon branch step
2. Update `openspec-verify-change/SKILL.md` with optional branch verification
3. Update `openspec-archive-change/SKILL.md` with optional branch cleanup

### Phase 2: Test Infrastructure
4. Add `neon_session_branch` fixture to integration conftest
5. Add `@pytest.mark.neon` marker to pytest configuration
6. Wire auto-detection into conftest

### Phase 3: CI/CD
7. Add `test-neon` job to GitHub Actions
8. Document required secrets in README/contributing guide

### Rollback Plan
- Phase 1: Revert SKILL.md changes (additive text, no code)
- Phase 2: Remove fixtures (no other code depends on them)
- Phase 3: Remove CI job (no effect on local development)

## Resolved Questions

1. **Should branch creation block session start?**
   - **Decision**: No. Create branches on-demand when `/opsx:apply` starts, not on session start. This avoids wasted branches for sessions that don't need DB isolation.

2. **Should tests automatically use Neon when available?**
   - **Decision**: No. Tests must explicitly opt in via `@pytest.mark.neon` or by using the `neon_session_branch` fixture. This prevents surprise behavior when developers have Neon credentials set.

3. **Should the clean command run automatically?**
   - **Decision**: No. Keep it manual (`aca neon clean`) or add to CI post-job step. Automatic cleanup risks deleting branches that other active sessions are using.
