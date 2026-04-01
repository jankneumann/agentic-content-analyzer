# Settings Management — Delta Spec (settings-reorganization)

## ADDED Requirements

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
