# cloud-stt Specification

## Purpose
TBD - created by archiving change add-cloud-stt. Update Purpose after archive.
## Requirements
### Requirement: Cloud STT Provider Abstraction
The system SHALL provide a provider abstraction for cloud-based speech-to-text services, where the provider is determined by the model selected for the `CLOUD_STT` pipeline step.

#### Scenario: Provider interface
- **WHEN** a cloud STT provider is implemented
- **THEN** it SHALL implement the `CloudSTTProvider` interface with methods: `start_stream()`, `send_audio(chunk)`, `get_results()`, `stop_stream()`
- **AND** it SHALL normalize provider-specific response formats into a common transcript result structure
- **AND** each result SHALL include a `cleaned: boolean` flag indicating whether the transcript includes built-in cleanup

#### Scenario: Provider resolved from model family
- **WHEN** a model is configured for the `CLOUD_STT` pipeline step
- **THEN** the system SHALL resolve the provider adapter from the model family
- **AND** `gemini` family models SHALL use the `GeminiSTTProvider`
- **AND** `whisper` family models SHALL use the `WhisperSTTProvider`
- **AND** `deepgram` family models SHALL use the `DeepgramSTTProvider`

#### Scenario: Gemini provider (default)
- **WHEN** the `CLOUD_STT` model is a Gemini family model (e.g., `gemini-2.5-flash`)
- **THEN** the system SHALL use the Google Gemini API with native audio input for transcription
- **AND** the transcription prompt SHALL include cleanup instructions (fix grammar, remove filler words, structure text)
- **AND** the result SHALL have `cleaned: true`
- **AND** use the configured `GOOGLE_API_KEY`

#### Scenario: OpenAI Whisper provider
- **WHEN** the `CLOUD_STT` model is a Whisper family model (e.g., `whisper-1`)
- **THEN** the system SHALL use the OpenAI Whisper API for transcription
- **AND** the result SHALL have `cleaned: false` (raw transcript)
- **AND** use the configured `OPENAI_API_KEY`

#### Scenario: Deepgram provider
- **WHEN** the `CLOUD_STT` model is a Deepgram family model (e.g., `deepgram-nova-3`)
- **THEN** the system SHALL use the Deepgram streaming API for transcription
- **AND** the result SHALL have `cleaned: false` (raw transcript)
- **AND** use the configured `DEEPGRAM_API_KEY`

#### Scenario: Provider not configured
- **WHEN** the selected `CLOUD_STT` model's provider has no API key configured
- **THEN** the system SHALL return an error indicating the provider requires configuration
- **AND** the Model Configuration dialog SHALL show the API key status for the selected model's provider

### Requirement: WebSocket Audio Streaming Endpoint
The system SHALL provide a WebSocket endpoint for real-time audio streaming and transcript delivery.

#### Scenario: WebSocket connection
- **WHEN** a client connects to `ws://{host}/ws/voice/stream`
- **THEN** the server SHALL authenticate the connection via `X-Admin-Key` in the initial handshake query params
- **AND** establish a streaming session with the configured cloud STT provider

#### Scenario: Authentication required
- **WHEN** a WebSocket connection is attempted without a valid `X-Admin-Key`
- **THEN** the server SHALL reject the connection with an HTTP 401 response during the WebSocket handshake (before upgrade)

#### Scenario: Send audio chunk
- **WHEN** the client sends a binary WebSocket message containing audio data (PCM 16-bit mono 16kHz)
- **THEN** the server SHALL forward the audio chunk to the cloud STT provider's streaming API

#### Scenario: Receive interim transcript
- **WHEN** the cloud STT provider returns an interim (non-final) transcript result
- **THEN** the server SHALL send a JSON WebSocket message: `{ "type": "interim", "text": "partial transcript" }`

#### Scenario: Receive final transcript
- **WHEN** the cloud STT provider returns a final transcript result
- **THEN** the server SHALL send a JSON WebSocket message: `{ "type": "final", "text": "complete transcript", "cleaned": true|false }`
- **AND** the `cleaned` flag SHALL indicate whether the transcript includes built-in cleanup from the provider

#### Scenario: Stream error
- **WHEN** the cloud STT provider returns an error during streaming
- **THEN** the server SHALL send a JSON WebSocket message: `{ "type": "error", "message": "error description" }`

#### Scenario: Connection close
- **WHEN** the client closes the WebSocket connection
- **THEN** the server SHALL cleanly terminate the cloud STT provider stream
- **AND** release all associated resources

#### Scenario: Provider connection failure
- **WHEN** the server cannot connect to the cloud STT provider
- **THEN** the server SHALL send an error message and close the WebSocket connection

### Requirement: Frontend Audio Streaming
The system SHALL capture microphone audio and stream it to the backend via WebSocket.

#### Scenario: Start streaming
- **WHEN** cloud STT voice input is activated
- **THEN** the system SHALL request microphone access via `getUserMedia`
- **AND** open a WebSocket connection to `/ws/voice/stream`
- **AND** begin streaming audio chunks via the WebSocket

#### Scenario: Audio format conversion
- **WHEN** microphone audio is captured via MediaRecorder
- **THEN** the system SHALL convert audio to PCM 16-bit mono 16kHz using AudioContext
- **AND** send PCM chunks as binary WebSocket messages

#### Scenario: Chunk interval
- **WHEN** audio is being streamed
- **THEN** audio chunks SHALL be sent at intervals of 100-250ms
- **AND** chunk size SHALL be configurable

#### Scenario: WebSocket reconnection
- **WHEN** the WebSocket connection drops during streaming
- **THEN** the system SHALL attempt reconnection with exponential backoff (1s, 2s, 4s, max 3 attempts)
- **AND** display a "Reconnecting..." indicator to the user

#### Scenario: Stop streaming
- **WHEN** the user stops cloud STT voice input
- **THEN** the system SHALL stop the MediaRecorder
- **AND** close the WebSocket connection cleanly

### Requirement: Cloud STT Pipeline Step
The system SHALL register cloud STT as a configurable pipeline step in the model configuration system, with provider selection handled via the existing Model Configuration dialog.

#### Scenario: ModelStep registration
- **WHEN** the application starts
- **THEN** `CLOUD_STT` SHALL be registered in the `ModelStep` enum
- **AND** the default model SHALL be defined in `model_registry.yaml` under `default_models.cloud_stt`

#### Scenario: Model selection
- **WHEN** the cloud STT model is not explicitly configured
- **THEN** the system SHALL use the `CLOUD_STT` pipeline step default (`gemini-2.5-flash`)
- **AND** the model SHALL be overridable via env var `MODEL_CLOUD_STT`, DB override, or YAML default

#### Scenario: Settings UI display
- **WHEN** the Model Configuration section of the Settings page renders
- **THEN** `CLOUD_STT` SHALL appear as a configurable pipeline step alongside other steps
- **AND** the model selector SHALL only show models with `supports_audio: true`
- **AND** selecting a model implicitly selects its provider (no separate provider dropdown)

#### Scenario: Audio-capable model filtering
- **WHEN** the model selector for `CLOUD_STT` is displayed
- **THEN** only models with `supports_audio: true` in `model_registry.yaml` SHALL be shown
- **AND** each model option SHALL indicate its provider family (Gemini, OpenAI, Deepgram)

### Requirement: Audio Capability Indicator
The system SHALL declare audio input capability for models in the model registry, analogous to the existing `supports_video` flag.

#### Scenario: Audio capability in model registry
- **WHEN** a model supports audio input for transcription
- **THEN** its definition in `model_registry.yaml` SHALL include `supports_audio: true`
- **AND** models that do not support audio input SHALL have `supports_audio: false` (or omit the field, defaulting to `false`)

#### Scenario: ModelInfo dataclass
- **WHEN** the model registry is loaded
- **THEN** `ModelInfo` SHALL include a `supports_audio: bool` field
- **AND** the `load_model_registry()` function SHALL parse the `supports_audio` field from YAML

#### Scenario: Audio-capable models
- **WHEN** the following models are defined
- **THEN** `supports_audio` SHALL be `true` for: Gemini family models (2.0+), `whisper-1`, `deepgram-nova-3`
- **AND** `supports_audio` SHALL be `false` for: Claude family models, GPT family models

### Requirement: Built-in Cleanup Bypass
The system SHALL skip the separate `VOICE_CLEANUP` pipeline step when the cloud STT provider returns already-cleaned transcripts.

#### Scenario: Gemini returns cleaned transcript
- **WHEN** the cloud STT engine returns a final transcript with `cleaned: true`
- **THEN** the frontend SHALL insert the transcript directly without calling `POST /api/v1/voice/cleanup`
- **AND** the cleanup button SHALL remain available for manual re-cleanup if desired

#### Scenario: Whisper/Deepgram returns raw transcript
- **WHEN** the cloud STT engine returns a final transcript with `cleaned: false`
- **THEN** the frontend SHALL treat the transcript the same as browser/on-device STT output
- **AND** the user MAY trigger cleanup manually via the cleanup button or voice key phrase

#### Scenario: Cleanup button always available
- **WHEN** a cloud STT transcript is inserted (regardless of `cleaned` flag)
- **THEN** the cleanup button SHALL remain enabled
- **AND** clicking it SHALL send the text through `VOICE_CLEANUP` for additional refinement

### Requirement: Cloud STT Language Configuration
The system SHALL support language selection for cloud STT transcription.

#### Scenario: Language setting
- **WHEN** a language is configured for cloud STT
- **THEN** the language SHALL be passed to the cloud STT provider for improved accuracy

#### Scenario: Auto-detect language
- **WHEN** no language is explicitly configured
- **THEN** the system SHALL use the provider's automatic language detection
- **AND** default to `"en"` if the provider does not support auto-detection
