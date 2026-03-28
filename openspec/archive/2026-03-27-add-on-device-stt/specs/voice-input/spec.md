# voice-input Delta Spec

## MODIFIED Requirements

### Requirement: Voice Input Hook
The system SHALL provide a `useVoiceInput` React hook that wraps the Web Speech API or on-device Whisper engine and exposes recording state, transcript, and control methods.

#### Scenario: Start listening
- **WHEN** `startListening()` is called
- **THEN** the hook SHALL activate the configured STT engine (browser or on-device)
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
- **WHEN** the SpeechRecognition `result` event fires with `isFinal === false`
- **THEN** the hook SHALL update `interimTranscript` with the current in-progress text
- **AND** `interimTranscript` SHALL be visually distinct from final text

#### Scenario: Final results
- **WHEN** the SpeechRecognition `result` event fires with `isFinal === true`
- **THEN** the hook SHALL append the result to `transcript`
- **AND** clear `interimTranscript`

#### Scenario: Engine option
- **WHEN** the `engine` option is set to `"browser"`, `"on-device"`, or `"auto"`
- **THEN** the hook SHALL use the corresponding STT backend
- **AND** default to `"auto"` if not specified

#### Scenario: Continuous mode
- **WHEN** `continuous` option is set to `true`
- **THEN** SpeechRecognition SHALL remain active after each final result
- **AND** continue accepting speech until explicitly stopped

#### Scenario: Single-utterance mode
- **WHEN** `continuous` option is set to `false` (default)
- **THEN** SpeechRecognition SHALL stop after the first final result

#### Scenario: Language configuration
- **WHEN** `lang` option is provided (e.g., `"en-US"`)
- **THEN** the hook SHALL set `SpeechRecognition.lang` to that value
- **AND** default to `"en-US"` if not specified

#### Scenario: Reset transcript
- **WHEN** `resetTranscript()` is called
- **THEN** `transcript` and `interimTranscript` SHALL both be cleared to empty strings

### Requirement: Voice Input Feature Detection
The system SHALL detect STT engine availability (Web Speech API and/or on-device model) and disable voice input gracefully when no engine is available.

#### Scenario: Browser engine supported
- **WHEN** `window.SpeechRecognition` or `window.webkitSpeechRecognition` is available
- **THEN** `browserSupported` SHALL be `true`

#### Scenario: On-device engine available
- **WHEN** an on-device Whisper model is cached in the browser
- **THEN** `onDeviceAvailable` SHALL be `true`

#### Scenario: At least one engine available
- **WHEN** `browserSupported` is `true` OR `onDeviceAvailable` is `true`
- **THEN** `isSupported` SHALL be `true`
- **AND** the voice input button SHALL be enabled

#### Scenario: No engine available
- **WHEN** `browserSupported` is `false` AND `onDeviceAvailable` is `false`
- **THEN** `isSupported` SHALL be `false`
- **AND** the voice input button SHALL be disabled with a tooltip suggesting model download
