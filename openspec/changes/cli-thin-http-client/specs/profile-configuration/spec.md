## MODIFIED Capability Spec

This change modifies the existing capability spec `specs/profile-configuration/spec.md`.

## ADDED Requirements

### Requirement: API base URL setting
Profiles SHALL support an `api_base_url` setting for CLI → API communication.

#### Scenario: Default API URL
- **WHEN** no profile is active or `api_base_url` is not set
- **THEN** `Settings.api_base_url` SHALL default to `http://localhost:8000`

#### Scenario: Profile overrides API URL
- **WHEN** a profile sets `settings.api.api_base_url`
- **THEN** the CLI SHALL use that URL for all API requests

#### Scenario: Environment variable takes precedence
- **WHEN** `API_BASE_URL` environment variable is set
- **THEN** it SHALL override the profile's `api_base_url` value

### Requirement: API timeout setting
Profiles SHALL support an `api_timeout` setting for long-running CLI requests.

#### Scenario: Default timeout
- **WHEN** no `api_timeout` is configured
- **THEN** `Settings.api_timeout` SHALL default to 300 seconds

#### Scenario: Profile overrides timeout
- **WHEN** a profile sets `settings.api.api_timeout`
- **THEN** the CLI HTTP client SHALL use that timeout value
