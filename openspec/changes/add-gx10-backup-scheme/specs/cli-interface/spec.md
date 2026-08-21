# CLI Interface

## ADDED Requirements

### Requirement: Backup Command Group

The CLI SHALL expose an `aca backup` command group providing scheduled-backup
execution, prerequisite verification, and backup listing, following the
established CLI output contract.

#### Scenario: Backup command group is discoverable
- **GIVEN** the CLI is installed
- **WHEN** `aca backup --help` is invoked
- **THEN** `run`, `verify`, and `list` subcommands SHALL be listed

#### Scenario: Backup commands honor the JSON output contract
- **GIVEN** the CLI is invoked in JSON mode
- **WHEN** any `aca backup` subcommand completes
- **THEN** stdout SHALL contain exactly one JSON document
- **AND** all logging and diagnostics SHALL be written to stderr

#### Scenario: Backup output never contains credentials
- **GIVEN** any `aca backup` subcommand result in either output mode
- **WHEN** the output is inspected
- **THEN** it SHALL NOT contain access keys, secret keys, or any URL embedding credentials

#### Scenario: Listing backups does not mutate the target
- **GIVEN** `aca backup list` is invoked
- **WHEN** it completes
- **THEN** it SHALL perform only read operations against the backup target

## MODIFIED Requirements

### Requirement: Restore From Cloud Command

The CLI SHALL provide `aca manage restore-from-cloud` to retrieve a backup from
the configured backup target and replay it into a target database. The command
SHALL operate against any S3-compatible backup target, SHALL NOT expose
credentials in its arguments or output, and SHALL retain its safeguards against
restoring over a live remote database.

#### Scenario: Restore works against any S3-compatible target
- **GIVEN** the backup target is Cloudflare R2, AWS S3, or MinIO
- **WHEN** `aca manage restore-from-cloud` is invoked
- **THEN** the same code path SHALL be used for each
- **AND** the target SHALL be resolved from the provider-neutral backup settings

#### Scenario: Backup artifacts are discovered independently of legacy naming
- **GIVEN** backup artifacts stored under the configured prefix
- **WHEN** the command lists available backups
- **THEN** artifacts SHALL be discovered by the configured prefix and timestamp convention
- **AND** discovery SHALL NOT depend on a `railway-` filename prefix

#### Scenario: Credentials are not passed as process arguments
- **GIVEN** the command invokes an external storage client
- **WHEN** the subprocess is constructed
- **THEN** access keys and secret keys SHALL NOT appear in the process argument list

#### Scenario: Command output masks the target database credentials
- **GIVEN** the command completes successfully in JSON mode
- **WHEN** the emitted document is inspected
- **THEN** the reported target database SHALL have its credentials masked

#### Scenario: Encrypted artifacts are decrypted during restore
- **GIVEN** a backup artifact encrypted with the configured recipient
- **WHEN** the command retrieves it
- **THEN** it SHALL be decrypted using the configured identity before replay
- **AND** GIVEN no identity is available, the command SHALL abort naming the missing identity

#### Scenario: Live database safeguard resists URL variation
- **GIVEN** a requested target database URL that addresses the same database as the configured remote database URL but differs in textual form
- **WHEN** the command resolves the restore target
- **THEN** the command SHALL refuse the restore
- **AND** the refusal SHALL name the explicit opt-in flag required to override it

#### Scenario: Destructive restore safeguards are retained
- **GIVEN** a restore that will drop and recreate schema objects in the target
- **WHEN** the command runs without an explicit confirmation flag in interactive mode
- **THEN** it SHALL require confirmation before proceeding
