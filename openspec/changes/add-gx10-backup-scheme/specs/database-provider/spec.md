# Database Provider

## MODIFIED Requirements

### Requirement: Railway Backup Strategy

The system SHALL retain the Railway pg_cron backup configuration surface for
backward compatibility, but SHALL NOT rely on it as the operative backup
mechanism. Disaster-recovery backup and restore behavior is owned by the
`backup-and-restore` capability.

The previously specified behavior — that a compressed `pg_dump` SHALL be created
by a pg_cron job and stored in the configured MinIO bucket — is **not satisfiable
by the current implementation** and is withdrawn as a normative requirement. The
implementation cannot deliver it because the MinIO endpoint is never supplied to
the database service, the job body self-skips when that endpoint is absent, and
the MinIO client binary is not present in the database image. This requirement is
therefore narrowed to describe a configuration surface, not an operative backup.

#### Scenario: Backup settings configuration
- **GIVEN** `DATABASE_PROVIDER=railway` is set
- **WHEN** the application starts
- **THEN** the legacy backup settings SHALL remain available for backward compatibility:
  - `railway_backup_enabled` (boolean, default `true`)
  - `railway_backup_schedule` (cron expression, default `0 3 * * *`)
  - `railway_backup_retention_days` (integer, default `7`)
  - `railway_backup_bucket` (string, default `backups`)
- **AND** these settings SHALL be documented as legacy configuration superseded by the provider-neutral backup target settings

#### Scenario: Backup job execution
- **GIVEN** any database provider
- **WHEN** disaster-recovery backups are produced
- **THEN** they SHALL be produced by the host-level backup command owned by the `backup-and-restore` capability
- **AND** the database scheduler extension SHALL NOT be required to produce a backup
- **AND** no binary SHALL be required inside the database container to produce a backup

#### Scenario: Backup retention cleanup
- **GIVEN** backup artifacts older than the configured retention tiers
- **WHEN** retention is enforced
- **THEN** enforcement SHALL be performed by backup-target lifecycle rules
- **AND** no scheduled database job SHALL delete backup objects unattended

#### Scenario: Backup disabled
- **GIVEN** backup monitoring is disabled via settings
- **WHEN** the readiness endpoint is queried
- **THEN** no backup status SHALL be reported
- **AND** no backup freshness alert SHALL be emitted

#### Scenario: Backup health check
- **GIVEN** backup monitoring is enabled
- **WHEN** the readiness endpoint is queried
- **THEN** the response SHALL include a backup recency status regardless of the configured database provider
- **AND** the status SHALL be derived from the backup target manifest rather than from database scheduler run history
- **AND** the staleness threshold SHALL be the configured staleness setting
- **AND** any operator-facing message SHALL describe that configured threshold accurately rather than a derived schedule multiple

#### Scenario: Legacy MinIO settings map to the provider-neutral namespace
- **GIVEN** `railway_minio_endpoint`, `minio_root_user`, and `minio_root_password` are set
- **AND** no `backup_s3_*` field is explicitly set
- **WHEN** settings are resolved
- **THEN** the legacy values SHALL be mapped onto the provider-neutral backup target fields
- **AND** a deprecation warning SHALL be logged naming the replacement fields
