# voice-input Delta Spec

## MODIFIED Requirements

### Requirement: Voice Input Hook
The system SHALL provide a `useVoiceInput` React hook that wraps the Web Speech API, on-device Whisper engine, native Capacitor speech recognition, or Tauri-hosted STT, and exposes recording state, transcript, and control methods.

#### Scenario: Start listening
- **WHEN** `startListening()` is called
- **THEN** the hook SHALL activate the configured STT engine
- **AND** set `isListening` to `true`

#### Scenario: Stop listening
- **WHEN** `stopListening()` is called
- **THEN** the hook SHALL stop the active STT engine
- **AND** set `isListening` to `false`
- **AND** emit the final transcript via `onResult` callback

#### Scenario: Global hotkey trigger
- **WHEN** the global keyboard shortcut is pressed on a Tauri desktop
- **THEN** `toggleListening()` SHALL be called
- **AND** a floating voice input overlay SHALL appear if starting

#### Scenario: Floating overlay transcript
- **WHEN** voice input is activated via the global shortcut
- **THEN** interim and final transcripts SHALL be displayed in the floating overlay
- **AND** the transcript SHALL be available for insertion into the app when the overlay is dismissed

#### Scenario: Interim results
- **WHEN** the active STT engine produces an interim result
- **THEN** the hook SHALL update `interimTranscript`

#### Scenario: Final results
- **WHEN** the active STT engine produces a final result
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
