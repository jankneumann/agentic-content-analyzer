# Design: Neon Branch Management for Agent Workflows

## Context

Neon's copy-on-write branching creates isolated database copies in milliseconds, regardless of database size. This is the key capability that makes agent-driven development practical — each agent session gets its own database without the overhead of provisioning, seeding, or cleaning up.

The `NeonBranchManager` class (`src/storage/providers/neon_branch.py`) is fully implemented with:
- `create_branch()`, `delete_branch()`, `list_branches()`, `get_connection_string()`
- `branch_context()` async context manager for auto-cleanup
- Exponential backoff retry on rate limits
- Endpoint readiness polling

The `aca neon` CLI commands and `neon-branch` skill design are ready. Additionally, the official
Neon CLI (`neonctl`, install via `npm i -g neonctl`) provides features our Python CLI lacks:
- **`--expires-at`**: Auto-delete branches after a TTL (eliminates orphaned branch problem)
- **`schema-diff`**: Compare schemas between branches (powerful verification tool)
- **`connection-string --pooled`**: Direct connection string retrieval

The skill should prefer `neonctl` when available and fall back to `aca neon`.
What remains is wiring them into the agent workflow lifecycle and test infrastructure.

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

### Decision 2: Prefer neonctl, Fall Back to aca neon

**What**: The `neon-branch` skill detects whether `neonctl` (official Neon CLI) is installed and prefers it over `aca neon` for branch operations.

**Why**:
- `neonctl` provides `--expires-at` for auto-expiring branches — eliminates orphaned branch problem
- `neonctl` provides `schema-diff` — catches unintended schema changes during verification
- `aca neon` is still needed: Python test fixtures use `NeonBranchManager` directly, and `aca neon clean` has built-in prefix/age filtering that `neonctl` lacks

**Tool selection matrix**:

| Operation | Preferred (`neonctl`) | Fallback (`aca neon`) |
|-----------|----------------------|----------------------|
| Create branch | `neonctl branches create --expires-at +48h` | `aca neon create` (no TTL) |
| Schema diff | `neonctl branches schema-diff main <branch>` | Not available |
| Connection string | `neonctl connection-string <branch> --pooled` | `aca neon connection <branch>` |
| Delete branch | `neonctl branches delete <branch>` | `aca neon delete <branch> --force` |
| Bulk cleanup | Not available | `aca neon clean --prefix claude/ --older-than 24` |
| Python test fixtures | Not applicable | `NeonBranchManager` (async API) |

**Detection pattern**:
```bash
if command -v neonctl &>/dev/null; then
  NEON_CLI="neonctl"
else
  NEON_CLI="aca neon"
fi
```

### Decision 3: Skill Integration via Documented Convention (Not Hard Wiring)

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

### Decision 4: Branch Naming Convention

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

### Decision 5: Test Infrastructure — Session-Scoped Branch Fixture

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

### Decision 6: CI/CD — Neon GitHub Actions + Profile-Aware Workflows

**What**: Use Neon's official GitHub Actions (`create-branch-action`, `delete-branch-action`,
`schema-diff-action`) in CI workflows, and make CI jobs profile-aware so they use the same
configuration system as local development.

**Why**:
- Neon provides purpose-built GitHub Actions that handle branch lifecycle automatically
- `create-branch-action@v6` supports `expires_at` — CI branches auto-cleanup even if jobs crash
- `schema-diff-action@v1` auto-comments on PRs with schema change diffs — reviewers see DB changes without reading SQL
- Profile-aware CI means CI and local development share the same config resolution logic (no hardcoded env vars)
- Forks and PRs from external contributors won't have the secret — Neon jobs are skipped

**Neon GitHub Actions ecosystem**:

| Action | Version | Purpose |
|--------|---------|---------|
| `neondatabase/create-branch-action` | `@v6` | Create branch per PR, returns `db_url`, `db_url_pooled`, `branch_id` |
| `neondatabase/delete-branch-action` | `@v3` | Delete branch on PR close |
| `neondatabase/schema-diff-action` | `@v1` | Diff schemas, post PR comment |

**PR-based branch lifecycle**:
```
PR opened/synchronized → create-branch-action → alembic upgrade head → tests → schema-diff
PR closed             → delete-branch-action
```

**Profile-aware CI pattern**:

Currently, CI jobs hardcode env vars like `DATABASE_URL` and `ANTHROPIC_API_KEY`. Instead,
CI jobs should use `PROFILE=<name>` to activate a profile, just like local development.

| CI Job | Profile | Purpose |
|--------|---------|---------|
| `lint` | None needed | Static analysis, no DB |
| `test` | None (local postgres service) | Unit tests against local PG |
| `test-neon` | `ci-neon` | Integration tests on Neon branch |
| `validate-profiles` | Each profile | Already profile-aware |

The `ci-neon` profile extends `base` with `database: neon` and takes connection
strings from the `create-branch-action` outputs:

```yaml
# profiles/ci-neon.yaml
name: ci-neon
extends: base
description: CI job profile — Neon branch created per PR

providers:
  database: neon
  neo4j: local      # CI doesn't need real Neo4j for most tests
  storage: local
  observability: noop

settings:
  environment: test
  database:
    # Injected by create-branch-action output → env var
    neon_database_url: "${NEON_DATABASE_URL}"
    neon_api_key: "${NEON_API_KEY:-}"
    neon_project_id: "${NEON_PROJECT_ID:-}"
```

**Complete CI workflow pattern** (new `neon-pr.yml`):

```yaml
name: Neon PR Branch
on:
  pull_request:
    types: [opened, reopened, synchronize, closed]

jobs:
  # Create branch on PR open/update
  create-branch:
    if: |
      github.event.action != 'closed' &&
      vars.NEON_PROJECT_ID != ''
    runs-on: ubuntu-latest
    outputs:
      db_url: ${{ steps.create.outputs.db_url }}
      db_url_pooled: ${{ steps.create.outputs.db_url_pooled }}
      branch_id: ${{ steps.create.outputs.branch_id }}
    steps:
      - uses: neondatabase/create-branch-action@v6
        id: create
        with:
          project_id: ${{ vars.NEON_PROJECT_ID }}
          api_key: ${{ secrets.NEON_API_KEY }}
          branch_name: preview/pr-${{ github.event.number }}
          parent_branch: main
          expires_at: $(date -u -d '+48 hours' +%Y-%m-%dT%H:%M:%SZ)

  # Run migrations + tests on the Neon branch
  test-neon:
    needs: create-branch
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv pip install --system -e ".[dev]"

      - name: Run migrations on Neon branch
        env:
          DATABASE_URL: ${{ needs.create-branch.outputs.db_url }}
        run: alembic upgrade head

      - name: Run tests against Neon branch
        env:
          PROFILE: ci-neon
          NEON_DATABASE_URL: ${{ needs.create-branch.outputs.db_url_pooled }}
          NEON_API_KEY: ${{ secrets.NEON_API_KEY }}
          NEON_PROJECT_ID: ${{ vars.NEON_PROJECT_ID }}
          ANTHROPIC_API_KEY: test-key-for-ci
        run: pytest tests/ -v -m "not slow"

  # Schema diff comment on PR
  schema-diff:
    needs: create-branch
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: neondatabase/schema-diff-action@v1
        with:
          project_id: ${{ vars.NEON_PROJECT_ID }}
          api_key: ${{ secrets.NEON_API_KEY }}
          compare_branch: preview/pr-${{ github.event.number }}
          base_branch: main

  # Delete branch on PR close
  delete-branch:
    if: github.event.action == 'closed'
    runs-on: ubuntu-latest
    steps:
      - uses: neondatabase/delete-branch-action@v3
        with:
          project_id: ${{ vars.NEON_PROJECT_ID }}
          api_key: ${{ secrets.NEON_API_KEY }}
          branch: preview/pr-${{ github.event.number }}
```

### Decision 7: CI Profile for Neon Integration Tests

**What**: Add a `ci-neon.yaml` profile that CI uses when running tests against a Neon branch.

**Why**:
- CI should use the same profile system as local development — no hardcoded env vars
- The Neon branch connection string comes from the `create-branch-action` output
- `database: neon` provider ensures correct pool settings, SSL, etc.
- Other providers (neo4j, storage) stay `local` — CI doesn't need cloud services for unit tests

**How profiles flow in CI**:
```
create-branch-action → outputs db_url → env NEON_DATABASE_URL
                                       → env PROFILE=ci-neon
                                       → profiles/ci-neon.yaml reads ${NEON_DATABASE_URL}
                                       → Settings resolves to Neon provider
```

## Risks / Trade-offs

### Risk: Neon Free Tier Branch Limits
- **Issue**: 10 branches max; concurrent PRs + agents could exhaust this
- **Mitigation**: `expires_at` on `create-branch-action` auto-cleans CI branches (48h);
  agent branches use `--expires-at` via `neonctl` (48h); `aca neon clean` as backup;
  CI reuses `preview/pr-<number>` (same PR = same branch, not new one)

### Risk: Branch Creation Latency
- **Issue**: 2-5s endpoint wake-up adds delay to skill invocation
- **Mitigation**: Branch creation is a one-time cost per session, not per task;
  `_wait_for_endpoint_ready()` already polls with 2s interval

### Risk: Orphaned Branches from Crashed Sessions
- **Issue**: If an agent session crashes, the cleanup step never runs
- **Mitigation**: `expires_at` on both CI (`create-branch-action`) and agent
  (`neonctl --expires-at`) branches means they auto-delete after 48h regardless.
  `aca neon clean --prefix claude/ --older-than 24` as additional safety net.

### Risk: Schema Diff Noise
- **Issue**: `schema-diff-action` may comment on every PR push, even without schema changes
- **Mitigation**: The action only posts a comment when there ARE differences;
  no-diff = no comment. Updates existing comment on re-push (doesn't spam).

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

### Phase 3: CI/CD — Neon GitHub Actions
7. Create `profiles/ci-neon.yaml` profile
8. Create `.github/workflows/neon-pr.yml` with full PR lifecycle
9. Update `.github/workflows/ci.yml` to add `test-neon` job (or delegate to `neon-pr.yml`)
10. Add `NEON_API_KEY` secret and `NEON_PROJECT_ID` variable to repository settings
11. Document required secrets in README/contributing guide

### Rollback Plan
- Phase 1: Revert SKILL.md changes (additive text, no code)
- Phase 2: Remove fixtures (no other code depends on them)
- Phase 3: Remove `neon-pr.yml` and `ci-neon.yaml` profile (no effect on main CI or local development)

## Resolved Questions

1. **Should branch creation block session start?**
   - **Decision**: No. Create branches on-demand when `/opsx:apply` starts, not on session start. This avoids wasted branches for sessions that don't need DB isolation.

2. **Should tests automatically use Neon when available?**
   - **Decision**: No. Tests must explicitly opt in via `@pytest.mark.neon` or by using the `neon_session_branch` fixture. This prevents surprise behavior when developers have Neon credentials set.

3. **Should the clean command run automatically?**
   - **Decision**: No. Keep it manual (`aca neon clean`) or add to CI post-job step. Automatic cleanup risks deleting branches that other active sessions are using.
