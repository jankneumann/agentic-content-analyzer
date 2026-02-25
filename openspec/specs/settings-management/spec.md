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

The system SHALL provide an endpoint to read and update voice configuration including cloud STT language and engine preference settings, protected by admin API key. Cloud STT provider/model selection is handled via the `CLOUD_STT` pipeline step in the Model Configuration dialog — not as a separate voice setting.

#### Scenario: Get current voice configuration
- **WHEN** `GET /api/v1/settings/voice` is called with a valid `X-Admin-Key` header
- **THEN** the response SHALL include cloud STT settings: `cloud_stt_language`, `engine_preference_order`
- **AND** each field SHALL indicate its source (env var, DB override, or code default)
- **AND** the response SHALL include `cloud_stt_model` as a read-only reference to the current `CLOUD_STT` pipeline step model (managed via Model Configuration)

#### Scenario: Update cloud STT language
- **WHEN** a cloud STT language override is saved via `PUT /api/v1/settings/voice/cloud_stt_language` with a valid BCP-47 language tag or `"auto"`
- **THEN** the override SHALL be persisted with key `voice.cloud_stt_language`

#### Scenario: Update engine preference order
- **WHEN** an engine preference order override is saved via `PUT /api/v1/settings/voice/engine_preference_order` with a comma-separated list (e.g., `"cloud,browser,on-device"`)
- **THEN** the override SHALL be persisted with key `voice.engine_preference_order`
- **AND** the list SHALL only contain valid engine names

#### Scenario: Default cloud STT settings
- **WHEN** no cloud STT overrides exist
- **THEN** `cloud_stt_language` SHALL default to `"auto"`
- **AND** `engine_preference_order` SHALL default to `"cloud,native,browser,on-device"`
- **AND** the `CLOUD_STT` pipeline step model SHALL default to `gemini-2.5-flash` (managed in `model_registry.yaml`)

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

The Settings page SHALL include cloud STT configuration within the Voice Configuration section. Provider/model selection appears in the Model Configuration dialog (as the `CLOUD_STT` pipeline step), while language and engine preference remain in the Voice Configuration section.

#### Scenario: Display cloud STT settings
- **WHEN** the Settings page is loaded
- **THEN** the Voice Configuration section SHALL display cloud STT language selector and engine preference order
- **AND** a link or note SHALL direct users to the Model Configuration section for cloud STT model/provider selection

#### Scenario: Cloud STT model reference
- **WHEN** the Voice Configuration section renders
- **THEN** it SHALL show the currently selected `CLOUD_STT` model as a read-only badge (e.g., "Model: gemini-2.5-flash")
- **AND** the badge SHALL link to the Model Configuration dialog for editing

#### Scenario: Provider API key status
- **WHEN** the Voice Configuration section renders
- **THEN** the UI SHALL indicate whether the required API key for the current `CLOUD_STT` model's provider is configured
- **AND** unconfigured providers SHALL show a setup hint

#### Scenario: Engine preference order
- **WHEN** a user reorders the engine preference list
- **THEN** the override SHALL be saved with key `voice.engine_preference_order`
- **AND** the list SHALL support drag-and-drop reordering

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

### Requirement: Notification Preferences UI

The Settings page SHALL include a Notifications section for per-event-type notification preferences.

#### Scenario: Display notification preferences
- **WHEN** the Settings page is loaded
- **THEN** a Notifications section SHALL display toggles for each notification event type
- **AND** each toggle SHALL show the event type name and a brief description

#### Scenario: Toggle event type
- **WHEN** a user toggles a notification event type on or off
- **THEN** the preference SHALL be saved with key `notification.<event_type>` via the settings override API
- **AND** a success toast SHALL be displayed

#### Scenario: Default preferences
- **WHEN** no notification preferences have been set
- **THEN** all event types SHALL default to enabled (`"true"`)

#### Scenario: Source badges
- **WHEN** notification preferences are displayed
- **THEN** each toggle SHALL show a source badge (env/db/default) indicating where the current value comes from

#### Scenario: Reset preference
- **WHEN** a user resets a notification preference
- **THEN** the database override SHALL be removed
- **AND** the default value (`"true"`) SHALL be restored
