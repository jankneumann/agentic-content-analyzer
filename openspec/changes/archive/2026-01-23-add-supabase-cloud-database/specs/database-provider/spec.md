# Database Provider Capability

## ADDED Requirements

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

The system SHALL provide a factory function that returns the appropriate database provider.

#### Scenario: Automatic provider detection
- **GIVEN** no explicit `DATABASE_PROVIDER` is set
- **WHEN** the provider factory is called
- **THEN** the provider SHALL be detected based on configuration

#### Scenario: Provider initialization failure
- **WHEN** provider configuration is invalid
- **THEN** a clear error message SHALL be raised

### Requirement: Backward Compatibility

The system SHALL maintain full backward compatibility with existing DATABASE_URL configurations.

#### Scenario: Existing local configuration unchanged
- **GIVEN** an existing deployment uses `DATABASE_URL=postgresql://user:pass@localhost/db`
- **WHEN** upgrading to the new provider abstraction
- **THEN** no configuration changes SHALL be required
