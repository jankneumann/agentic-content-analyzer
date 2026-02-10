# local-development Specification

## Purpose
TBD - created by archiving change add-local-supabase-support. Update Purpose after archive.
## Requirements
### Requirement: Local Supabase Development Mode

The system SHALL support running against a local Supabase instance for development.

#### Scenario: Enable local Supabase mode

- **GIVEN** the environment variable `SUPABASE_LOCAL=true` is set
- **WHEN** the application starts
- **THEN** it connects to local Supabase endpoints (127.0.0.1:54321, 127.0.0.1:54322)
- **AND** logs indicate local Supabase mode is active

#### Scenario: Auto-configure local endpoints

- **GIVEN** `SUPABASE_LOCAL=true` is set
- **AND** no explicit Supabase URLs are provided
- **WHEN** settings are loaded
- **THEN** `supabase_url` defaults to `http://127.0.0.1:54321`
- **AND** `supabase_db_url` defaults to `postgresql://postgres:postgres@127.0.0.1:54322/postgres`

### Requirement: Local Supabase Storage

The system SHALL support Supabase Storage operations against a local instance.

#### Scenario: Upload file to local storage

- **GIVEN** local Supabase mode is enabled
- **WHEN** a file is uploaded via `get_storage("images").save(data, filename, content_type)`
- **THEN** the file is stored in the local Supabase Storage
- **AND** the file can be retrieved via `get_storage("images").get(path)`

#### Scenario: Create bucket locally

- **GIVEN** local Supabase mode is enabled
- **WHEN** storage is initialized with a new bucket name
- **THEN** the bucket is created in local Supabase Storage if it doesn't exist

### Requirement: Local Supabase Database

The system SHALL support database operations against a local Supabase PostgreSQL instance.

#### Scenario: Run migrations locally

- **GIVEN** local Supabase mode is enabled
- **WHEN** Alembic migrations are run
- **THEN** migrations are applied to the local Supabase PostgreSQL
- **AND** the schema matches the production schema

#### Scenario: Connect to local database

- **GIVEN** `SUPABASE_LOCAL=true` is set
- **WHEN** a database session is created
- **THEN** it connects to `127.0.0.1:54322`
- **AND** queries execute successfully

### Requirement: Docker Compose Supabase Profile

The system SHALL provide a Docker Compose profile for running local Supabase.

#### Scenario: Start local Supabase via Docker Compose

- **WHEN** `docker compose --profile supabase up` is executed
- **THEN** PostgreSQL starts on port 54322
- **AND** Supabase API starts on port 54321
- **AND** Supabase Studio starts on port 54323

#### Scenario: Persist local data

- **GIVEN** local Supabase is running
- **WHEN** data is written to the database or storage
- **AND** containers are stopped and restarted
- **THEN** the data persists across restarts

### Requirement: Environment Validation

The system SHALL validate Supabase configuration consistency.

#### Scenario: Warn on mixed configuration

- **GIVEN** `SUPABASE_LOCAL=true` is set
- **AND** `SUPABASE_URL` points to a cloud instance
- **WHEN** settings are loaded
- **THEN** a warning is logged about configuration mismatch
- **AND** local settings take precedence
