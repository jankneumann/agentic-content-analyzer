# settings-management Delta Spec

## MODIFIED Requirements

### Requirement: Voice Configuration API

The system SHALL provide an endpoint to read and update voice configuration including cloud STT provider settings, protected by admin API key.

#### Scenario: Get current voice configuration
- **WHEN** `GET /api/v1/settings/voice` is called with a valid `X-Admin-Key` header
- **THEN** the response SHALL include cloud STT settings: `cloud_stt_provider`, `cloud_stt_language`, `engine_preference_order`
- **AND** each field SHALL indicate its source (env var, DB override, or code default)

#### Scenario: Update cloud STT provider
- **WHEN** a cloud STT provider override is saved via `PUT /api/v1/settings/voice/cloud_stt_provider` with value `"openai"`, `"deepgram"`, or `"google"`
- **THEN** the override SHALL be persisted with key `voice.cloud_stt_provider`

#### Scenario: Update cloud STT language
- **WHEN** a cloud STT language override is saved via `PUT /api/v1/settings/voice/cloud_stt_language` with a valid BCP-47 language tag or `"auto"`
- **THEN** the override SHALL be persisted with key `voice.cloud_stt_language`

#### Scenario: Update engine preference order
- **WHEN** an engine preference order override is saved via `PUT /api/v1/settings/voice/engine_preference_order` with a comma-separated list (e.g., `"cloud,browser,on-device"`)
- **THEN** the override SHALL be persisted with key `voice.engine_preference_order`
- **AND** the list SHALL only contain valid engine names

#### Scenario: Default cloud STT settings
- **WHEN** no cloud STT overrides exist
- **THEN** `cloud_stt_provider` SHALL default to `"openai"`
- **AND** `cloud_stt_language` SHALL default to `"auto"`
- **AND** `engine_preference_order` SHALL default to `"cloud,native,browser,on-device"`

#### Scenario: Validate cloud STT provider
- **WHEN** a cloud STT provider override is saved with a value other than `"openai"`, `"deepgram"`, or `"google"`
- **THEN** the system SHALL return a 400 error listing the valid providers

#### Scenario: Authentication required for voice endpoint
- **WHEN** `GET /api/v1/settings/voice` is called without a valid `X-Admin-Key` header
- **THEN** the response SHALL be 401 Unauthorized

### Requirement: Voice Configuration UI

The Settings page SHALL include cloud STT configuration within the Voice Configuration section.

#### Scenario: Display cloud STT settings
- **WHEN** the Settings page is loaded
- **THEN** the Voice Configuration section SHALL display a Cloud STT subsection
- **AND** it SHALL include: provider selector, language selector, and engine preference order

#### Scenario: Cloud STT provider selector
- **WHEN** a user selects a cloud STT provider
- **THEN** the override SHALL be saved with key `voice.cloud_stt_provider`
- **AND** the selector SHALL show available providers with their configuration status (configured / not configured)

#### Scenario: Provider API key status
- **WHEN** a cloud STT provider is selected
- **THEN** the UI SHALL indicate whether the required API key is configured
- **AND** unconfigured providers SHALL show a setup hint

#### Scenario: Engine preference order
- **WHEN** a user reorders the engine preference list
- **THEN** the override SHALL be saved with key `voice.engine_preference_order`
- **AND** the list SHALL support drag-and-drop reordering
