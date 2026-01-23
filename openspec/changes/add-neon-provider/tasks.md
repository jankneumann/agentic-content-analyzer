# Tasks: Add Neon Provider

## 1. Core Provider Implementation

- [x] 1.1 Create `src/storage/providers/neon.py` with `NeonProvider` class
  - Implement `DatabaseProvider` protocol (name, get_engine_url, get_engine_options, health_check)
  - Add `get_direct_url()` method for migrations (removes `-pooler` suffix)
  - Configure engine options for Neon (SSL required, connection pooling settings)

- [x] 1.2 Update `src/storage/providers/factory.py`
  - Add `"neon"` to `detect_provider()` function (check for `.neon.tech` in URL)
  - Add Neon instantiation in `get_provider()` function
  - Update type hints to include `Literal["local", "supabase", "neon"]`

- [x] 1.3 Update `src/storage/providers/__init__.py`
  - Export `NeonProvider` class

- [x] 1.4 Add Neon settings to `src/config/settings.py`
  - `neon_api_key: str | None` - API key for branch management
  - `neon_project_id: str | None` - Project ID for branch management
  - `neon_default_branch: str = "main"` - Default parent branch
  - `neon_region: str | None` - Region (auto-detected from URL if not set)
  - `neon_direct_url: str | None` - Direct URL for migrations

## 2. Branch Manager Implementation

- [x] 2.1 Create `src/storage/providers/neon_branch.py` with `NeonBranchManager` class
  - Async methods: `create_branch()`, `delete_branch()`, `list_branches()`, `get_connection_string()`
  - Support point-in-time branching via `from_timestamp` and `from_lsn` parameters
  - Use `httpx` for Neon API calls with proper error handling
  - Implement exponential backoff for rate limiting

- [x] 2.2 Create `NeonBranch` Pydantic model for branch data
  - Fields: `id`, `name`, `parent_id`, `created_at`, `connection_string`

- [x] 2.3 Add `branch_context()` async context manager
  - Creates branch on enter, deletes on exit
  - Returns connection string for use during context

## 3. Alembic Integration

- [x] 3.1 Update `alembic/env.py` to support Neon direct connections
  - Check for `NEON_DIRECT_URL` environment variable
  - Use direct (non-pooled) URL for migrations

## 4. Unit Tests

- [x] 4.1 Create `tests/test_storage/test_neon_provider.py`
  - Test URL detection logic in factory
  - Test pooled vs direct URL conversion
  - Test engine options configuration
  - Mock health check behavior
  - Note: Tests added to existing `test_providers.py` file (16 new tests)

- [x] 4.2 Create `tests/test_storage/test_neon_branch.py`
  - Mock Neon API responses
  - Test branch CRUD operations
  - Test error handling and retries
  - Test point-in-time branching parameters

## 5. Integration Test Fixtures

- [x] 5.1 Create `tests/integration/fixtures/neon.py`
  - `neon_test_branch` fixture (module-scoped)
  - `neon_isolated_branch` fixture (function-scoped)
  - Skip if `NEON_API_KEY` not set
  - Cleanup branches after test session

- [x] 5.2 Create example integration test using Neon branch
  - Fixtures include docstrings with usage examples
  - Context manager pattern demonstrated

## 6. Documentation

- [x] 6.1 Update `docs/SETUP.md` with Neon configuration section
  - Account creation and project setup
  - Connection string formats (pooled vs direct)
  - Environment variable configuration
  - Migration setup

- [x] 6.2 Add agent workflow documentation
  - Branch naming conventions for agents
  - Example: Creating feature branch for Claude Code session
  - Example: CI/CD workflow with ephemeral branches
  - Programmatic branch management examples

- [x] 6.3 Update `CLAUDE.md` with Neon-specific guidance
  - Database providers table with detection patterns
  - Quick branching example for agents
  - Added gotcha for scale-to-zero cold start latency

## 7. Validation

- [x] 7.1 Run existing provider tests to ensure no regressions
  - All 72 storage tests pass
- [ ] 7.2 Test with real Neon account (manual verification)
- [ ] 7.3 Verify Alembic migrations work with Neon direct connection
