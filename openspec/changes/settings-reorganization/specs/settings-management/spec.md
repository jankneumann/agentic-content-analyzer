# Settings Management — Delta Spec (settings-reorganization)

## ADDED Requirements

### Requirement: Config Registry Service

The system SHALL provide a `ConfigRegistry` service that manages YAML-based configuration defaults for all settings domains.

#### Scenario: settings-mgmt.1 — Domain registration
- **GIVEN** a `ConfigDomain` with name="voice" and yaml_file="voice.yaml"
- **WHEN** `registry.register(domain)` is called
- **THEN** the domain SHALL be registered for lazy loading
- **AND** the YAML file SHALL NOT be loaded until first access

#### Scenario: settings-mgmt.2 — Default value resolution
- **GIVEN** a registered domain "prompts" with YAML containing `chat.summary.system: "You are..."`
- **WHEN** `registry.get("prompts", "chat.summary.system")` is called
- **THEN** the value "You are..." SHALL be returned
- **AND** the YAML file SHALL be cached after first load

#### Scenario: settings-mgmt.3 — Cache invalidation
- **GIVEN** a previously loaded domain "models"
- **WHEN** `registry.reload("models")` is called
- **THEN** the YAML file SHALL be re-read from disk
- **AND** subsequent `get()` calls SHALL return fresh values

#### Scenario: settings-mgmt.4 — Missing key returns None
- **GIVEN** a registered domain "voice"
- **WHEN** `registry.get("voice", "nonexistent.key")` is called
- **THEN** `None` SHALL be returned
- **AND** no exception SHALL be raised

#### Scenario: settings-mgmt.5 — List all keys in domain
- **GIVEN** a registered domain with nested YAML structure
- **WHEN** `registry.list_keys(domain)` is called
- **THEN** all leaf-node keys SHALL be returned as dot-separated paths
- **AND** intermediate nodes SHALL NOT appear in the list

#### Scenario: settings-mgmt.6 — Unregistered domain raises error
- **WHEN** `registry.get("unknown_domain", "key")` is called
- **THEN** a `ValueError` SHALL be raised with a message listing available domains

### Requirement: Settings YAML Directory

The system SHALL use a top-level `settings/` directory for all configurable default YAML files.

#### Scenario: settings-mgmt.7 — YAML files present
- **GIVEN** the project repository
- **THEN** `settings/prompts.yaml` SHALL exist (moved from `src/config/prompts.yaml`)
- **AND** `settings/models.yaml` SHALL exist (moved from `src/config/model_registry.yaml`)
- **AND** `settings/voice.yaml` SHALL exist (new)
- **AND** `settings/notifications.yaml` SHALL exist (new)

#### Scenario: settings-mgmt.8 — Old YAML paths resolve via symlink or redirect
- **GIVEN** code that previously imported from `src/config/prompts.yaml`
- **WHEN** the code loads the file
- **THEN** it SHALL resolve to `settings/prompts.yaml`

### Requirement: Settings Precedence

The system SHALL maintain the existing settings precedence order.

#### Scenario: settings-mgmt.9 — Precedence chain
- **GIVEN** a setting with key "voice.provider"
- **AND** the YAML default is "openai"
- **AND** a DB override sets it to "elevenlabs"
- **AND** an env var `AUDIO_DIGEST_PROVIDER` is set to "deepgram"
- **THEN** the resolved value SHALL be "deepgram" (env var wins)

#### Scenario: settings-mgmt.10 — DB override wins over YAML
- **GIVEN** a setting with key "model.summarization"
- **AND** the YAML default is "claude-haiku-4-5"
- **AND** a DB override sets it to "gemini-2.5-flash"
- **AND** no env var is set
- **THEN** the resolved value SHALL be "gemini-2.5-flash"

### Requirement: Connection Status Endpoint Migration

The system SHALL serve connection health status from `/api/v1/status/connections`.

#### Scenario: settings-mgmt.11 — New status endpoint
- **WHEN** GET `/api/v1/status/connections` is called with valid auth
- **THEN** the response SHALL contain service health statuses
- **AND** the response format SHALL match the existing `/api/v1/settings/connections` response

#### Scenario: settings-mgmt.12 — Old endpoint redirects
- **WHEN** GET `/api/v1/settings/connections` is called
- **THEN** a 307 redirect to `/api/v1/status/connections` SHALL be returned

### Requirement: Frontend Tabbed Settings

The system SHALL organize settings into tabbed sub-pages under `/settings`.

#### Scenario: settings-mgmt.13 — Tab navigation
- **WHEN** the user navigates to `/settings`
- **THEN** a tab bar SHALL be displayed with tabs: Prompts, Models, Voice, Notifications
- **AND** the default tab SHALL be Prompts

#### Scenario: settings-mgmt.14 — Tab URL routing
- **WHEN** the user clicks the "Models" tab
- **THEN** the URL SHALL change to `/settings/models`
- **AND** only the Models configuration SHALL be displayed
- **AND** no other tab's data SHALL be fetched

#### Scenario: settings-mgmt.15 — Direct URL navigation
- **WHEN** the user navigates directly to `/settings/voice`
- **THEN** the Voice tab SHALL be active
- **AND** the voice configuration SHALL be displayed

#### Scenario: settings-mgmt.16 — Top-level status page
- **WHEN** the user navigates to `/status`
- **THEN** the connections health dashboard SHALL be displayed
- **AND** it SHALL NOT be accessible under `/settings`
