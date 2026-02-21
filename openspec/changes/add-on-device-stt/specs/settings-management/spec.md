# settings-management Delta Spec

## MODIFIED Requirements

### Requirement: Voice Configuration API

The system SHALL provide an endpoint to read and update voice/TTS configuration, protected by admin API key. The endpoint SHALL include voice output (TTS), voice input (STT), and STT engine settings.

#### Scenario: Get current voice configuration
- **WHEN** `GET /api/v1/settings/voice` is called with a valid `X-Admin-Key` header
- **THEN** the response SHALL include: provider (openai/elevenlabs), default_voice, speed, available presets, voice input settings, and STT engine settings
- **AND** STT engine settings SHALL include: `stt_engine`, `stt_model_size`
- **AND** each field SHALL indicate its source (env var, DB override, or code default)

#### Scenario: Update STT engine preference
- **WHEN** a STT engine override is saved via `PUT /api/v1/settings/voice/stt_engine` with value `"auto"`, `"browser"`, or `"on-device"`
- **THEN** the override SHALL be persisted with key `voice.stt_engine`

#### Scenario: Update STT model size
- **WHEN** a STT model size override is saved via `PUT /api/v1/settings/voice/stt_model_size` with value `"tiny"` or `"base"`
- **THEN** the override SHALL be persisted with key `voice.stt_model_size`

#### Scenario: Default STT engine settings
- **WHEN** no STT engine overrides exist
- **THEN** `stt_engine` SHALL default to `"auto"`
- **AND** `stt_model_size` SHALL default to `"tiny"`

#### Scenario: Validate STT engine value
- **WHEN** a STT engine override is saved with a value other than `"auto"`, `"browser"`, or `"on-device"`
- **THEN** the system SHALL return a 400 error listing the valid engine options

#### Scenario: Validate STT model size value
- **WHEN** a STT model size override is saved with a value other than `"tiny"` or `"base"`
- **THEN** the system SHALL return a 400 error listing the valid model sizes

#### Scenario: Authentication required for voice endpoint
- **WHEN** `GET /api/v1/settings/voice` is called without a valid `X-Admin-Key` header
- **THEN** the response SHALL be 401 Unauthorized

### Requirement: Voice Configuration UI

The Settings page SHALL include a Voice Configuration section for TTS output, STT input, and STT engine settings.

#### Scenario: Display STT engine settings
- **WHEN** the Settings page is loaded
- **THEN** the Voice Configuration section SHALL display an STT Engine subsection
- **AND** it SHALL include: engine selector (Auto/Browser/On-Device), model size selector, model management controls

#### Scenario: Model download button
- **WHEN** no on-device model is cached
- **THEN** a "Download Model" button SHALL be displayed with model size information

#### Scenario: Model status indicator
- **WHEN** an on-device model is cached
- **THEN** a green status indicator SHALL show the cached model name and size
- **AND** a "Delete Model" button SHALL be available
