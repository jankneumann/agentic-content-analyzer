# Change: Add Neon Serverless PostgreSQL Provider

## Why

The current database provider abstraction supports local PostgreSQL and Supabase. Adding Neon as a provider unlocks unique capabilities for AI coding agent workflows:

1. **Instant copy-on-write branching**: Neon's storage architecture enables database branches in milliseconds, regardless of database size. This is ideal for coding agents that need isolated environments per feature or test run.

2. **Agent-native integration testing**: Each coding agent session can create an ephemeral database branch, run tests against real data without mocking, and delete it when done. No state pollution between sessions.

3. **Time-travel debugging**: Restore database state to any point within the retention window (down to millisecond precision). Useful for debugging failed agent runs or reverting accidental changes.

4. **Scale-to-zero compute**: Neon automatically scales compute to zero when idle, reducing costs for development/testing branches that are used intermittently.

5. **Competitive free tier**: 100 CU-hours/month with 500 MB storage on free plan (as of late 2025).

## What Changes

- **NEW**: `NeonProvider` class in `src/storage/providers/neon.py`
- **NEW**: `NeonBranchManager` utility for programmatic branch CRUD operations
- **NEW**: Environment variable detection for Neon URLs (`.neon.tech` pattern)
- **NEW**: CLI integration helper for `neonctl` commands
- **NEW**: Integration test fixtures using ephemeral Neon branches
- **MODIFIED**: `src/storage/providers/factory.py` to detect and instantiate Neon provider
- **MODIFIED**: `src/config/settings.py` to add Neon configuration options
- **MODIFIED**: `docs/SETUP.md` for Neon setup instructions
- **MODIFIED**: `alembic/env.py` to support Neon direct connections for migrations

## Configuration Examples

**Direct connection string**:
```bash
DATABASE_URL=postgresql://alex:AbC123dEf@ep-cool-darkness-123456.us-east-2.aws.neon.tech/dbname?sslmode=require
```

**Pooled connection (recommended for applications)**:
```bash
DATABASE_URL=postgresql://alex:AbC123dEf@ep-cool-darkness-123456-pooler.us-east-2.aws.neon.tech/dbname?sslmode=require
```

**Component-based config (for branch management)**:
```bash
NEON_API_KEY=neon_api_key_abc123
NEON_PROJECT_ID=proud-paper-123456
NEON_DEFAULT_BRANCH=main
NEON_REGION=us-east-2
```

## Branching for Agent Workflows

### Feature Development Branch
```bash
# Agent creates branch for feature work
neonctl branches create --name claude/feature-xyz --project-id $NEON_PROJECT_ID

# Get connection string for the branch
DATABASE_URL=$(neonctl connection-string claude/feature-xyz)

# Run tests, make changes...

# Delete when done
neonctl branches delete claude/feature-xyz
```

### Integration Test Fixtures
```python
@pytest.fixture
async def neon_test_branch():
    """Create ephemeral branch for test isolation."""
    branch_name = f"test/{uuid.uuid4().hex[:8]}"
    manager = NeonBranchManager()

    branch = await manager.create_branch(
        name=branch_name,
        parent="main",
    )

    yield branch.connection_string

    await manager.delete_branch(branch_name)
```

## Impact

- **New code**:
  - `src/storage/providers/neon.py` - Provider implementation
  - `src/storage/providers/neon_branch.py` - Branch management API client
  - `tests/integration/fixtures/neon.py` - Test fixtures

- **Affected code**:
  - `src/storage/providers/factory.py` - Add Neon detection
  - `src/storage/providers/__init__.py` - Export new classes
  - `src/config/settings.py` - Add Neon settings
  - `alembic/env.py` - Support Neon direct URLs for migrations
  - `docs/SETUP.md` - Neon setup instructions

- **Migration**: None required (existing DATABASE_URL continues to work)

## Related Proposals

### Database Provider Series
1. **add-supabase-cloud-database** (completed) - Initial provider abstraction
2. **add-neon-provider** (this proposal) - Neon with branching for agent workflows

### Cross-Cutting Concerns
- **add-observability**: Health checks for Neon connections
- **add-test-infrastructure**: Ephemeral branch fixtures for integration tests
- **add-deployment-pipeline**: CI/CD workflows using Neon branches per PR

## Non-Goals

- Multi-tenant branch management (each user manages their own Neon project)
- Automatic branch cleanup policies (manual or GitHub Actions-based)
- Data synchronization between Neon and other providers
