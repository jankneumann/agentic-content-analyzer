# voice-input Delta Spec

## MODIFIED Requirements

### Requirement: Voice Input Hook
The system SHALL provide a `useVoiceInput` React hook that wraps the Web Speech API, on-device Whisper engine, or native Capacitor speech recognition, and exposes recording state, transcript, and control methods.

#### Scenario: Start listening
- **WHEN** `startListening()` is called
- **THEN** the hook SHALL activate the configured STT engine (browser, on-device, or native)
- **AND** set `isListening` to `true`

#### Scenario: Stop listening
- **WHEN** `stopListening()` is called
- **THEN** the hook SHALL stop the active STT engine
- **AND** set `isListening` to `false`
- **AND** emit the final transcript via `onResult` callback

#### Scenario: Toggle listening
- **WHEN** `toggleListening()` is called while not listening
- **THEN** the hook SHALL start listening
- **WHEN** `toggleListening()` is called while listening
- **THEN** the hook SHALL stop listening

#### Scenario: Interim results
- **WHEN** the active STT engine produces an interim result
- **THEN** the hook SHALL update `interimTranscript` with the current in-progress text

#### Scenario: Final results
- **WHEN** the active STT engine produces a final result
- **THEN** the hook SHALL append the result to `transcript`
- **AND** clear `interimTranscript`

#### Scenario: Native engine option
- **WHEN** the `engine` option is set to `"native"`
- **AND** the app is running on a Capacitor native platform
- **THEN** the hook SHALL use the Capacitor speech recognition plugin

#### Scenario: Native engine on web
- **WHEN** the `engine` option is set to `"native"`
- **AND** the app is running in a web browser
- **THEN** the hook SHALL fall back to the `"browser"` engine

#### Scenario: Auto engine on native
- **WHEN** the `engine` option is set to `"auto"`
- **AND** the app is running on a Capacitor native platform
- **THEN** the hook SHALL prefer the `"native"` engine

#### Scenario: Continuous mode
- **WHEN** `continuous` option is set to `true`
- **THEN** the active engine SHALL remain active after each final result

#### Scenario: Language configuration
- **WHEN** `lang` option is provided
- **THEN** the hook SHALL configure the active engine with that language

#### Scenario: Reset transcript
- **WHEN** `resetTranscript()` is called
- **THEN** `transcript` and `interimTranscript` SHALL both be cleared
