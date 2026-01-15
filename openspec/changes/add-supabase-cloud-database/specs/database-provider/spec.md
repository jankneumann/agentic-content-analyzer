# Database Provider Capability

## ADDED Requirements

### Requirement: Database Provider Abstraction

The system SHALL provide a database provider abstraction that allows different PostgreSQL hosting solutions to be used interchangeably without changes to application code.

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

The system SHALL support local PostgreSQL installations as the default database provider for development and self-hosted deployments.

#### Scenario: Local provider from DATABASE_URL
- **GIVEN** `DATABASE_URL` is set to a local PostgreSQL connection string
- **AND** no Supabase configuration is present
- **WHEN** the database provider is initialized
- **THEN** the local PostgreSQL provider SHALL be selected
- **AND** standard connection pooling SHALL be configured

#### Scenario: Local provider default configuration
- **WHEN** local PostgreSQL provider is used
- **THEN** engine options SHALL include:
  - `pool_pre_ping=True` for connection validation
  - No SSL requirement (optional for local)
  - Standard pool size appropriate for local development

### Requirement: Supabase Cloud Provider

The system SHALL support Supabase as a cloud-hosted PostgreSQL provider, enabling "bring your own Supabase" deployments.

#### Scenario: Supabase detection from URL
- **GIVEN** `DATABASE_URL` contains `.supabase.`
- **WHEN** the database provider is initialized
- **THEN** the Supabase provider SHALL be automatically selected
- **AND** Supabase-specific engine options SHALL be applied

#### Scenario: Supabase detection from config
- **GIVEN** `SUPABASE_PROJECT_REF` environment variable is set
- **AND** `SUPABASE_DB_PASSWORD` environment variable is set
- **WHEN** the database provider is initialized
- **THEN** the Supabase provider SHALL be selected
- **AND** the connection URL SHALL be constructed from configuration

#### Scenario: Supabase URL construction
- **GIVEN** Supabase configuration includes:
  - `SUPABASE_PROJECT_REF=myproject`
  - `SUPABASE_DB_PASSWORD=secret`
  - `SUPABASE_REGION=us-east-1`
  - `SUPABASE_POOLER_MODE=transaction`
- **WHEN** the database URL is constructed
- **THEN** the URL SHALL follow the format:
  `postgresql://postgres.myproject:secret@aws-0-us-east-1.pooler.supabase.com:6543/postgres`

#### Scenario: Supabase transaction pooling configuration
- **WHEN** Supabase provider is used with transaction pooling mode
- **THEN** engine options SHALL include:
  - `pool_pre_ping=True`
  - `pool_size` limited for free tier (5 connections)
  - `pool_recycle=300` for connection refresh
  - `sslmode=require` for secure connections
  - Statement timeout to prevent hung queries

#### Scenario: Supabase session pooling configuration
- **GIVEN** `SUPABASE_POOLER_MODE=session`
- **WHEN** Supabase provider is configured
- **THEN** the connection port SHALL be 5432 (session pooler)
- **AND** prepared statements SHALL be supported

### Requirement: Provider Factory

The system SHALL provide a factory function that returns the appropriate database provider based on configuration.

#### Scenario: Explicit provider override
- **GIVEN** `DATABASE_PROVIDER` environment variable is set to `supabase`
- **WHEN** the provider factory is called
- **THEN** the Supabase provider SHALL be returned regardless of other configuration

#### Scenario: Automatic provider detection
- **GIVEN** no explicit `DATABASE_PROVIDER` is set
- **WHEN** the provider factory is called
- **THEN** the provider SHALL be detected based on:
  1. Presence of `SUPABASE_PROJECT_REF` → Supabase
  2. `DATABASE_URL` contains `.supabase.` → Supabase
  3. Otherwise → Local PostgreSQL

#### Scenario: Provider initialization failure
- **WHEN** provider configuration is invalid (e.g., missing Supabase password)
- **THEN** a clear error message SHALL be raised
- **AND** the error SHALL indicate which configuration is missing

### Requirement: Database Health Check

The system SHALL provide health check capabilities for database connectivity verification.

#### Scenario: Successful health check
- **GIVEN** the database is reachable and configured correctly
- **WHEN** a health check is performed
- **THEN** the check SHALL return success
- **AND** connection latency SHALL be measured

#### Scenario: Failed health check
- **GIVEN** the database is unreachable or misconfigured
- **WHEN** a health check is performed
- **THEN** the check SHALL return failure
- **AND** a descriptive error message SHALL be provided

### Requirement: Migration Support

The system SHALL support Alembic database migrations with all providers.

#### Scenario: Local PostgreSQL migrations
- **GIVEN** local PostgreSQL provider is configured
- **WHEN** `alembic upgrade head` is executed
- **THEN** all migrations SHALL be applied successfully

#### Scenario: Supabase migrations
- **GIVEN** Supabase provider is configured
- **AND** a direct database URL is available (not pooler)
- **WHEN** `alembic upgrade head` is executed
- **THEN** all migrations SHALL be applied successfully
- **AND** migrations SHALL work through the direct connection

#### Scenario: Migration URL configuration
- **GIVEN** Supabase pooler URL is configured as primary `DATABASE_URL`
- **AND** `SUPABASE_DIRECT_URL` is set for migrations
- **WHEN** Alembic reads the configuration
- **THEN** the direct URL SHALL be used for DDL operations

### Requirement: Backward Compatibility

The system SHALL maintain full backward compatibility with existing DATABASE_URL configurations.

#### Scenario: Existing local configuration unchanged
- **GIVEN** an existing deployment uses `DATABASE_URL=postgresql://user:pass@localhost/db`
- **WHEN** upgrading to the new provider abstraction
- **THEN** no configuration changes SHALL be required
- **AND** all functionality SHALL work identically

#### Scenario: Environment variable precedence
- **GIVEN** both `DATABASE_URL` and Supabase configuration are set
- **WHEN** the provider is determined
- **THEN** `DATABASE_PROVIDER` explicit setting takes precedence
- **THEN** Supabase configuration takes precedence over URL-only detection
