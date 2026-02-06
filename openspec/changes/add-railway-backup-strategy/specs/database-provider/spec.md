## ADDED Requirements

### Requirement: Railway Backup Strategy

The system SHALL support automated PostgreSQL backups for the Railway provider using pg_cron scheduled jobs that write compressed dumps to MinIO storage.

#### Scenario: Backup settings configuration
- **GIVEN** `DATABASE_PROVIDER=railway` is set
- **AND** `railway_backup_enabled=true` (default)
- **WHEN** the application starts
- **THEN** backup settings SHALL be available:
  - `railway_backup_schedule` (cron expression, default `0 3 * * *`)
  - `railway_backup_retention_days` (integer, default `7`)
  - `railway_backup_bucket` (string, default `backups`)

#### Scenario: Backup job execution
- **GIVEN** pg_cron extension is enabled
- **AND** backup is enabled via settings
- **WHEN** the scheduled cron time is reached
- **THEN** a compressed `pg_dump` SHALL be created
- **AND** the dump SHALL be stored in the configured MinIO bucket

#### Scenario: Backup retention cleanup
- **GIVEN** backups exist in MinIO older than `railway_backup_retention_days`
- **WHEN** the retention cleanup job runs
- **THEN** backups older than the retention period SHALL be removed

#### Scenario: Backup disabled
- **GIVEN** `railway_backup_enabled=false`
- **WHEN** the database provider is initialized
- **THEN** no backup pg_cron jobs SHALL be created

#### Scenario: Backup health check
- **GIVEN** backup is enabled
- **WHEN** the readiness endpoint is queried
- **THEN** the response SHALL include backup recency status
- **AND** a warning SHALL be returned if the last successful backup exceeds twice the schedule interval
