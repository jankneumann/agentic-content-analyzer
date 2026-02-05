## MODIFIED Requirements

### Requirement: Profile CLI Commands

The system SHALL provide CLI commands for profile management under `aca profile`.

This modifies the existing requirement which uses `newsletter-cli profile`. The `newsletter-cli` entrypoint SHALL continue to work as a deprecated alias (see `cli-interface` spec for backward compatibility).

#### Scenario: List available profiles
- **WHEN** `aca profile list` is executed
- **THEN** all profiles in `profiles/` SHALL be listed
- **AND** each entry SHALL show: name, extends (if any), description (if any)
- **AND** the currently active profile SHALL be marked

#### Scenario: Show resolved profile
- **WHEN** `aca profile show railway` is executed
- **THEN** the fully resolved profile SHALL be displayed
- **AND** inherited values SHALL show their source
- **AND** secret values SHALL be masked

#### Scenario: Validate profile
- **WHEN** `aca profile validate railway` is executed
- **AND** the profile is valid
- **THEN** "Profile 'railway' is valid" SHALL be printed
- **AND** exit code SHALL be 0

#### Scenario: Validate invalid profile
- **WHEN** `aca profile validate broken` is executed
- **AND** the profile has validation errors
- **THEN** all errors SHALL be printed
- **AND** exit code SHALL be 1

#### Scenario: Inspect effective configuration
- **WHEN** `aca profile inspect` is executed
- **THEN** the effective Settings SHALL be displayed
- **AND** each value SHALL show its source (profile, secrets, env, default)
- **AND** secrets SHALL be masked

### Requirement: Profile Migration Tooling

The system SHALL provide a CLI command to migrate existing `.env` configurations to profile format.

#### Scenario: Migrate .env to profile
- **WHEN** `aca profile migrate --from .env --to profiles/migrated.yaml` is executed
- **THEN** a new profile file SHALL be created
- **AND** provider choices SHALL be extracted from `*_PROVIDER` variables
- **AND** non-secret settings SHALL be written to the profile
- **AND** secret values SHALL be written to `.secrets.yaml`

#### Scenario: Secret detection during migration
- **GIVEN** `.env` contains `ANTHROPIC_API_KEY=sk-ant-xxx`
- **WHEN** migration is executed
- **THEN** `ANTHROPIC_API_KEY` SHALL be written to `.secrets.yaml`
- **AND** the profile SHALL reference `${ANTHROPIC_API_KEY}`

#### Scenario: Dry run migration
- **WHEN** `aca profile migrate --dry-run` is executed
- **THEN** the would-be profile content SHALL be printed to stdout
- **AND** no files SHALL be created or modified

#### Scenario: Migration preserves comments
- **GIVEN** `.env` contains comments describing sections (lines starting with `#`)
- **WHEN** migration is executed with `--preserve-comments` flag
- **THEN** section header comments SHALL be converted to YAML comments
- **AND** inline comments on variable lines SHALL be preserved where possible
