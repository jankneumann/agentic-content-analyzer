# settings-management Delta Spec

## MODIFIED Requirements

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
