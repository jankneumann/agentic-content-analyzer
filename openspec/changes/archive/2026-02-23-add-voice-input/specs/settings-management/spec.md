# settings-management Delta Spec

## MODIFIED Requirements

### Requirement: Voice Configuration API

The system SHALL provide an endpoint to read and update voice/TTS configuration, protected by admin API key. The endpoint SHALL include both voice output (TTS) and voice input (STT) settings.

#### Scenario: Get current voice configuration
- **WHEN** `GET /api/v1/settings/voice` is called with a valid `X-Admin-Key` header
- **THEN** the response SHALL include: provider (openai/elevenlabs), default_voice, speed, and available presets
- **AND** the response SHALL include voice input settings: input_language, input_continuous, input_auto_submit
- **AND** each field SHALL indicate its source (env var, DB override, or code default)

#### Scenario: Update voice input language
- **WHEN** a voice input language override is saved via `PUT /api/v1/settings/voice/input_language` with a valid BCP-47 language tag
- **THEN** the override SHALL be persisted with key `voice.input_language`
- **AND** subsequent voice input sessions SHALL use the configured language

#### Scenario: Update voice input continuous mode
- **WHEN** a voice input continuous mode override is saved via `PUT /api/v1/settings/voice/input_continuous` with value `"true"` or `"false"`
- **THEN** the override SHALL be persisted with key `voice.input_continuous`

#### Scenario: Update voice input auto-submit
- **WHEN** a voice input auto-submit override is saved via `PUT /api/v1/settings/voice/input_auto_submit` with value `"true"` or `"false"`
- **THEN** the override SHALL be persisted with key `voice.input_auto_submit`

#### Scenario: Default voice input settings
- **WHEN** no voice input overrides exist
- **THEN** `input_language` SHALL default to `"en-US"`
- **AND** `input_continuous` SHALL default to `"false"`
- **AND** `input_auto_submit` SHALL default to `"false"`

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

### Requirement: Voice Configuration UI

The Settings page SHALL include a Voice Configuration section for TTS output settings and STT input settings.

#### Scenario: Display voice settings
- **WHEN** the Settings page is loaded
- **THEN** the Voice Configuration section SHALL display: provider selector, voice/preset picker, speed slider, and a Voice Input subsection

#### Scenario: Display voice input settings
- **WHEN** the Settings page is loaded
- **THEN** the Voice Input subsection SHALL display: language selector, continuous mode toggle, and auto-submit toggle

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

#### Scenario: Voice input language selector
- **WHEN** a user selects a language from the input language dropdown
- **THEN** the override SHALL be saved with key `voice.input_language`
- **AND** the dropdown SHALL show common languages (English US, English UK, Spanish, French, German, Japanese, Chinese)

#### Scenario: Continuous mode toggle
- **WHEN** a user toggles continuous mode on
- **THEN** the override SHALL be saved with key `voice.input_continuous` and value `"true"`
- **AND** a description SHALL explain that continuous mode keeps listening after each utterance

#### Scenario: Auto-submit toggle
- **WHEN** a user toggles auto-submit on
- **THEN** the override SHALL be saved with key `voice.input_auto_submit` and value `"true"`
- **AND** a description SHALL explain that messages are sent automatically after speech ends
