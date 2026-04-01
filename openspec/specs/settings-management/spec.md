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

### Requirement: Config Registry Service

The system SHALL provide a `ConfigRegistry` service that manages read-only access to YAML-based configuration defaults for all settings domains via `get(domain, key)` and `list_keys(domain)` methods, with cache invalidation via `reload(domain)`.

#### Scenario: settings-mgmt.1 — Domain registration (lazy loading)
- **GIVEN** a `ConfigDomain` with name="voice" and yaml_file="voice.yaml"
- **WHEN** `registry.register(domain)` is called
- **THEN** the domain SHALL be registered for lazy loading
- **AND** the YAML file SHALL NOT be opened or read until first `get()` call

#### Scenario: settings-mgmt.1a — Duplicate domain registration rejected
- **GIVEN** a domain "voice" is already registered
- **WHEN** `registry.register(ConfigDomain(name="voice", ...))` is called again
- **THEN** a `ValueError` SHALL be raised

#### Scenario: settings-mgmt.2 — Default value resolution
- **GIVEN** a registered domain "prompts" with YAML containing nested structure `chat: { summary: { system: "You are..." } }`
- **WHEN** `registry.get("prompts", "chat.summary.system")` is called
- **THEN** the string value `"You are..."` SHALL be returned
- **AND** the YAML file SHALL be cached after first load

#### Scenario: settings-mgmt.3 — Cache invalidation via reload
- **GIVEN** a previously loaded domain "models"
- **AND** the YAML file on disk has been modified since loading
- **WHEN** `registry.reload("models")` is called
- **THEN** the YAML file SHALL be re-read from disk
- **AND** subsequent `get()` calls SHALL return values from the reloaded file

#### Scenario: settings-mgmt.4 — Missing key returns None
- **GIVEN** a registered domain "voice"
- **WHEN** `registry.get("voice", "nonexistent.key")` is called
- **THEN** `None` SHALL be returned
- **AND** no exception SHALL be raised

#### Scenario: settings-mgmt.4a — Null YAML value returns None
- **GIVEN** a registered domain with YAML containing `chat: { summary: null }`
- **WHEN** `registry.get("domain", "chat.summary")` is called
- **THEN** `None` SHALL be returned

#### Scenario: settings-mgmt.5 — List all keys in domain
- **GIVEN** a registered domain with YAML `{a: {b: {c: 1}}, d: 2}`
- **WHEN** `registry.list_keys(domain)` is called
- **THEN** `["a.b.c", "d"]` SHALL be returned (leaf-node paths only)
- **AND** intermediate nodes (`"a"`, `"a.b"`) SHALL NOT appear in the list

#### Scenario: settings-mgmt.6 — Unregistered domain raises error
- **WHEN** `registry.get("unknown_domain", "key")` is called
- **THEN** a `ValueError` SHALL be raised with a message listing available domains

#### Scenario: settings-mgmt.6a — Malformed YAML raises error
- **GIVEN** a registered domain "broken" whose YAML file contains invalid syntax
- **WHEN** `registry.get("broken", "any.key")` is called
- **THEN** a `yaml.YAMLError` (or subclass) SHALL be raised

#### Scenario: settings-mgmt.6b — Missing YAML file raises error
- **GIVEN** a registered domain "missing" whose yaml_file does not exist on disk
- **WHEN** `registry.get("missing", "any.key")` is called
- **THEN** a `FileNotFoundError` SHALL be raised

### Requirement: Settings YAML Directory

The system SHALL use a top-level `settings/` directory (at project root, same level as `src/`, `profiles/`, `sources.d/`) for all configurable default YAML files.

#### Scenario: settings-mgmt.7 — YAML files present
- **GIVEN** the project repository
- **THEN** `settings/prompts.yaml` SHALL exist (moved from `src/config/prompts.yaml`)
- **AND** `settings/models.yaml` SHALL exist (moved from `src/config/model_registry.yaml`)
- **AND** `settings/voice.yaml` SHALL exist (new)
- **AND** `settings/notifications.yaml` SHALL exist (new)
- **AND** all four files SHALL be loadable as valid YAML

#### Scenario: settings-mgmt.8 — Old YAML paths removed
- **GIVEN** the migration is complete
- **THEN** `src/config/prompts.yaml` SHALL NOT exist (deleted, not symlinked)
- **AND** `src/config/model_registry.yaml` SHALL NOT exist (deleted, not symlinked)
- **AND** all code SHALL use ConfigRegistry for YAML loading instead of direct file reads

### Requirement: Settings Precedence

The system SHALL maintain the precedence order: environment variable > database override > YAML default. If a key exists in multiple sources, the highest-precedence source wins.

#### Scenario: settings-mgmt.9 — Env var wins over DB and YAML
- **GIVEN** a setting with key "voice.provider"
- **AND** the ConfigRegistry returns YAML default "openai"
- **AND** a DB override in `settings_overrides` sets it to "elevenlabs"
- **AND** an env var `AUDIO_DIGEST_PROVIDER` is set to "deepgram"
- **THEN** the resolved value SHALL be "deepgram" (env var wins)

#### Scenario: settings-mgmt.10 — DB override wins over YAML
- **GIVEN** a setting with key "model.summarization"
- **AND** the ConfigRegistry returns YAML default "claude-haiku-4-5"
- **AND** a DB override in `settings_overrides` sets it to "gemini-2.5-flash"
- **AND** no env var is set
- **THEN** the resolved value SHALL be "gemini-2.5-flash"

#### Scenario: settings-mgmt.10a — Voice YAML defaults loaded correctly
- **GIVEN** a loaded domain "voice" with `settings/voice.yaml`
- **WHEN** `registry.get("voice", "provider")` is called
- **THEN** `"openai"` SHALL be returned (matching the default from Settings class)

#### Scenario: settings-mgmt.10b — Notification YAML defaults loaded correctly
- **GIVEN** a loaded domain "notifications" with `settings/notifications.yaml`
- **WHEN** `registry.get("notifications", "defaults.batch_summary")` is called
- **THEN** `true` SHALL be returned

### Requirement: Connection Status Endpoint Migration

The system SHALL serve connection health status from `/api/v1/status/connections`.

#### Scenario: settings-mgmt.11 — New status endpoint
- **WHEN** GET `/api/v1/status/connections` is called with valid auth
- **THEN** the response SHALL return HTTP 200
- **AND** the response SHALL contain a JSON object with `status` (string) and `services` (object with per-service health)
- **AND** each service entry SHALL include `status` and `latency_ms` fields

#### Scenario: settings-mgmt.12 — Old endpoint redirects
- **WHEN** GET `/api/v1/settings/connections` is called
- **THEN** a 307 redirect to `/api/v1/status/connections` SHALL be returned
- **AND** the redirect SHALL preserve the request method and auth headers

### Requirement: Frontend Tabbed Settings

The system SHALL organize settings into tabbed sub-pages under `/settings` using React Router nested routes.

#### Scenario: settings-mgmt.13 — Tab navigation
- **WHEN** the user navigates to `/settings`
- **THEN** a `<nav role="tablist">` SHALL be visible with exactly 4 tab buttons: Prompts, Models, Voice, Notifications (in that order)
- **AND** the Prompts tab SHALL be active by default (URL redirects to `/settings/prompts`)

#### Scenario: settings-mgmt.14 — Tab URL routing and lazy loading
- **WHEN** the user clicks the "Models" tab
- **THEN** the URL SHALL change to `/settings/models`
- **AND** the Models configuration component SHALL be rendered
- **AND** exactly one HTTP API call for `/api/v1/settings/models` SHALL be initiated
- **AND** no HTTP API calls for other tabs' data (prompts, voice, notifications) SHALL be initiated

#### Scenario: settings-mgmt.15 — Direct URL navigation
- **WHEN** the user navigates directly to `/settings/voice`
- **THEN** the Voice tab button SHALL have `aria-selected="true"`
- **AND** other tab buttons SHALL have `aria-selected="false"`
- **AND** the voice configuration component SHALL be rendered

#### Scenario: settings-mgmt.15a — Invalid tab URL
- **WHEN** the user navigates to `/settings/nonexistent`
- **THEN** the user SHALL be redirected to `/settings/prompts`
- **OR** a 404 page SHALL be displayed

### Requirement: Connections Removed from Settings

The connections health dashboard SHALL NOT appear as a tab or section in the settings page.

#### Scenario: settings-mgmt.16 — Top-level status page
- **WHEN** the user navigates to `/status`
- **THEN** the connections health dashboard SHALL be displayed with service health rows
- **AND** no tab for "Connections" or "Health" SHALL appear in the settings tab bar

#### Scenario: settings-mgmt.16a — Connections not in settings
- **GIVEN** the user is on `/settings` or any `/settings/*` sub-page
- **WHEN** the page renders
- **THEN** no connections/health dashboard component SHALL be visible
- **AND** the tab count SHALL be exactly 4 (Prompts, Models, Voice, Notifications)

### Requirement: All Domains Registered at Startup

The system SHALL register all four settings domains (prompts, models, voice, notifications) with the ConfigRegistry before the application is ready to serve requests.

#### Scenario: settings-mgmt.17 — Startup registration
- **GIVEN** the FastAPI application starts
- **WHEN** the lifespan or module-level initialization completes
- **THEN** `registry.list_keys("prompts")` SHALL return a non-empty list
- **AND** `registry.list_keys("models")` SHALL return a non-empty list
- **AND** `registry.list_keys("voice")` SHALL return a non-empty list
- **AND** `registry.list_keys("notifications")` SHALL return a non-empty list

