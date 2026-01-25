# Design: Neon Provider Implementation

## Context

Neon is a serverless PostgreSQL platform that separates storage and compute, enabling instant copy-on-write database branching. This architecture is particularly valuable for AI coding agents that need isolated database environments for feature development and testing.

**Stakeholders**:
- AI coding agents (Claude Code, Cursor, etc.) - primary users of branching
- Developers running integration tests
- CI/CD pipelines needing ephemeral test databases

**Constraints**:
- Must follow existing `DatabaseProvider` protocol
- Neon API requires API key for branch operations
- Connection strings differ between pooled and direct connections
- Free tier has 100 CU-hours/month compute limit

## Goals / Non-Goals

### Goals
- Implement `NeonProvider` following the existing provider protocol
- Enable automatic detection of Neon URLs in `factory.py`
- Provide `NeonBranchManager` for programmatic branch CRUD
- Support both pooled (application) and direct (migration) connections
- Create pytest fixtures for ephemeral test branches

### Non-Goals
- Automatic branch lifecycle management (leave to GitHub Actions or manual)
- Multi-project management (one project per deployment)
- Billing/usage monitoring (use Neon dashboard)

## Decisions

### Decision 1: Connection String Detection

**What**: Detect Neon URLs by checking for `.neon.tech` domain pattern.

**Why**: Consistent with Supabase detection (`.supabase.` pattern). Neon URLs follow predictable formats:
- Direct: `ep-{adjective}-{noun}-{id}.{region}.aws.neon.tech`
- Pooled: `ep-{adjective}-{noun}-{id}-pooler.{region}.aws.neon.tech`

**Alternatives considered**:
- Explicit `DATABASE_PROVIDER=neon` - More verbose, less DX-friendly
- Check for `ep-` prefix - Too fragile, might match other providers

### Decision 2: Pooled vs Direct Connections

**What**: Default to pooled connections for application use, provide `get_direct_url()` for migrations.

**Why**: Neon recommends pooled connections for applications (supports up to 10,000 concurrent connections). Direct connections are needed for migrations and prepared statements.

**Implementation**:
```python
class NeonProvider:
    def get_engine_url(self) -> str:
        """Return pooled URL if available, otherwise direct."""
        if "-pooler" not in self._database_url:
            return self._make_pooled_url()
        return self._database_url

    def get_direct_url(self) -> str:
        """Return direct URL for migrations."""
        return self._database_url.replace("-pooler", "")
```

### Decision 3: Branch Manager as Separate Class

**What**: Create `NeonBranchManager` class separate from `NeonProvider`.

**Why**: Separation of concerns:
- `NeonProvider` - Connection management (implements protocol)
- `NeonBranchManager` - Branch lifecycle operations (Neon API client)

This allows using `NeonBranchManager` independently for test fixtures without requiring a full provider setup.

**Alternatives considered**:
- Add branching methods to `NeonProvider` - Violates single responsibility, bloats protocol
- Use Neon CLI directly - Less portable, harder to test

### Decision 4: Branch Manager API Design

**What**: Async-first API using `httpx` for Neon REST API calls.

```python
class NeonBranchManager:
    async def create_branch(
        self,
        name: str,
        parent: str = "main",
        *,
        from_timestamp: datetime | None = None,
        from_lsn: str | None = None,
    ) -> NeonBranch:
        """Create a new branch with optional point-in-time restore."""

    async def delete_branch(self, name: str) -> None:
        """Delete a branch by name."""

    async def list_branches(self) -> list[NeonBranch]:
        """List all branches in the project."""

    async def get_connection_string(
        self,
        branch: str,
        pooled: bool = True,
    ) -> str:
        """Get connection string for a branch."""
```

**Why**:
- Async matches FastAPI and modern Python patterns
- `httpx` is already a project dependency via Anthropic SDK
- Point-in-time options (`from_timestamp`, `from_lsn`) enable time-travel debugging

### Decision 5: Test Fixture Strategy

**What**: Provide both pytest fixtures and context managers for branch isolation.

```python
# Fixture for entire test module
@pytest.fixture(scope="module")
async def neon_test_branch():
    """Create branch for test module, cleanup after."""

# Context manager for fine-grained control
async with NeonBranchManager().branch_context("test/my-test") as conn_str:
    # Run tests with isolated database
```

**Why**: Different tests have different isolation needs:
- Module-scoped: Fast, shares branch across tests in module
- Context manager: Maximum isolation, branch per test

**Alternatives considered**:
- Function-scoped fixture only - Too slow (branch creation overhead per test)
- Class-scoped only - Less flexible than context manager

### Decision 6: Environment Variable Naming

**What**: Use `NEON_` prefix for Neon-specific configuration.

```bash
NEON_API_KEY=neon_api_key_...      # Required for branch management
NEON_PROJECT_ID=proud-paper-123456  # Required for branch management
NEON_DEFAULT_BRANCH=main            # Optional, defaults to "main"
NEON_REGION=us-east-2               # Optional, inferred from URL
```

**Why**: Consistent with `SUPABASE_` naming convention. `DATABASE_URL` remains the primary connection string variable.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Neon API rate limits | Implement exponential backoff in `NeonBranchManager` |
| Branch creation latency in tests | Use module-scoped fixtures, parallel test branches |
| Free tier compute exhaustion | Document limits, provide usage tracking example |
| API key security | Document `.env` best practices, never commit keys |

## Migration Plan

1. **No breaking changes**: Existing `DATABASE_URL` configurations continue to work
2. **Opt-in branching**: `NeonBranchManager` only used when `NEON_API_KEY` is set
3. **Gradual adoption**: Start with manual branch management, add fixtures later

### Rollback
- Remove `neon.py` and `neon_branch.py` files
- Revert factory.py changes
- No database migration required

## Open Questions

1. **Should branch cleanup be automatic?** Current design leaves cleanup to the caller. Could add `auto_delete_after` parameter for time-based cleanup.

2. **Support for Neon's new Data API?** Neon has a REST API for queries. Out of scope for this proposal but could be valuable for serverless functions.

3. **Branch naming conventions?** Proposed: `{agent|test|preview}/{identifier}`. Could enforce via validation in `NeonBranchManager`.
