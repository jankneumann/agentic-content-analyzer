# backup-and-restore Specification

## Purpose
TBD - created by archiving change add-gx10-backup-scheme. Update Purpose after archive.
## Requirements
### Requirement: Provider-Neutral Backup Configuration

The system SHALL resolve all backup configuration — destination, encryption, and
monitoring — from provider-neutral setting namespaces declared in a single
settings surface, such that no backup, restore, health, or alerting code path
depends on a Railway-specific or MinIO-specific setting name. The destination
namespace SHALL work unchanged against Cloudflare R2, AWS S3, and any
S3-compatible endpoint, and SHALL be read by both the backup and restore paths.

#### Scenario: Backup target settings are available
- **GIVEN** a profile declaring `backup_s3_endpoint`, `backup_s3_bucket`, `backup_s3_region`, `backup_s3_access_key_id`, and `backup_s3_secret_access_key`
- **WHEN** settings are resolved
- **THEN** each value SHALL be exposed on `Settings`
- **AND** `backup_s3_access_key_id` and `backup_s3_secret_access_key` SHALL be typed as `SecretStr`
- **AND** `backup_s3_prefix` SHALL default to `aca` when not supplied

#### Scenario: Cloudflare R2 endpoint requires no protocol change
- **GIVEN** `backup_s3_endpoint` is set to an `https://<account>.r2.cloudflarestorage.com` URL
- **AND** `backup_s3_region` is set to `auto`
- **WHEN** the backup or restore path builds its storage invocation
- **THEN** the same code path SHALL be used as for AWS S3
- **AND** no R2-specific branch SHALL be required

#### Scenario: Deprecated MinIO settings still resolve
- **GIVEN** a configuration setting only `railway_minio_endpoint`, `minio_root_user`, `minio_root_password`, and `railway_backup_bucket`
- **AND** no `backup_s3_*` field is explicitly set
- **WHEN** settings are resolved
- **THEN** the deprecated values SHALL be mapped onto the corresponding `backup_s3_*` fields
- **AND** exactly one deprecation warning SHALL be logged naming the replacement fields

#### Scenario: New settings win over deprecated ones
- **GIVEN** both `backup_s3_endpoint` and `railway_minio_endpoint` are explicitly set to different values
- **WHEN** settings are resolved
- **THEN** `backup_s3_endpoint` SHALL retain its explicitly-set value
- **AND** the deprecated value SHALL NOT overwrite it

#### Scenario: Backup credentials are masked in diagnostics
- **GIVEN** `backup_s3_access_key_id` and `backup_s3_secret_access_key` are set
- **WHEN** any settings dump, log line, or CLI diagnostic renders them
- **THEN** both values SHALL be masked
- **AND** the masking rule SHALL match identifier-suffixed names such as `*_ACCESS_KEY_ID`

#### Scenario: Encryption settings are declared in the same surface
- **GIVEN** a configuration declaring `backup_age_recipient` and `backup_age_identity_path`
- **WHEN** settings are resolved
- **THEN** both values SHALL be exposed on `Settings`
- **AND** `backup_age_recipient` SHALL be required by the backup path and SHALL NOT be required by the restore or verification paths
- **AND** `backup_age_identity_path` SHALL be required by the restore and verification paths and SHALL NOT be required by the backup path

#### Scenario: Monitoring settings are provider-neutral
- **GIVEN** a configuration declaring `backup_monitoring_enabled` and `backup_staleness_hours`
- **WHEN** settings are resolved
- **THEN** both values SHALL be exposed on `Settings`
- **AND** `backup_staleness_hours` SHALL default to the same value as the legacy staleness setting it replaces
- **AND** no freshness, alerting, or readiness code path SHALL read a setting whose name is prefixed `railway_`

#### Scenario: Legacy monitoring settings map forward
- **GIVEN** a configuration setting only `railway_backup_enabled` and `railway_backup_staleness_hours`
- **AND** neither `backup_monitoring_enabled` nor `backup_staleness_hours` is explicitly set
- **WHEN** settings are resolved
- **THEN** the legacy values SHALL be mapped onto the provider-neutral monitoring fields
- **AND** the mapping SHALL be performed by the same validator that maps the deprecated target settings

### Requirement: Multi-Store Scheduled Backup

The system SHALL provide an `aca backup run` command that captures every
durable data store to the configured backup target in a single invocation, and
SHALL report per-store outcomes rather than a single aggregate status.

#### Scenario: PostgreSQL is captured as a portable dump
- **GIVEN** a reachable PostgreSQL database
- **WHEN** `aca backup run` executes
- **THEN** a `pg_dump` in custom format SHALL be produced
- **AND** the resulting artifact SHALL be uploaded under the configured prefix
- **AND** the artifact key SHALL embed an ISO-8601 UTC timestamp

#### Scenario: Artifacts are written under a retention tier decided at write time
- **GIVEN** a backup run producing artifacts
- **WHEN** each artifact key is constructed
- **THEN** it SHALL include a tier segment identifying daily, weekly, or monthly retention
- **AND** the tier SHALL be derived from the run date by a documented promotion rule
- **AND** the tier SHALL be recorded in the manifest

#### Scenario: Graph database is captured per configured provider and mode
- **GIVEN** `graphdb_provider` is `neo4j` and `graphdb_mode` is `local` or `embedded`
- **WHEN** `aca backup run` executes
- **THEN** a Neo4j database dump SHALL be produced and uploaded
- **AND** GIVEN the deployment requires the database to be stopped to dump it, the run SHALL either coordinate that stop or record the store as failed with a named reason, and SHALL NOT produce a silently incomplete dump

#### Scenario: Managed graph database without filesystem access is skipped explicitly
- **GIVEN** `graphdb_provider` is `neo4j` and `graphdb_mode` is `cloud`
- **WHEN** `aca backup run` executes
- **THEN** the store SHALL be recorded as skipped with a named reason identifying the managed-provider limitation
- **AND** the run SHALL NOT report the graph database as captured
- **AND** the runbook SHALL name the provider-native snapshot procedure that covers this configuration instead

#### Scenario: FalkorDB snapshot is a declared write exception
- **GIVEN** `graphdb_provider` is `falkordb`
- **WHEN** `aca backup run` executes
- **THEN** an RDB snapshot SHALL be produced and uploaded
- **AND** the snapshot command SHALL be the single declared exception to the read-only requirement
- **AND** it SHALL NOT modify any application data

#### Scenario: Artifact directories are captured wholesale
- **GIVEN** local artifact directories for the `images`, `podcasts`, and `audio-digests` buckets
- **WHEN** `aca backup run` executes
- **THEN** the directory contents SHALL be synchronized to the backup target
- **AND** files present on disk but unreferenced by any database row SHALL be included

#### Scenario: OpenBao is captured when configured
- **GIVEN** OpenBao is configured and reachable
- **WHEN** `aca backup run` executes
- **THEN** a raft snapshot SHALL be produced and uploaded
- **AND** GIVEN OpenBao is not configured, the store SHALL be reported as skipped rather than failed

#### Scenario: A failing store does not silently pass
- **GIVEN** one configured store fails to produce an artifact
- **WHEN** `aca backup run` completes
- **THEN** that store SHALL be recorded with a failed outcome
- **AND** the command SHALL exit non-zero
- **AND** stores that succeeded SHALL still be recorded as succeeded

#### Scenario: Backup makes no destructive production mutations
- **GIVEN** any invocation of `aca backup run`
- **WHEN** the command executes
- **THEN** it SHALL NOT create, modify, or delete any application data in any source store
- **AND** the only permitted state-changing operation SHALL be a provider snapshot command that writes no application data, declared explicitly per store
- **AND** it SHALL NOT delete any object from the backup target

#### Scenario: Every pipeline stage's exit status is checked
- **GIVEN** a store artifact produced by a multi-stage pipeline of dump, encrypt, and upload
- **WHEN** any stage exits non-zero
- **THEN** the store SHALL be recorded as failed
- **AND** the run SHALL NOT record that store as succeeded on the basis of the final stage's exit status alone
- **AND** the manifest SHALL NOT be written as though the run succeeded

#### Scenario: Uploaded artifact size is verified against bytes streamed
- **GIVEN** a store artifact that uploaded without error
- **WHEN** the run records its outcome
- **THEN** the stored object's size SHALL be read back from the backup target
- **AND** it SHALL be compared against the byte count streamed
- **AND** a mismatch SHALL mark the store failed

#### Scenario: An artifact directory that does not exist is excluded, not failed
- **GIVEN** a configured artifact directory that is not present on the host
- **WHEN** the artifacts store is planned
- **THEN** that directory SHALL be excluded from the capture
- **AND** the store SHALL NOT be marked failed because of its absence
- **AND** a configured directory that is present but empty SHALL still be captured
- **AND** when no configured directory is present the store SHALL record a named skip

#### Scenario: Credentials are not passed as process arguments
- **GIVEN** the run invokes any external tool for dumping, encrypting, uploading, or reading secrets
- **WHEN** each subprocess is constructed
- **THEN** access keys, secret keys, database passwords, and tokens SHALL NOT appear in its argument list
- **AND** they SHALL be supplied through the process environment or a credentials file instead

#### Scenario: Scheduled run preflights its binaries before touching any store
- **GIVEN** a required external binary is absent
- **WHEN** `aca backup run` executes
- **THEN** it SHALL abort with an error naming each missing binary
- **AND** it SHALL do so before contacting any source data store or the backup target

### Requirement: Client-Side Backup Encryption

The system SHALL encrypt every backup artifact with `age` before upload, such
that the backup target never receives plaintext.

#### Scenario: Artifacts are encrypted before leaving the host
- **GIVEN** `backup_age_recipient` is configured
- **WHEN** any store artifact is produced
- **THEN** it SHALL be piped through `age` encryption before upload
- **AND** the uploaded object SHALL carry an encrypted-artifact suffix

#### Scenario: Missing recipient key aborts before any upload
- **GIVEN** `backup_age_recipient` is not configured
- **WHEN** `aca backup run` executes
- **THEN** the command SHALL abort with a non-zero exit
- **AND** no artifact SHALL be uploaded
- **AND** the error SHALL name the missing setting

#### Scenario: Decryption capability is verified, not assumed
- **GIVEN** an identity key is available to `aca backup verify`
- **WHEN** the verify command runs
- **THEN** it SHALL decrypt a canary object using that identity
- **AND** GIVEN decryption fails, the command SHALL report a failed verification

#### Scenario: The canary is produced by the backup run, not placed by hand
- **GIVEN** a successful backup run
- **WHEN** the run completes
- **THEN** it SHALL write a canary object encrypted to the configured recipient through the same encryption path used for store artifacts
- **AND** GIVEN no canary object exists, `aca backup verify` SHALL report an absent-canary result distinguishable from a decryption failure

### Requirement: Backup Run Manifest

Each successful backup run SHALL write a manifest object to the backup target
describing that run, and the manifest SHALL be the authoritative record of
backup freshness.

#### Scenario: Manifest records the run
- **GIVEN** a backup run completes
- **WHEN** the manifest is written
- **THEN** it SHALL record the environment that produced it
- **AND** it SHALL record the run completion timestamp in UTC
- **AND** it SHALL record per-store outcome, artifact key, byte size, and checksum
- **AND** it SHALL be written to a stable, well-known key under the configured prefix

#### Scenario: The manifest key is environment-scoped
- **GIVEN** two environments configured against the same backup target
- **WHEN** each writes its manifest
- **THEN** the manifest key SHALL include a segment identifying the writing environment
- **AND** neither environment's manifest SHALL overwrite the other's
- **AND** the environment recorded inside the manifest SHALL match the segment in its key

#### Scenario: Manifest contains no credentials
- **GIVEN** a written manifest
- **WHEN** its contents are inspected
- **THEN** it SHALL NOT contain access keys, secret keys, or any URL embedding credentials

#### Scenario: Manifest is readable without the decryption identity
- **GIVEN** a written manifest
- **WHEN** a freshness reader retrieves it
- **THEN** it SHALL be readable without possession of the decryption identity
- **AND** it SHALL be the only object written to the backup target that is not encrypted

#### Scenario: Manifest is not written for a failed run
- **GIVEN** a backup run in which a required store failed
- **WHEN** the run terminates
- **THEN** the previous manifest SHALL NOT be overwritten with a failed run's timestamp

### Requirement: Backup Freshness Monitoring

The system SHALL determine backup freshness from the backup target's manifest
rather than from database-local scheduler history, SHALL apply this check
independently of the configured database provider, and SHALL NOT allow backup
staleness to affect service readiness.

#### Scenario: Freshness is derived from the manifest
- **GIVEN** a manifest exists at the well-known key
- **WHEN** the readiness endpoint is queried
- **THEN** the reported backup status SHALL be derived from the manifest's completion timestamp and its recorded outcomes
- **AND** the status SHALL be `ok` only when the age is within the configured staleness threshold AND every required store succeeded
- **AND** the status SHALL be `stale` when the age exceeds the threshold

#### Scenario: A fresh but partial run does not report healthy
- **GIVEN** a manifest whose age is within the staleness threshold
- **AND** whose overall outcome is partial, or in which any required store failed
- **WHEN** the readiness endpoint is queried
- **THEN** the reported status SHALL distinguish the partial run from a healthy one
- **AND** it SHALL NOT be reported as `ok`

#### Scenario: A manifest from another environment is rejected
- **GIVEN** a manifest whose recorded environment differs from the reading process's environment
- **WHEN** freshness is evaluated
- **THEN** the manifest SHALL NOT be treated as evidence of a backup for this environment
- **AND** the reported status SHALL identify the environment mismatch

#### Scenario: Freshness check is provider-independent
- **GIVEN** `database_provider` is any value other than `railway`
- **AND** backup monitoring is enabled
- **WHEN** the readiness endpoint is queried
- **THEN** the backup status SHALL still be evaluated and reported

#### Scenario: Absent manifest is distinguishable from an error
- **GIVEN** no manifest exists at the well-known key
- **WHEN** the readiness endpoint is queried
- **THEN** the reported status SHALL be `no_history`
- **AND** GIVEN the backup target is unreachable, the reported status SHALL be `unknown`

#### Scenario: Stale backup does not affect readiness
- **GIVEN** the backup status is `stale`
- **WHEN** the readiness endpoint is queried
- **THEN** the response status code SHALL remain unchanged by the backup status
- **AND** overall readiness SHALL NOT be reported as not-ready on account of backup staleness

#### Scenario: Freshness check survives a broken database layer
- **GIVEN** the database health check raises before the backup check executes
- **WHEN** the readiness endpoint is queried
- **THEN** the backup status SHALL still be evaluated
- **AND** the response SHALL NOT fail due to an unbound local variable

#### Scenario: Freshness reader holds no decryption identity
- **GIVEN** the process evaluating backup freshness
- **WHEN** it reads the manifest
- **THEN** it SHALL require only read access to the manifest key
- **AND** it SHALL NOT require, load, or reference the decryption identity
- **AND** it SHALL NOT require write or delete access to the backup target

#### Scenario: Freshness check is bounded and non-blocking
- **GIVEN** the backup target is slow to respond
- **WHEN** the readiness endpoint is queried
- **THEN** the backup check SHALL be time-bounded by the configured health-check timeout
- **AND** it SHALL NOT block the event loop
- **AND** repeated probes within a short interval SHALL be served without issuing a network read per probe
- **AND** a backup-target read failure SHALL be reported as a status value rather than raised

### Requirement: Durable Backup Freshness Alerting

The system SHALL emit backup freshness alerts over the durable out-of-band alert
path, SHALL emit them from periodic worker maintenance rather than from the
readiness endpoint, and SHALL NOT emit duplicate alerts for one check window.

#### Scenario: Stale backup raises a durable alert
- **GIVEN** the backup manifest is older than the staleness threshold
- **WHEN** periodic worker maintenance evaluates backup freshness
- **THEN** an alert envelope SHALL be enqueued on the durable delivery path
- **AND** its diagnostic code SHALL identify the backup staleness condition

#### Scenario: System-check alerts carry no operation identity
- **GIVEN** a backup freshness alert envelope
- **WHEN** it is constructed
- **THEN** its source kind SHALL identify a system check
- **AND** operation-scoped fields SHALL be omitted rather than populated with synthesized values
- **AND** fetching its diagnostic URL SHALL return a diagnostic projection for that event
- **AND** emitting it SHALL produce telemetry rather than being silently dropped

#### Scenario: A backup that recovered before classification raises no alert
- **GIVEN** a pending backup freshness event whose condition no longer holds when it is classified
- **WHEN** the event is classified
- **THEN** no alert envelope SHALL be enqueued for delivery
- **AND** no alert SHALL be delivered carrying an empty diagnostic-code list

#### Scenario: Readiness polling does not multiply alerts
- **GIVEN** the readiness endpoint is polled repeatedly while a backup is stale
- **WHEN** each poll is served
- **THEN** no alert SHALL be emitted by the readiness path
- **AND** at most one alert SHALL be emitted per check window by worker maintenance

#### Scenario: Alerts never carry credentials
- **GIVEN** any emitted backup alert envelope
- **WHEN** its payload is inspected
- **THEN** it SHALL NOT contain access keys, secret keys, bucket credentials, or database URLs

### Requirement: Provider-Side Backup Retention

Backup retention SHALL be enforced by backup-target lifecycle rules declared as
committed configuration, and no scheduled process SHALL delete backup objects
unattended.

#### Scenario: Tiered retention is declared as configuration
- **GIVEN** the committed retention configuration
- **WHEN** it is read
- **THEN** it SHALL declare 7 daily, 4 weekly, and 12 monthly retention tiers
- **AND** it SHALL be expressible for both Cloudflare R2 and AWS S3

#### Scenario: Applying retention is dry-run by default
- **GIVEN** the retention applier is invoked without an explicit apply flag
- **WHEN** it runs
- **THEN** it SHALL report the lifecycle rules it would set
- **AND** it SHALL NOT modify the backup target

#### Scenario: No unattended deletion path exists
- **GIVEN** the scheduled backup unit
- **WHEN** it executes
- **THEN** it SHALL NOT invoke any object-deletion operation against the backup target

### Requirement: Scheduled Execution On The Host

The system SHALL provide host-level scheduling units that invoke the backup
command, and scheduling SHALL NOT depend on database extensions or superuser
privileges.

#### Scenario: Scheduling units are provided
- **GIVEN** the gx-10 deployment assets
- **WHEN** they are inspected
- **THEN** a service unit invoking the backup command SHALL be present
- **AND** a timer unit declaring the schedule SHALL be present

#### Scenario: Scheduling requires no database privileges
- **GIVEN** the scheduled backup path
- **WHEN** it executes
- **THEN** it SHALL NOT require a database scheduler extension
- **AND** it SHALL NOT require database superuser privileges
- **AND** it SHALL NOT require any binary to be installed inside the database container

#### Scenario: Preflight names missing prerequisites
- **GIVEN** a required host binary is absent
- **WHEN** `aca backup verify` runs
- **THEN** it SHALL report each missing binary by name
- **AND** it SHALL exit non-zero without attempting a backup

### Requirement: Multi-Store Restore

The system SHALL document and support restoring every backed-up store from the
backup target, and restore procedures SHALL preserve existing safeguards against
overwriting live databases.

#### Scenario: Restore is possible for each backed-up store
- **GIVEN** a backup run that captured PostgreSQL, the graph database, artifacts, and secrets
- **WHEN** the restore runbook is followed
- **THEN** it SHALL provide an ordered procedure for each captured store
- **AND** it SHALL begin with recovery of the decryption identity

#### Scenario: Verification decrypts a real encrypted canary
- **GIVEN** a canary object produced by the real encryption tool
- **WHEN** `aca backup verify` reads it back and decrypts it with the configured identity
- **THEN** it SHALL report the canary as decrypted
- **AND** it SHALL do so without decoding the ciphertext as text
- **AND** a canary encrypted to a different key SHALL be reported as undecryptable rather than raising

#### Scenario: Restore passes no database password as a process argument
- **GIVEN** a restore into a target database whose URL embeds a password
- **WHEN** the restore tool is invoked
- **THEN** the password SHALL NOT appear in any subprocess argument list
- **AND** it SHALL be supplied through the process environment instead

#### Scenario: Round-trip restore is verified by test
- **GIVEN** a containerized S3-compatible backup target
- **WHEN** a backup is produced and then restored into a scratch database
- **THEN** the restored data SHALL match the source data
- **AND** the verification SHALL execute without contacting any production system

