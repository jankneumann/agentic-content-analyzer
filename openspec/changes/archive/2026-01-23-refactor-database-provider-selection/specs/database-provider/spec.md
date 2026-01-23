# Database Provider Capability - Explicit Selection Refactor

## ADDED Requirements

### Requirement: Explicit Provider Configuration

The system SHALL require explicit database provider selection via the `DATABASE_PROVIDER` environment variable.

#### Scenario: Provider selection from environment
- **GIVEN** `DATABASE_PROVIDER` is set to `"neon"`, `"supabase"`, or `"local"`
- **WHEN** the application starts
- **THEN** the specified provider SHALL be used without implicit detection
- **AND** provider-specific features SHALL be enabled accordingly

#### Scenario: Default to local provider
- **GIVEN** `DATABASE_PROVIDER` is not set
- **WHEN** the application starts
- **THEN** the `local` provider SHALL be used by default
- **AND** the application SHALL connect using `DATABASE_URL` directly

### Requirement: Startup Configuration Validation

The system SHALL validate that provider configuration is consistent at startup.

#### Scenario: Neon provider validation
- **GIVEN** `DATABASE_PROVIDER=neon`
- **WHEN** the application starts
- **THEN** the system SHALL verify `DATABASE_URL` contains `.neon.tech`
- **AND** if validation fails, a `ValueError` SHALL be raised with a clear message

#### Scenario: Supabase provider validation
- **GIVEN** `DATABASE_PROVIDER=supabase`
- **WHEN** the application starts
- **THEN** the system SHALL verify either:
  - `SUPABASE_PROJECT_REF` is set, OR
  - `DATABASE_URL` contains `.supabase.`
- **AND** if validation fails, a `ValueError` SHALL be raised with a clear message

#### Scenario: Local provider with cloud URL warning
- **GIVEN** `DATABASE_PROVIDER=local` (or unset)
- **AND** `DATABASE_URL` contains `.neon.tech` or `.supabase.`
- **WHEN** the application starts
- **THEN** a warning SHALL be logged suggesting the appropriate provider setting
- **AND** the application SHALL continue with local provider behavior

#### Scenario: Masked URLs in error messages
- **WHEN** a validation error occurs
- **THEN** the error message SHALL include the database URL
- **AND** the password portion of the URL SHALL be masked as `***`

### Requirement: Provider Startup Logging

The system SHALL log the active database provider configuration at startup.

#### Scenario: Log provider selection
- **WHEN** the application starts successfully
- **THEN** the active provider name SHALL be logged at INFO level
- **AND** the database host (with masked credentials) SHALL be logged
- **AND** this helps operators verify configuration

## MODIFIED Requirements

### Requirement: Provider Factory

The system SHALL determine the database provider from explicit configuration rather than implicit detection.

#### Scenario: Automatic provider detection (MODIFIED)
> **Change**: Detection now reads from `DATABASE_PROVIDER` instead of cascading env var checks.

- **WHEN** the provider factory is called
- **THEN** the provider SHALL be determined by `settings.database_provider`
- **AND** implicit detection from `SUPABASE_PROJECT_REF` or `NEON_PROJECT_ID` SHALL NOT occur
- **AND** URL pattern detection SHALL only be used for validation warnings

## REMOVED Requirements

### Requirement: Implicit Provider Detection Chain

**Reason**: Implicit detection causes confusion when multiple providers are partially configured. The priority cascade (env vars → URL patterns → default) leads to unexpected behavior.

**Migration**: Users must add `DATABASE_PROVIDER=neon|supabase|local` to their `.env` file. The validator provides clear error messages guiding this migration.
