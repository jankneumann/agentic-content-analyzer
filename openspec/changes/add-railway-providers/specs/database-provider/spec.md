## ADDED Requirements

### Requirement: Railway PostgreSQL Provider

The system SHALL support Railway as a PostgreSQL provider using a custom Docker image with pre-installed extensions (pgvector, pg_search, pgmq, pg_cron).

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

#### Scenario: Railway extension support flags
- **WHEN** Railway provider is used with the custom PostgreSQL image
- **THEN** `supports_pg_cron()` SHALL return `True` by default
- **AND** extension flags (`railway_pg_cron_enabled`, `railway_pgvector_enabled`, `railway_pg_search_enabled`, `railway_pgmq_enabled`) SHALL be configurable via settings

#### Scenario: Railway queue connection
- **WHEN** `get_queue_url()` is called on the Railway provider
- **THEN** it SHALL return the same database URL (no pooler separation needed)
- **AND** `get_queue_options()` SHALL return a larger pool for worker processes

## MODIFIED Requirements

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
