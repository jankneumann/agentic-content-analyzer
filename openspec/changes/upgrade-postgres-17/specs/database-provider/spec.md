## MODIFIED Requirements

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
- **AND** pg_search SHALL NOT require `shared_preload_libraries` on PostgreSQL 17
- **AND** only `pg_cron` SHALL be listed in `shared_preload_libraries`
