# railway-secrets-sync Specification

## Purpose
TBD - created by archiving change add-railway-secrets-sync. Update Purpose after archive.
## Requirements
### Requirement: Allowlist-gated secret eligibility
The command SHALL only push secrets explicitly declared for the target service
in `settings/deploy/railway_secrets.yaml`.

#### Scenario: Unlisted key is never pushed
- **WHEN** a local secret key is not present in the service's mapping
- **THEN** the command SHALL NOT send that key to Railway
- **AND** it SHALL NOT appear in the dry-run diff as a pushable change

#### Scenario: Rename on push
- **WHEN** a mapping entry specifies a `railway` name different from `local`
- **THEN** the value of the local key SHALL be pushed under the `railway` name

#### Scenario: Missing local value
- **WHEN** a mapped key has no value in env or `.secrets.yaml`
- **THEN** the key SHALL be reported as `skipped (no local value)`
- **AND** SHALL NOT be pushed

### Requirement: Dry-run by default
`sync-secrets` SHALL compute and display a diff without writing, unless
`--apply` is passed.

#### Scenario: Default invocation writes nothing
- **WHEN** `aca deploy sync-secrets --service <s> --env <e>` runs without `--apply`
- **THEN** no `railway variables --set` call SHALL be made
- **AND** a redacted diff of `new` / `changed` / `unchanged` keys SHALL be shown

#### Scenario: Apply writes mapped changes
- **WHEN** the same command runs with `--apply`
- **THEN** each `new` and `changed` mapped variable SHALL be set on Railway
- **AND** `unchanged` keys SHALL be skipped
- **AND** the command SHALL report the counts of variables created and updated

### Requirement: Diff classification against live Railway variables
The command SHALL classify each mapped key by comparing the local value to the
current value on the target Railway service/environment.

#### Scenario: Classification
- **WHEN** the diff is computed
- **THEN** a key absent on Railway SHALL be `new`
- **AND** a key present with a different value SHALL be `changed`
- **AND** a key present with an identical value SHALL be `unchanged`

#### Scenario: Unmanaged remote variables are reported, not modified
- **WHEN** the target service has variables not present in the mapping
- **THEN** they SHALL be listed as `unmanaged`
- **AND** they SHALL NOT be modified or deleted

### Requirement: Secret value redaction
The command SHALL NOT print any secret value in clear text in any output mode.

#### Scenario: Human output is masked
- **WHEN** the diff is rendered to a terminal
- **THEN** each value SHALL be masked (e.g. first 3 and last 4 characters only)

#### Scenario: JSON output is masked
- **WHEN** `--json` is active
- **THEN** the payload SHALL contain only masked previews, never raw values
- **AND** the payload SHALL include `service`, `environment`, `new`, `changed`,
  `unchanged`, `unmanaged`, and `applied`

### Requirement: Additive, non-destructive behavior
The command SHALL only create or update mapped variables and SHALL never delete
Railway variables.

#### Scenario: No deletion
- **WHEN** `--apply` runs
- **THEN** no Railway variable SHALL be deleted, including `unmanaged` ones

### Requirement: Target resolution and pre-flight checks
The command SHALL resolve the Railway service/environment and fail clearly when
the environment cannot be operated on safely.

#### Scenario: Explicit target
- **WHEN** `--service` and `--env` are provided
- **THEN** they SHALL be used as the target

#### Scenario: Default target for dry-run
- **WHEN** `--service`/`--env` are omitted and `railway status --json` provides
  defaults
- **THEN** those defaults SHALL be used for a dry-run

#### Scenario: Apply requires explicit environment
- **WHEN** `--apply` is requested without an explicit `--env`
- **THEN** the command SHALL refuse and require the environment to be named

#### Scenario: Railway CLI unavailable
- **WHEN** the `railway` CLI is not installed or the project is not linked
- **THEN** the command SHALL exit with an actionable error message
- **AND** SHALL NOT emit a stack trace
