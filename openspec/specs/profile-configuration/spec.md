# profile-configuration Specification

## Purpose
TBD - created by archiving change add-profile-configuration. Update Purpose after archive.
## Requirements
### Requirement: Profile File Format

The system SHALL support YAML-based configuration profiles stored in the `profiles/` directory at the project root.

Each profile file SHALL contain:
- `name` (required): Unique identifier for the profile
- `extends` (optional): Name of parent profile to inherit from
- `description` (optional): Human-readable description
- `providers`: Section specifying provider choices
- `settings`: Section specifying provider-specific configuration

Profile values SHALL support `${VAR}` syntax for environment variable interpolation.

#### Scenario: Load profile from YAML file
- **GIVEN** a file `profiles/railway.yaml` exists with valid YAML structure
- **WHEN** the profile loader loads "railway"
- **THEN** a Profile object SHALL be returned with all fields populated
- **AND** `${VAR}` references SHALL be resolved from environment variables

#### Scenario: Environment variable interpolation
- **GIVEN** a profile contains `database_url: ${RAILWAY_DATABASE_URL}`
- **AND** `RAILWAY_DATABASE_URL` is set in the environment
- **WHEN** the profile is loaded
- **THEN** the value SHALL be replaced with the environment variable value

#### Scenario: Missing environment variable reference
- **GIVEN** a profile contains `api_key: ${MISSING_VAR}`
- **AND** `MISSING_VAR` is not set in the environment or secrets
- **WHEN** the profile is loaded
- **THEN** a `ProfileResolutionError` SHALL be raised
- **AND** the error message SHALL include the variable name and profile location

#### Scenario: Profile not found
- **GIVEN** no file exists at `profiles/nonexistent.yaml`
- **WHEN** the profile loader attempts to load "nonexistent"
- **THEN** a `ProfileNotFoundError` SHALL be raised
- **AND** the error message SHALL list available profiles

#### Scenario: Malformed YAML syntax
- **GIVEN** a profile file contains invalid YAML syntax (unclosed quotes, bad indentation)
- **WHEN** the profile loader attempts to load it
- **THEN** a `ProfileParseError` SHALL be raised
- **AND** the error message SHALL include the line number and syntax issue
- **AND** the error SHALL be distinct from validation errors

#### Scenario: Escape interpolation syntax
- **GIVEN** a profile contains `literal_var: $${NOT_INTERPOLATED}`
- **WHEN** the profile is loaded
- **THEN** the value SHALL be `${NOT_INTERPOLATED}` (literal string, not resolved)

#### Scenario: Default value in interpolation
- **GIVEN** a profile contains `optional_key: ${OPTIONAL_VAR:-default_value}`
- **AND** `OPTIONAL_VAR` is not set in the environment
- **WHEN** the profile is loaded
- **THEN** the value SHALL be `default_value`

### Requirement: Provider Selection in Profiles

The system SHALL support explicit provider selection in the `providers` section of profiles.

Supported provider categories (matching existing Settings provider types):
- `database`: "local" | "supabase" | "neon" | "railway"
- `neo4j`: "local" | "auradb"
- `storage`: "local" | "s3" | "supabase" | "railway"
- `observability`: "noop" | "opik" | "braintrust" | "otel"

Note: TTS and LLM providers are configured via API keys in the `settings` section, not as provider choices. This matches the existing Settings pattern where these are implicit based on which API keys are present.

#### Scenario: Valid provider selection
- **GIVEN** a profile with `providers.database: railway`
- **WHEN** the profile is validated
- **THEN** validation SHALL pass
- **AND** the provider choice SHALL be applied to Settings.database_provider

#### Scenario: Invalid provider value
- **GIVEN** a profile with `providers.database: invalid_provider`
- **WHEN** the profile is validated
- **THEN** a `ProfileValidationError` SHALL be raised
- **AND** the error SHALL list valid provider options

#### Scenario: Provider settings coherence
- **GIVEN** a profile with `providers.database: railway`
- **AND** no `settings.database.railway_database_url` is provided
- **WHEN** the profile is validated
- **THEN** a `ProfileValidationError` SHALL be raised
- **AND** the error SHALL indicate the missing required setting

### Requirement: Profile Inheritance

The system SHALL support single-parent inheritance via the `extends` field.

Inheritance rules:
- Scalar values: Child overrides parent
- Dictionaries: Deep merge (child keys override parent keys at each level)
- Lists: Child replaces parent entirely
- `providers` section: Child value overrides parent value per key

#### Scenario: Single-level inheritance
- **GIVEN** `profiles/base.yaml` with `providers.database: local`
- **AND** `profiles/production.yaml` with `extends: base` and `providers.database: railway`
- **WHEN** "production" profile is loaded
- **THEN** the resolved profile SHALL have `providers.database: railway`
- **AND** all other settings from base SHALL be inherited

#### Scenario: Multi-level inheritance
- **GIVEN** "grandparent" → "parent" → "child" inheritance chain
- **WHEN** "child" profile is loaded
- **THEN** settings SHALL be resolved in order: grandparent → parent → child
- **AND** most specific (child) values SHALL win

#### Scenario: Circular inheritance detection
- **GIVEN** "a" extends "b" and "b" extends "a"
- **WHEN** profile "a" is loaded
- **THEN** a `ProfileInheritanceCycleError` SHALL be raised
- **AND** the error SHALL show the cycle path

#### Scenario: Missing parent profile
- **GIVEN** a profile with `extends: nonexistent`
- **WHEN** the profile is loaded
- **THEN** a `ProfileNotFoundError` SHALL be raised for the parent
- **AND** the error SHALL indicate which profile referenced it

### Requirement: Secrets Separation

The system SHALL load secrets from `.secrets.yaml` file, which SHALL be gitignored.

Secret resolution precedence (highest to lowest):
1. Environment variables
2. `.secrets.yaml` file
3. Profile default values

#### Scenario: Load secrets from file
- **GIVEN** `.secrets.yaml` contains `ANTHROPIC_API_KEY: sk-ant-xxx`
- **AND** the profile references `${ANTHROPIC_API_KEY}`
- **WHEN** the profile is resolved
- **THEN** the secret value SHALL be substituted

#### Scenario: Environment variable overrides secrets file
- **GIVEN** `.secrets.yaml` contains `API_KEY: file-value`
- **AND** environment has `API_KEY=env-value`
- **WHEN** the profile references `${API_KEY}`
- **THEN** the resolved value SHALL be "env-value"

#### Scenario: Secrets file not found
- **GIVEN** no `.secrets.yaml` file exists
- **WHEN** secrets are loaded
- **THEN** an empty secrets dict SHALL be returned
- **AND** no error SHALL be raised (secrets from env vars still work)

#### Scenario: Secret masking in output
- **WHEN** a resolved profile is displayed or logged
- **THEN** secret values SHALL be masked as "***" or "[MASKED]"
- **AND** non-secret values SHALL be shown in full

Secrets are identified by:
1. Values loaded from `.secrets.yaml` file
2. Keys matching secret patterns: `*_KEY`, `*_SECRET`, `*_PASSWORD`, `*_TOKEN`
3. Values matching credential URL patterns (passwords in connection strings)

#### Scenario: Malformed secrets YAML
- **GIVEN** `.secrets.yaml` exists but contains invalid YAML
- **WHEN** secrets are loaded
- **THEN** a `SecretsParseError` SHALL be raised
- **AND** the error message SHALL include the line number

### Requirement: Profile Activation

The system SHALL activate profiles based on the `PROFILE` environment variable.

Activation order:
1. If `PROFILE` env var set → load `profiles/{PROFILE}.yaml`
2. If `profiles/default.yaml` exists → load it
3. Otherwise → fall back to `.env` file loading (backward compatible)

#### Scenario: Activate profile via environment variable
- **GIVEN** `PROFILE=railway` is set in the environment
- **AND** `profiles/railway.yaml` exists and is valid
- **WHEN** Settings is initialized
- **THEN** the railway profile SHALL be loaded and applied
- **AND** the log SHALL indicate "Using profile: railway"

#### Scenario: Default profile activation
- **GIVEN** `PROFILE` env var is not set
- **AND** `profiles/default.yaml` exists
- **WHEN** Settings is initialized
- **THEN** the default profile SHALL be loaded

#### Scenario: Fallback to .env file
- **GIVEN** `PROFILE` env var is not set
- **AND** `profiles/default.yaml` does not exist
- **WHEN** Settings is initialized
- **THEN** settings SHALL be loaded from `.env` file
- **AND** behavior SHALL match the current Pydantic Settings loading

#### Scenario: Profiles directory does not exist
- **GIVEN** the `profiles/` directory does not exist
- **AND** `PROFILE` env var is not set
- **WHEN** Settings is initialized
- **THEN** settings SHALL fall back to `.env` file loading
- **AND** no error SHALL be raised about missing profiles directory

#### Scenario: Profile specified but profiles directory missing
- **GIVEN** the `profiles/` directory does not exist
- **AND** `PROFILE=railway` is set
- **WHEN** Settings is initialized
- **THEN** a `ProfileNotFoundError` SHALL be raised
- **AND** the error message SHALL indicate the profiles directory is missing

#### Scenario: Profile overrides .env values
- **GIVEN** `.env` contains `DATABASE_PROVIDER=local`
- **AND** active profile has `providers.database: railway`
- **WHEN** Settings is initialized
- **THEN** `settings.database_provider` SHALL be "railway"

### Requirement: Profile Validation

The system SHALL validate profile completeness and coherence at startup.

Validation checks:
- All required fields present for selected providers
- All `${VAR}` references resolvable
- Provider combinations are compatible
- No unknown provider values

#### Scenario: Valid profile passes validation
- **GIVEN** a profile with all required settings for its providers
- **WHEN** `validate_profile()` is called
- **THEN** no errors SHALL be raised
- **AND** the function SHALL return the validated Profile

#### Scenario: Missing required setting
- **GIVEN** a profile with `providers.neo4j: auradb`
- **AND** no `settings.neo4j.auradb_uri` is provided
- **WHEN** the profile is validated
- **THEN** a `ProfileValidationError` SHALL be raised
- **AND** the error SHALL specify: "providers.neo4j=auradb requires settings.neo4j.auradb_uri"

#### Scenario: Validation error aggregation
- **GIVEN** a profile with multiple validation errors
- **WHEN** the profile is validated
- **THEN** ALL errors SHALL be collected and reported together
- **AND** the error message SHALL list each issue

### Requirement: Profile CLI Commands

The system SHALL provide CLI commands for profile management under `newsletter-cli profile`.

#### Scenario: List available profiles
- **WHEN** `newsletter-cli profile list` is executed
- **THEN** all profiles in `profiles/` SHALL be listed
- **AND** each entry SHALL show: name, extends (if any), description (if any)
- **AND** the currently active profile SHALL be marked

#### Scenario: Show resolved profile
- **WHEN** `newsletter-cli profile show railway` is executed
- **THEN** the fully resolved profile SHALL be displayed
- **AND** inherited values SHALL show their source
- **AND** secret values SHALL be masked

#### Scenario: Validate profile
- **WHEN** `newsletter-cli profile validate railway` is executed
- **AND** the profile is valid
- **THEN** "Profile 'railway' is valid" SHALL be printed
- **AND** exit code SHALL be 0

#### Scenario: Validate invalid profile
- **WHEN** `newsletter-cli profile validate broken` is executed
- **AND** the profile has validation errors
- **THEN** all errors SHALL be printed
- **AND** exit code SHALL be 1

#### Scenario: Inspect effective configuration
- **WHEN** `newsletter-cli profile inspect` is executed
- **THEN** the effective Settings SHALL be displayed
- **AND** each value SHALL show its source (profile, secrets, env, default)
- **AND** secrets SHALL be masked

### Requirement: Profile Migration Tooling

The system SHALL provide a CLI command to migrate existing `.env` configurations to profile format.

#### Scenario: Migrate .env to profile
- **WHEN** `newsletter-cli profile migrate --from .env --to profiles/migrated.yaml` is executed
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
- **WHEN** `newsletter-cli profile migrate --dry-run` is executed
- **THEN** the would-be profile content SHALL be printed to stdout
- **AND** no files SHALL be created or modified

#### Scenario: Migration preserves comments
- **GIVEN** `.env` contains comments describing sections (lines starting with `#`)
- **WHEN** migration is executed with `--preserve-comments` flag
- **THEN** section header comments SHALL be converted to YAML comments
- **AND** inline comments on variable lines SHALL be preserved where possible

### Requirement: Default Profile Templates

The system SHALL ship with default profile templates for common deployment scenarios.

Templates:
- `profiles/base.yaml`: All defaults, all providers set to "local"
- `profiles/local.yaml`: Extends base, configured for Docker Compose
- `profiles/railway.yaml`: Extends base, configured for Railway deployment
- `profiles/supabase-cloud.yaml`: Extends base, configured for Supabase cloud

#### Scenario: Base profile provides all defaults
- **WHEN** `profiles/base.yaml` is loaded without any parent
- **THEN** all provider categories SHALL have explicit values
- **AND** all required settings for "local" providers SHALL have defaults

#### Scenario: Railway profile references injected variables
- **GIVEN** `profiles/railway.yaml` template
- **THEN** it SHALL contain `settings.database.railway_database_url: ${RAILWAY_DATABASE_URL}`
- **AND** it SHALL contain `settings.storage.minio_root_user: ${MINIO_ROOT_USER}`
- **AND** it SHALL contain `settings.storage.minio_root_password: ${MINIO_ROOT_PASSWORD}`
- **AND** YAML comments SHALL explain that Railway auto-injects these variables

#### Scenario: Template profiles are valid structurally
- **WHEN** each template profile is validated for structure only (ignoring unresolved variables)
- **THEN** all required fields SHALL be present
- **AND** all provider values SHALL be valid literals
- **AND** all settings keys SHALL match expected schema

#### Scenario: Template profiles list required secrets
- **GIVEN** a template profile references `${SECRET_VAR}` without defaults
- **WHEN** the profile is validated with secrets checking enabled
- **THEN** validation SHALL list missing secrets as warnings (not errors)
- **AND** the warning SHALL indicate which secrets need to be provided
