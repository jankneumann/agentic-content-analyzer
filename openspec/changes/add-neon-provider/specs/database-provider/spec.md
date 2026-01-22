# Database Provider Capability - Neon Extension

## ADDED Requirements

### Requirement: Neon Serverless Provider

The system SHALL support Neon as a serverless PostgreSQL provider with copy-on-write branching capabilities.

#### Scenario: Neon detection from URL
- **GIVEN** `DATABASE_URL` contains `.neon.tech`
- **WHEN** the database provider is initialized
- **THEN** the Neon provider SHALL be automatically selected

#### Scenario: Neon pooled connection default
- **GIVEN** a Neon `DATABASE_URL` without `-pooler` suffix
- **WHEN** the Neon provider constructs the engine URL
- **THEN** it SHALL add `-pooler` to the endpoint for connection pooling
- **AND** up to 10,000 concurrent connections SHALL be supported

#### Scenario: Neon direct connection for migrations
- **WHEN** `get_direct_url()` is called on the Neon provider
- **THEN** it SHALL return the URL without `-pooler` suffix
- **AND** this URL SHALL be used for Alembic migrations

#### Scenario: Neon connection configuration
- **WHEN** Neon provider is used
- **THEN** engine options SHALL include:
  - `pool_pre_ping=True`
  - `pool_size=5` (conservative for serverless)
  - `pool_recycle=300` for connection refresh
  - `sslmode=require` for secure connections

### Requirement: Neon Branch Management

The system SHALL provide a `NeonBranchManager` class for programmatic database branch operations via the Neon API.

#### Scenario: Create branch from parent
- **GIVEN** `NEON_API_KEY` and `NEON_PROJECT_ID` are configured
- **WHEN** `create_branch(name="feature/my-feature", parent="main")` is called
- **THEN** a new database branch SHALL be created instantly via copy-on-write
- **AND** the branch connection string SHALL be returned

#### Scenario: Create branch from point in time
- **GIVEN** a valid Neon configuration
- **WHEN** `create_branch(name="restore", from_timestamp=datetime)` is called
- **THEN** the branch SHALL be created from the database state at that timestamp
- **AND** this enables time-travel debugging for agent workflows

#### Scenario: Delete branch
- **GIVEN** an existing branch name
- **WHEN** `delete_branch(name)` is called
- **THEN** the branch and its compute resources SHALL be deleted
- **AND** no data from the parent branch SHALL be affected

#### Scenario: List branches
- **WHEN** `list_branches()` is called
- **THEN** all branches in the project SHALL be returned
- **AND** each branch SHALL include: id, name, parent_id, created_at, connection_string

#### Scenario: Branch context manager for tests
- **WHEN** `async with branch_context(name) as conn_str:` is used
- **THEN** a branch SHALL be created on context entry
- **AND** the branch SHALL be deleted on context exit
- **AND** this enables isolated test execution

### Requirement: Neon Integration Test Fixtures

The system SHALL provide pytest fixtures for ephemeral database branches in integration tests.

#### Scenario: Module-scoped test branch
- **GIVEN** `NEON_API_KEY` is set in the test environment
- **WHEN** a test module uses the `neon_test_branch` fixture
- **THEN** a branch SHALL be created before the first test
- **AND** the branch SHALL be deleted after the last test
- **AND** all tests in the module SHALL share the branch

#### Scenario: Skip tests when Neon not configured
- **GIVEN** `NEON_API_KEY` is not set
- **WHEN** a test requests the `neon_test_branch` fixture
- **THEN** the test SHALL be skipped with a clear message

#### Scenario: Parallel test execution
- **WHEN** multiple test sessions run concurrently
- **THEN** each session SHALL create its own uniquely-named branch
- **AND** branches SHALL be named with pattern `test/{session_id}`

## MODIFIED Requirements

### Requirement: Provider Factory

The system SHALL provide a factory function that returns the appropriate database provider.

#### Scenario: Automatic provider detection
- **GIVEN** no explicit `DATABASE_PROVIDER` is set
- **WHEN** the provider factory is called
- **THEN** the provider SHALL be detected based on configuration in order:
  1. Explicit `DATABASE_PROVIDER` override
  2. `NEON_PROJECT_ID` present → Neon provider
  3. `SUPABASE_PROJECT_REF` present → Supabase provider
  4. `.neon.tech` in DATABASE_URL → Neon provider
  5. `.supabase.` in DATABASE_URL → Supabase provider
  6. Default → Local PostgreSQL provider

#### Scenario: Provider initialization failure
- **WHEN** provider configuration is invalid
- **THEN** a clear error message SHALL be raised
- **AND** the error SHALL indicate which provider was detected and what configuration is missing
