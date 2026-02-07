# database-provider Specification

## Purpose
TBD - created by archiving change add-supabase-cloud-database. Update Purpose after archive.
## Requirements
### Requirement: Database Provider Abstraction

The system SHALL provide a database provider abstraction that allows different PostgreSQL hosting solutions to be used interchangeably.

#### Scenario: Provider protocol definition
- **WHEN** a new database provider is implemented
- **THEN** it SHALL implement the `DatabaseProvider` protocol
- **AND** the protocol SHALL define methods for:
  - `name` property returning provider identifier
  - `get_engine_url()` returning SQLAlchemy connection URL
  - `get_engine_options()` returning provider-specific engine configuration
  - `health_check(engine)` verifying database connectivity

#### Scenario: Provider selection is transparent
- **WHEN** application code requests a database session
- **THEN** the session SHALL be provided without knowledge of the underlying provider
- **AND** all existing database operations SHALL work unchanged

### Requirement: Local PostgreSQL Provider

The system SHALL support local PostgreSQL installations as the default database provider.

#### Scenario: Local provider from DATABASE_URL
- **GIVEN** `DATABASE_URL` is set to a local PostgreSQL connection string
- **AND** no Supabase configuration is present
- **WHEN** the database provider is initialized
- **THEN** the local PostgreSQL provider SHALL be selected

#### Scenario: Local provider default configuration
- **WHEN** local PostgreSQL provider is used
- **THEN** engine options SHALL include:
  - `pool_pre_ping=True` for connection validation
  - Standard pool size appropriate for local development

### Requirement: Supabase Cloud Provider

The system SHALL support Supabase as a cloud-hosted PostgreSQL provider.

#### Scenario: Supabase detection from URL
- **GIVEN** `DATABASE_URL` contains `.supabase.`
- **WHEN** the database provider is initialized
- **THEN** the Supabase provider SHALL be automatically selected

#### Scenario: Supabase detection from config
- **GIVEN** `SUPABASE_PROJECT_REF` and `SUPABASE_DB_PASSWORD` are set
- **WHEN** the database provider is initialized
- **THEN** the Supabase provider SHALL be selected
- **AND** the connection URL SHALL be constructed from configuration

#### Scenario: Supabase connection pooling
- **WHEN** Supabase provider is used
- **THEN** engine options SHALL include:
  - `pool_pre_ping=True`
  - `pool_size=5` (limited for free tier)
  - `pool_recycle=300` for connection refresh
  - `sslmode=require` for secure connections

### Requirement: Provider Factory

The provider factory SHALL detect and instantiate the appropriate database provider based on configuration, with Neon added to the detection chain.

> Extends the base Provider Factory requirement to include Railway in the detection chain.

#### Scenario: Automatic provider detection (MODIFIED)
> **Change**: Adds Railway as an explicit provider option.

- **GIVEN** no explicit `DATABASE_PROVIDER` is set
- **WHEN** the provider factory is called
- **THEN** the provider SHALL be detected based on configuration in order:
  1. Explicit `DATABASE_PROVIDER` override (supports: `local`, `supabase`, `neon`, `railway`)
  2. `NEON_PROJECT_ID` present → Neon provider
  3. `SUPABASE_PROJECT_REF` present → Supabase provider
  4. `.neon.tech` in DATABASE_URL → Neon provider
  5. `.supabase.` in DATABASE_URL → Supabase provider
  6. Default → Local PostgreSQL provider

#### Scenario: Provider initialization failure (MODIFIED)
> **Change**: Adds diagnostic information to error messages.

- **WHEN** provider configuration is invalid
- **THEN** a clear error message SHALL be raised
- **AND** the error SHALL indicate which provider was detected and what configuration is missing

### Requirement: Backward Compatibility

The system SHALL maintain full backward compatibility with existing DATABASE_URL configurations.

#### Scenario: Existing local configuration unchanged
- **GIVEN** an existing deployment uses `DATABASE_URL=postgresql://user:pass@localhost/db`
- **WHEN** upgrading to the new provider abstraction
- **THEN** no configuration changes SHALL be required

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

### Requirement: Railway PostgreSQL Provider

The system SHALL support Railway as a PostgreSQL provider using a custom Docker image based on PostgreSQL 17 with pre-installed extensions (pgvector, pg_search, pgmq, pg_cron).

#### Scenario: Railway provider from explicit configuration
- **GIVEN** `DATABASE_PROVIDER=railway` is set
- **AND** `DATABASE_URL` or `RAILWAY_DATABASE_URL` is configured
- **WHEN** the database provider is initialized
- **THEN** the Railway provider SHALL be selected

#### Scenario: Railway provider missing URL raises error
- **GIVEN** `DATABASE_PROVIDER=railway` is set
- **AND** neither `DATABASE_URL` nor `RAILWAY_DATABASE_URL` is configured
- **WHEN** the database provider is initialized
- **THEN** a clear error message SHALL be raised indicating a URL is required

#### Scenario: Railway connection configuration
- **WHEN** Railway provider is used
- **THEN** engine options SHALL include:
  - `pool_pre_ping=True` for connection validation
  - `pool_size=3` (default for Hobby plan, 512 MB RAM)
  - `max_overflow=2` (conservative for shared hosting)
  - `pool_recycle=300` for connection refresh
  - `sslmode=require` for secure connections
  - `statement_timeout=30000` (30s) for runaway query protection

#### Scenario: Railway migration URL routing
- **WHEN** `get_migration_database_url()` is called with `DATABASE_PROVIDER=railway`
- **THEN** it SHALL return `RAILWAY_DATABASE_URL` if set, otherwise `DATABASE_URL`
- **AND** it SHALL NOT fall through to the local provider's URL

#### Scenario: Railway extension support flags
- **WHEN** Railway provider is used with the custom PostgreSQL 17 image
- **THEN** `supports_pg_cron()` SHALL return `True` by default
- **AND** extension flags (`railway_pg_cron_enabled`, `railway_pgvector_enabled`, `railway_pg_search_enabled`, `railway_pgmq_enabled`) SHALL be configurable via settings

#### Scenario: Railway queue connection
- **WHEN** `get_queue_url()` is called on the Railway provider
- **THEN** it SHALL return the same database URL (no pooler separation needed)
- **AND** `get_queue_options()` SHALL return a larger pool for worker processes

#### Scenario: Railway Docker image extension versions
- **WHEN** the Railway PostgreSQL Docker image is built
- **THEN** it SHALL use PostgreSQL 17 as the base image
- **AND** it SHALL include pgvector v0.8.0, pg_cron v1.6.4, pgmq v1.4.4, and pg_search v0.13.0
- **AND** both `pg_cron` and `pg_search` SHALL be listed in `shared_preload_libraries`
