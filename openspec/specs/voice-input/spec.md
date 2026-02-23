# voice-input Specification

## Purpose
TBD - created by archiving change add-voice-input. Update Purpose after archive.
## Requirements
### Requirement: Voice Input Hook
The system SHALL provide a `useVoiceInput` React hook that wraps the Web Speech API and exposes recording state, transcript, and control methods.

#### Scenario: Start listening
- **WHEN** `startListening()` is called
- **THEN** the hook SHALL request microphone access via `SpeechRecognition.start()`
- **AND** set `isListening` to `true`

#### Scenario: Stop listening
- **WHEN** `stopListening()` is called
- **THEN** the hook SHALL call `SpeechRecognition.stop()`
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
The system SHALL detect Web Speech API availability and disable voice input gracefully on unsupported browsers.

#### Scenario: Supported browser
- **WHEN** `window.SpeechRecognition` or `window.webkitSpeechRecognition` is available
- **THEN** `isSupported` SHALL be `true`
- **AND** the voice input button SHALL be enabled

#### Scenario: Unsupported browser
- **WHEN** neither `window.SpeechRecognition` nor `window.webkitSpeechRecognition` is available
- **THEN** `isSupported` SHALL be `false`
- **AND** the voice input button SHALL be rendered as disabled
- **AND** a tooltip SHALL explain that the browser does not support speech recognition

### Requirement: Voice Input Error Handling
The system SHALL handle all SpeechRecognition error events gracefully with user-facing feedback.

#### Scenario: Microphone permission denied
- **WHEN** the SpeechRecognition `error` event fires with `error === "not-allowed"`
- **THEN** the hook SHALL set `error` to a message explaining microphone permission is required
- **AND** set `isListening` to `false`

#### Scenario: No speech detected
- **WHEN** the SpeechRecognition `error` event fires with `error === "no-speech"`
- **THEN** the hook SHALL set `error` to a message indicating no speech was detected
- **AND** set `isListening` to `false`

#### Scenario: Network error
- **WHEN** the SpeechRecognition `error` event fires with `error === "network"`
- **THEN** the hook SHALL set `error` to a message indicating a network connection is required
- **AND** set `isListening` to `false`

#### Scenario: Audio capture error
- **WHEN** the SpeechRecognition `error` event fires with `error === "audio-capture"`
- **THEN** the hook SHALL set `error` to a message indicating no microphone was found
- **AND** set `isListening` to `false`

### Requirement: Voice Input Button Component
The system SHALL provide a `VoiceInputButton` React component with microphone icon, recording animation, and accessibility labels.

#### Scenario: Idle state
- **WHEN** voice input is not active
- **THEN** the button SHALL display a microphone icon
- **AND** have `aria-label="Start voice input"`

#### Scenario: Recording state
- **WHEN** voice input is active (`isListening === true`)
- **THEN** the button SHALL display a pulsing animation (red ring)
- **AND** the microphone icon SHALL change to indicate active recording
- **AND** have `aria-label="Stop voice input"`

#### Scenario: Disabled state
- **WHEN** the Web Speech API is not supported
- **THEN** the button SHALL be visually disabled
- **AND** have `aria-disabled="true"`
- **AND** display a tooltip on hover explaining browser support requirements

#### Scenario: Error state
- **WHEN** a voice input error occurs
- **THEN** the button SHALL briefly display an error indicator
- **AND** a toast notification SHALL show the error message

### Requirement: Chat Input Voice Integration
The system SHALL integrate voice input into the ChatInput component.

#### Scenario: Voice button placement
- **WHEN** the ChatInput component renders
- **THEN** a `VoiceInputButton` SHALL appear adjacent to the send button

#### Scenario: Transcript insertion
- **WHEN** voice input produces a final transcript
- **THEN** the transcript text SHALL be appended to the current textarea content
- **AND** the textarea SHALL resize to fit the new content

#### Scenario: Interim transcript display
- **WHEN** voice input produces an interim transcript
- **THEN** the interim text SHALL be displayed in the textarea with reduced opacity
- **AND** the interim text SHALL be replaced by the final transcript when available

#### Scenario: Auto-submit
- **WHEN** auto-submit is enabled in voice input settings
- **AND** voice input produces a final transcript in single-utterance mode
- **THEN** the chat message SHALL be submitted automatically

#### Scenario: Auto-submit disabled
- **WHEN** auto-submit is disabled (default)
- **AND** voice input produces a final transcript
- **THEN** the transcript SHALL be inserted but NOT submitted
- **AND** the user SHALL manually press send or Enter

### Requirement: Search Input Voice Integration
The system SHALL integrate voice input into the main search bar.

#### Scenario: Voice button in search
- **WHEN** the search input renders
- **THEN** a `VoiceInputButton` SHALL appear inside the search input (right side)

#### Scenario: Search transcript insertion
- **WHEN** voice input produces a final transcript in a search field
- **THEN** the transcript SHALL replace the current search text
- **AND** the search SHALL be triggered automatically

### Requirement: LLM Transcript Cleanup
The system SHALL provide an LLM-based cleanup step that transforms raw voice transcripts into structured, polished text, triggered by a voice key phrase or a dedicated UI button.

#### Scenario: Cleanup button placement
- **WHEN** the ChatInput component renders with voice input enabled
- **THEN** a cleanup button (sparkle/wand icon) SHALL appear adjacent to the microphone button
- **AND** it SHALL be disabled when the textarea is empty

#### Scenario: Trigger cleanup via button
- **WHEN** the user clicks the cleanup button
- **AND** the textarea contains text
- **THEN** the system SHALL send the text to `POST /api/v1/voice/cleanup`
- **AND** display a loading spinner on the cleanup button
- **AND** replace the textarea content with the cleaned-up response

#### Scenario: Trigger cleanup via voice key phrase
- **WHEN** voice input is active in continuous mode
- **AND** the user says a configured key phrase (default: "clean up")
- **THEN** voice input SHALL stop
- **AND** the cleanup SHALL be triggered automatically on the accumulated transcript
- **AND** the key phrase itself SHALL NOT be included in the text sent for cleanup

#### Scenario: Cleanup API request
- **WHEN** `POST /api/v1/voice/cleanup` is called with `{ "text": "raw transcript" }`
- **THEN** the backend SHALL send the text to the configured LLM with a cleanup prompt
- **AND** return `{ "cleaned_text": "structured result" }` with the cleaned version

#### Scenario: Cleanup prompt behavior
- **WHEN** the LLM processes a cleanup request
- **THEN** it SHALL fix grammar, punctuation, and remove filler words (um, uh, like)
- **AND** structure the text appropriately (paragraphs, bullet points) based on context
- **AND** preserve the user's intent and meaning without adding information
- **AND** return only the cleaned text without explanations or metadata

#### Scenario: Cleanup model as pipeline step
- **WHEN** the cleanup model is not explicitly configured
- **THEN** the system SHALL use the `VOICE_CLEANUP` pipeline step (default: `claude-haiku-4-5`)
- **AND** the step SHALL be registered in the `ModelStep` enum alongside existing steps (summarization, theme_analysis, etc.)
- **AND** the default model SHALL be defined in `model_registry.yaml` under `default_models.voice_cleanup`
- **AND** the step SHALL appear in the Model Configuration UI on the Settings page automatically
- **AND** the model SHALL be overridable via env var `MODEL_VOICE_CLEANUP`, DB override, or YAML default (standard 3-tier precedence)

#### Scenario: Cleanup error handling
- **WHEN** the cleanup API call fails (network error or server error)
- **THEN** the original text SHALL remain in the textarea unchanged
- **AND** an error toast SHALL be displayed
- **AND** the cleanup button SHALL return to its idle state

#### Scenario: Cleanup preserves cursor position
- **WHEN** cleanup completes successfully
- **THEN** the textarea content SHALL be replaced with the cleaned text
- **AND** the cursor SHALL be positioned at the end of the cleaned text
- **AND** the textarea SHALL resize to fit the new content

#### Scenario: Keyboard shortcut for cleanup
- **WHEN** the textarea has focus and contains text
- **AND** the user presses `Ctrl+Shift+C` / `Cmd+Shift+C`
- **THEN** the cleanup SHALL be triggered

### Requirement: Voice Input Accessibility
Voice input controls SHALL meet WCAG 2.1 AA accessibility requirements.

#### Scenario: Keyboard activation
- **WHEN** the voice input button has focus
- **AND** the user presses Enter or Space
- **THEN** voice input SHALL toggle on/off

#### Scenario: Screen reader announcement
- **WHEN** voice input state changes (start, stop, error)
- **THEN** an ARIA live region SHALL announce the state change
- **AND** the announcement SHALL describe the current state (e.g., "Recording started", "Recording stopped")

#### Scenario: Focus management
- **WHEN** voice input stops
- **THEN** focus SHALL return to the associated input field
- **AND** the cursor SHALL be positioned at the end of the inserted text
