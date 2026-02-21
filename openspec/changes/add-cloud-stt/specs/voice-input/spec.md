# voice-input Delta Spec

## MODIFIED Requirements

### Requirement: Voice Input Hook
The system SHALL provide a `useVoiceInput` React hook that wraps the Web Speech API, on-device Whisper engine, native Capacitor speech recognition, or cloud STT streaming, and exposes recording state, transcript, and control methods.

#### Scenario: Start listening
- **WHEN** `startListening()` is called
- **THEN** the hook SHALL activate the configured STT engine
- **AND** set `isListening` to `true`

#### Scenario: Stop listening
- **WHEN** `stopListening()` is called
- **THEN** the hook SHALL stop the active STT engine
- **AND** set `isListening` to `false`
- **AND** emit the final transcript via `onResult` callback

#### Scenario: Cloud engine option
- **WHEN** the `engine` option is set to `"cloud"`
- **THEN** the hook SHALL use the WebSocket-based cloud STT engine
- **AND** stream audio to the backend in real-time
- **AND** display interim transcripts as they arrive via WebSocket

#### Scenario: Auto engine preference order
- **WHEN** the `engine` option is set to `"auto"`
- **THEN** the hook SHALL select an engine based on a configurable preference order
- **AND** the default preference order SHALL be: `cloud` → `native` → `browser` → `on-device`
- **AND** the first available engine in the preference order SHALL be used

#### Scenario: Auto engine preference customization
- **WHEN** the user configures the engine preference order in settings
- **THEN** the `"auto"` engine SHALL follow the user's custom preference order

#### Scenario: Interim results (cloud)
- **WHEN** the cloud STT WebSocket returns a message with `type: "interim"`
- **THEN** the hook SHALL update `interimTranscript` with the interim text

#### Scenario: Final results (cloud)
- **WHEN** the cloud STT WebSocket returns a message with `type: "final"`
- **THEN** the hook SHALL append the result to `transcript`
- **AND** clear `interimTranscript`

#### Scenario: Continuous mode
- **WHEN** `continuous` option is set to `true`
- **THEN** the active engine SHALL remain active after each final result

#### Scenario: Language configuration
- **WHEN** `lang` option is provided
- **THEN** the hook SHALL configure the active engine with that language

#### Scenario: Reset transcript
- **WHEN** `resetTranscript()` is called
- **THEN** `transcript` and `interimTranscript` SHALL both be cleared

### Requirement: Voice Input Feature Detection
The system SHALL detect all available STT engines and disable voice input only when no engine is available.

#### Scenario: Cloud engine available
- **WHEN** a cloud STT provider is configured with a valid API key
- **THEN** `cloudAvailable` SHALL be `true`

#### Scenario: Cloud engine not configured
- **WHEN** no cloud STT provider API key is configured
- **THEN** `cloudAvailable` SHALL be `false`
- **AND** the engine preference order SHALL skip `"cloud"`

#### Scenario: At least one engine available
- **WHEN** any of `browserSupported`, `onDeviceAvailable`, `cloudAvailable`, or native is available
- **THEN** `isSupported` SHALL be `true`
