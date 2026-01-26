## ADDED Requirements

### Requirement: Railway PostgreSQL Provider

The system SHALL support Railway PostgreSQL as a cloud-hosted database provider.

#### Scenario: Railway provider selection
- **GIVEN** `DATABASE_PROVIDER=railway` is set
- **WHEN** the database provider is initialized
- **THEN** the Railway provider SHALL be selected
- **AND** the connection URL SHALL use `RAILWAY_DATABASE_URL` or `DATABASE_URL`

#### Scenario: Railway environment variable handling
- **GIVEN** the application is deployed on Railway
- **AND** Railway has injected `DATABASE_URL` with the PostgreSQL connection string
- **WHEN** `DATABASE_PROVIDER=railway` is configured
- **THEN** the provider SHALL use the Railway-provided URL automatically

#### Scenario: Railway connection configuration
- **WHEN** Railway provider is used
- **THEN** engine options SHALL include:
  - `pool_pre_ping=True` for connection validation
  - `pool_size=5` (conservative for shared hosting)
  - `pool_recycle=300` for connection refresh
  - `sslmode=require` for SSL connections (Railway enforces SSL)

#### Scenario: Railway internal vs external connection
- **GIVEN** the application runs on Railway's private network
- **WHEN** `DATABASE_URL` contains `.railway.internal`
- **THEN** the provider SHALL use the internal URL for low-latency connections
- **AND** no external proxy overhead SHALL occur

#### Scenario: Railway pg_cron support
- **GIVEN** the custom PostgreSQL image with pg_cron is deployed
- **AND** `RAILWAY_PG_CRON_ENABLED=true` (default)
- **WHEN** `supports_pg_cron()` is called on the Railway provider
- **THEN** it SHALL return `True`
- **AND** pg_cron jobs MAY be scheduled within PostgreSQL

#### Scenario: Railway pg_cron disabled
- **GIVEN** `RAILWAY_PG_CRON_ENABLED=false`
- **WHEN** `supports_pg_cron()` is called on the Railway provider
- **THEN** it SHALL return `False`
- **AND** scheduled jobs MUST use external schedulers

### Requirement: Railway PostgreSQL Extensions

The Railway PostgreSQL custom image SHALL include extensions for feature parity with other cloud providers.

#### Scenario: pgvector extension availability
- **GIVEN** the custom PostgreSQL image is deployed on Railway
- **WHEN** the database is initialized
- **THEN** the `vector` extension SHALL be available
- **AND** vector similarity search operations SHALL work correctly

#### Scenario: pg_search extension availability
- **GIVEN** the custom PostgreSQL image is deployed on Railway
- **WHEN** the database is initialized
- **THEN** the `pg_search` extension (ParadeDB) SHALL be available
- **AND** BM25 full-text search operations SHALL work correctly

#### Scenario: pgmq extension availability
- **GIVEN** the custom PostgreSQL image is deployed on Railway
- **WHEN** the database is initialized
- **THEN** the `pgmq` extension SHALL be available
- **AND** message queue operations SHALL work correctly

#### Scenario: pg_cron extension availability
- **GIVEN** the custom PostgreSQL image is deployed on Railway
- **WHEN** the database is initialized
- **THEN** the `pg_cron` extension SHALL be available
- **AND** scheduled job operations SHALL work correctly

#### Scenario: Extension initialization on database creation
- **GIVEN** the custom PostgreSQL container starts
- **WHEN** the database is created for the first time
- **THEN** all extensions SHALL be enabled via init script:
  - `CREATE EXTENSION IF NOT EXISTS vector;`
  - `CREATE EXTENSION IF NOT EXISTS pg_search;`
  - `CREATE EXTENSION IF NOT EXISTS pgmq;`
  - `CREATE EXTENSION IF NOT EXISTS pg_cron;`

## MODIFIED Requirements

### Requirement: Provider Factory

The provider factory SHALL detect and instantiate the appropriate database provider based on configuration, with Railway added to the provider options.

> Extends the base Provider Factory requirement to include Railway in the provider list.

#### Scenario: Automatic provider detection (MODIFIED)
> **Change**: Adds Railway as a valid provider option.

- **GIVEN** `DATABASE_PROVIDER` is set to a valid provider name
- **WHEN** the provider factory is called
- **THEN** the provider SHALL be instantiated based on the value:
  - `"local"` → LocalPostgresProvider
  - `"supabase"` → SupabaseProvider
  - `"neon"` → NeonProvider
  - `"railway"` → RailwayProvider *(NEW)*

#### Scenario: Railway provider initialization validation
- **GIVEN** `DATABASE_PROVIDER=railway`
- **AND** neither `RAILWAY_DATABASE_URL` nor `DATABASE_URL` is set
- **WHEN** the provider factory is called
- **THEN** a clear error message SHALL be raised
- **AND** the error SHALL indicate that a database URL is required
