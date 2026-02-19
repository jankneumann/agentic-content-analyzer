# settings-management Specification

## Purpose
TBD - created by archiving change add-settings-management. Update Purpose after archive.
## Requirements
### Requirement: Settings Override Storage

The system SHALL provide a database-backed settings override system that layers user customizations on top of environment variable defaults and code defaults.

#### Scenario: Store a settings override
- **WHEN** a settings override is saved via `SettingsService.set(key, value)`
- **THEN** the value SHALL be stored in the `settings_overrides` table
- **AND** the `version` column SHALL be incremented if the key already exists
- **AND** the `updated_at` timestamp SHALL be set to the current time

#### Scenario: Retrieve a settings override
- **WHEN** a settings override is requested via `SettingsService.get(key)`
- **AND** a database override exists for that key
- **THEN** the database override value SHALL be returned

#### Scenario: Retrieve setting with no override
- **WHEN** a settings override is requested via `SettingsService.get(key)`
- **AND** no database override exists for that key
- **THEN** None SHALL be returned so the caller falls back to env-var or code default

#### Scenario: Delete a settings override
- **WHEN** a settings override is deleted via `SettingsService.delete(key)`
- **THEN** the database row for that key SHALL be removed
- **AND** subsequent requests for that key SHALL return None

#### Scenario: Delete a non-existent override
- **WHEN** a settings override is deleted via `SettingsService.delete(key)`
- **AND** no database override exists for that key
- **THEN** the operation SHALL succeed without error (idempotent)

#### Scenario: List overrides by prefix
- **WHEN** `SettingsService.list(prefix="model")` is called
- **THEN** all overrides with keys starting with `model.` SHALL be returned
- **AND** each entry SHALL include key, value, version, and updated_at

#### Scenario: List overrides with no matches
- **WHEN** `SettingsService.list(prefix="nonexistent")` is called
- **AND** no overrides match the prefix
- **THEN** an empty list SHALL be returned

### Requirement: Settings Override Database Schema

The `settings_overrides` table SHALL store user customizations with versioning support.

#### Scenario: Schema columns
- **GIVEN** the `settings_overrides` table
- **THEN** it SHALL have columns: `id` (PK), `key` (unique indexed varchar), `value` (text), `version` (integer default 1), `description` (text nullable), `created_at` (timestamp), `updated_at` (timestamp)

#### Scenario: Version auto-increments on update
- **WHEN** an existing settings override is updated
- **THEN** the `version` column SHALL be incremented by 1

### Requirement: Settings Override API

The system SHALL provide REST API endpoints for managing settings overrides under `/api/v1/settings/overrides`, protected by admin API key.

#### Scenario: List overrides
- **WHEN** `GET /api/v1/settings/overrides` is called with an optional `prefix` query parameter
- **THEN** matching overrides SHALL be returned with key, value, version, and updated_at
- **AND** the request SHALL require a valid `X-Admin-Key` header

#### Scenario: Get single override
- **WHEN** `GET /api/v1/settings/overrides/{key}` is called
- **THEN** the override details SHALL be returned if it exists
- **AND** 404 SHALL be returned if no override exists for that key

#### Scenario: Set override
- **WHEN** `PUT /api/v1/settings/overrides/{key}` is called with a value
- **THEN** the override SHALL be created or updated in the database
- **AND** the response SHALL confirm the new value and version

#### Scenario: Delete override
- **WHEN** `DELETE /api/v1/settings/overrides/{key}` is called
- **THEN** the override SHALL be removed
- **AND** the response SHALL confirm deletion

#### Scenario: Authentication required for all override endpoints
- **WHEN** any settings override endpoint is called without a valid `X-Admin-Key` header
- **THEN** the response SHALL be 401 Unauthorized

#### Scenario: Reject invalid key format
- **WHEN** `PUT /api/v1/settings/overrides/{key}` is called with a key that does not match the `namespace.name` pattern
- **THEN** the response SHALL be 400 Bad Request with a descriptive error message

### Requirement: Model Configuration API

The system SHALL provide an endpoint to list available models and current selection per pipeline step, protected by admin API key.

#### Scenario: List available models and current selections
- **WHEN** `GET /api/v1/settings/models` is called with a valid `X-Admin-Key` header
- **THEN** the response SHALL include a list of all models from `model_registry.yaml` with id, name, family, and capabilities
- **AND** the response SHALL include the current effective model for each pipeline step
- **AND** each step SHALL indicate whether the current model comes from an env var, DB override, or YAML default

#### Scenario: Model selection precedence
- **WHEN** determining the effective model for a pipeline step
- **THEN** the system SHALL use this precedence: environment variable > database override > YAML default
- **AND** env-var-sourced selections SHALL be marked as non-editable in the UI

#### Scenario: Authentication required for models endpoint
- **WHEN** `GET /api/v1/settings/models` is called without a valid `X-Admin-Key` header
- **THEN** the response SHALL be 401 Unauthorized

### Requirement: Model Selection Override

The system SHALL allow users to override the LLM model used for each pipeline step via the settings UI.

#### Scenario: Override model for a pipeline step
- **WHEN** a user selects a different model for a pipeline step and saves
- **THEN** the override SHALL be stored with key `model.<step_name>`
- **AND** subsequent pipeline runs SHALL use the overridden model

#### Scenario: Reset model to default
- **WHEN** a user resets a pipeline step to its default model
- **THEN** the database override SHALL be removed
- **AND** the YAML default SHALL be used for subsequent runs

#### Scenario: Validate model selection
- **WHEN** a model override is saved with a model ID present in `model_registry.yaml`
- **THEN** the override SHALL be accepted and stored

#### Scenario: Reject invalid model ID
- **WHEN** a model override is saved with a model ID NOT present in `model_registry.yaml`
- **THEN** the system SHALL return a 400 error
- **AND** the response SHALL include the list of valid model IDs

### Requirement: Voice Configuration API

The system SHALL provide an endpoint to read and update voice/TTS configuration, protected by admin API key.

#### Scenario: Get current voice configuration
- **WHEN** `GET /api/v1/settings/voice` is called with a valid `X-Admin-Key` header
- **THEN** the response SHALL include: provider (openai/elevenlabs), default_voice, speed, and available presets
- **AND** each field SHALL indicate its source (env var, DB override, or code default)

#### Scenario: Update voice setting
- **WHEN** a voice setting is updated via the settings override API with key `voice.<field>`
- **THEN** the override SHALL be persisted
- **AND** subsequent audio digest generation SHALL use the new value

#### Scenario: Validate voice speed range
- **WHEN** a voice speed override is saved with a value within 0.5–2.0
- **THEN** the override SHALL be accepted

#### Scenario: Reject voice speed out of range
- **WHEN** a voice speed override is saved with a value outside 0.5–2.0
- **THEN** the system SHALL return a 400 error with the valid range (0.5–2.0)

#### Scenario: Validate voice provider
- **WHEN** a voice provider override is saved with "openai" or "elevenlabs"
- **THEN** the override SHALL be accepted

#### Scenario: Reject unknown voice provider
- **WHEN** a voice provider override is saved with any value other than "openai" or "elevenlabs"
- **THEN** the system SHALL return a 400 error listing the valid providers

#### Scenario: Authentication required for voice endpoint
- **WHEN** `GET /api/v1/settings/voice` is called without a valid `X-Admin-Key` header
- **THEN** the response SHALL be 401 Unauthorized

### Requirement: Connection Status API

The system SHALL provide an endpoint to check the health of all configured backend services.

#### Scenario: Check all connections
- **WHEN** `GET /api/v1/settings/connections` is called with a valid `X-Admin-Key` header
- **THEN** the response SHALL include health status for each configured service
- **AND** each service SHALL report one of: `ok`, `degraded`, `unavailable`, or `not_configured`
- **AND** `not_configured` SHALL be used when the service has no credentials or URI configured

#### Scenario: Authentication required for connections endpoint
- **WHEN** `GET /api/v1/settings/connections` is called without a valid `X-Admin-Key` header
- **THEN** the response SHALL be 401 Unauthorized

#### Scenario: PostgreSQL connection check
- **WHEN** the connection status is requested
- **THEN** the PostgreSQL check SHALL execute a simple query (e.g., `SELECT 1`)
- **AND** report `ok` if successful within the timeout, `unavailable` otherwise

#### Scenario: Neo4j connection check
- **WHEN** the connection status is requested
- **AND** Neo4j is configured (provider is not "noop")
- **THEN** the Neo4j check SHALL verify bolt connectivity
- **AND** report `ok` if reachable, `unavailable` if unreachable

#### Scenario: Neo4j not configured
- **WHEN** the connection status is requested
- **AND** Neo4j provider is "noop"
- **THEN** the Neo4j service SHALL report `not_configured`

#### Scenario: LLM provider connection check
- **WHEN** the connection status is requested
- **THEN** each configured LLM provider (Anthropic, OpenAI, Google AI) SHALL be checked
- **AND** the check SHALL verify the API key is valid (e.g., list models)
- **AND** report `ok` if the API key is valid, `unavailable` if invalid or unreachable

#### Scenario: LLM provider not configured
- **WHEN** the connection status is requested
- **AND** an LLM provider has no API key set
- **THEN** that provider SHALL report `not_configured`

#### Scenario: TTS provider connection check
- **WHEN** the connection status is requested
- **AND** a TTS provider (OpenAI or ElevenLabs) has an API key configured
- **THEN** the TTS provider SHALL be checked for reachability
- **AND** report `ok` if reachable, `unavailable` if unreachable

#### Scenario: TTS provider not configured
- **WHEN** the connection status is requested
- **AND** no TTS provider API key is configured
- **THEN** the TTS service SHALL report `not_configured`

#### Scenario: Embedding provider connection check
- **WHEN** the connection status is requested
- **AND** an embedding provider is configured
- **THEN** the embedding provider SHALL be checked for reachability
- **AND** report `ok` if reachable, `unavailable` if unreachable

#### Scenario: Connection check timeout
- **WHEN** a connection check exceeds `health_check_timeout_seconds` (default 5s)
- **THEN** the check SHALL be marked as `unavailable`
- **AND** other checks SHALL continue independently (partial failure isolation)

#### Scenario: Partial connection failure
- **WHEN** one or more connection checks fail
- **THEN** the endpoint SHALL still return 200 with the full status report
- **AND** only the failing services SHALL show `unavailable`
- **AND** healthy services SHALL still show `ok`

### Requirement: Settings CLI Commands

The system SHALL provide CLI commands for managing settings overrides.

#### Scenario: List all overrides
- **WHEN** `aca settings list` is executed
- **THEN** all settings overrides SHALL be listed with key, value, and version

#### Scenario: List overrides by prefix
- **WHEN** `aca settings list --prefix model` is executed
- **THEN** only overrides with keys starting with `model.` SHALL be listed

#### Scenario: Get a setting
- **WHEN** `aca settings get <key>` is executed
- **THEN** the override value SHALL be displayed if it exists
- **AND** a "not set" message SHALL be displayed if no override exists

#### Scenario: Set a setting
- **WHEN** `aca settings set <key> <value>` is executed
- **THEN** the override SHALL be created or updated in the database

#### Scenario: Reset a setting
- **WHEN** `aca settings reset <key>` is executed
- **THEN** the override SHALL be removed from the database

### Requirement: Model Configuration UI

The Settings page SHALL include a Model Configuration section with dropdown selectors for each pipeline step.

#### Scenario: Display model selectors
- **WHEN** the Settings page is loaded
- **THEN** the Model Configuration section SHALL display a dropdown for each pipeline step
- **AND** each dropdown SHALL show the current effective model
- **AND** available options SHALL be populated from the model registry

#### Scenario: Show model metadata
- **WHEN** a model is displayed in a dropdown
- **THEN** it SHALL show the model name and family (Claude, Gemini, GPT)
- **AND** indicate vision/video support where applicable

#### Scenario: Save model selection
- **WHEN** a user selects a different model and confirms
- **THEN** the override SHALL be saved via the settings API
- **AND** a success toast SHALL be displayed

#### Scenario: Indicate non-editable steps
- **WHEN** a pipeline step's model is set via environment variable
- **THEN** the dropdown SHALL be disabled
- **AND** a tooltip SHALL explain that the value is controlled by an environment variable

#### Scenario: Display error on save failure
- **WHEN** saving a model override fails (network error or server error)
- **THEN** an error toast SHALL be displayed with the failure reason

### Requirement: Voice Configuration UI

The Settings page SHALL include a Voice Configuration section for TTS settings.

#### Scenario: Display voice settings
- **WHEN** the Settings page is loaded
- **THEN** the Voice Configuration section SHALL display: provider selector, voice/preset picker, and speed slider

#### Scenario: Provider selection
- **WHEN** a user selects a TTS provider
- **THEN** the voice/preset options SHALL update to show provider-specific choices

#### Scenario: Speed slider
- **WHEN** a user adjusts the speed slider
- **THEN** the slider SHALL display the current value (0.5–2.0)
- **AND** saving SHALL persist the value via the settings override API

#### Scenario: Save voice configuration
- **WHEN** a user changes any voice setting and saves
- **THEN** the override SHALL be saved via the settings API
- **AND** a success toast SHALL be displayed

#### Scenario: Display error on save failure
- **WHEN** saving a voice setting fails (network error or server error)
- **THEN** an error toast SHALL be displayed with the failure reason

### Requirement: Connection Status Dashboard

The Settings page SHALL include a Connection Status section showing backend health.

#### Scenario: Display connection cards
- **WHEN** the Settings page is loaded
- **THEN** the Connection Status section SHALL display a card for each configured service
- **AND** each card SHALL show the service name and status indicator (green/yellow/red/gray)
- **AND** gray SHALL indicate `not_configured` status

#### Scenario: Auto-refresh
- **WHEN** the connection dashboard is visible
- **THEN** it SHALL poll the connections endpoint every 30 seconds
- **AND** update status indicators without full page reload

#### Scenario: Manual refresh
- **WHEN** a user clicks the refresh button
- **THEN** all connection checks SHALL be re-executed immediately
- **AND** a loading indicator SHALL be shown during the check
