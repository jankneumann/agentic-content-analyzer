# cloud-stt Specification

## Purpose
Cloud-based speech-to-text with real-time audio streaming via WebSocket, supporting multiple providers and configurable as a pipeline step.

## ADDED Requirements

### Requirement: Cloud STT Provider Abstraction
The system SHALL provide a provider abstraction for cloud-based speech-to-text services.

#### Scenario: Provider interface
- **WHEN** a cloud STT provider is implemented
- **THEN** it SHALL implement the `CloudSTTProvider` interface with methods: `start_stream()`, `send_audio(chunk)`, `get_results()`, `stop_stream()`
- **AND** it SHALL normalize provider-specific response formats into a common transcript result structure

#### Scenario: OpenAI Whisper provider
- **WHEN** the cloud STT provider is set to `"openai"`
- **THEN** the system SHALL use the OpenAI Whisper API for transcription
- **AND** use the configured `OPENAI_API_KEY`

#### Scenario: Deepgram provider
- **WHEN** the cloud STT provider is set to `"deepgram"`
- **THEN** the system SHALL use the Deepgram streaming API for transcription
- **AND** use the configured `DEEPGRAM_API_KEY`

#### Scenario: Google Cloud Speech provider
- **WHEN** the cloud STT provider is set to `"google"`
- **THEN** the system SHALL use the Google Cloud Speech-to-Text streaming API
- **AND** use the configured Google Cloud credentials

#### Scenario: Provider not configured
- **WHEN** the selected cloud STT provider has no API key configured
- **THEN** the system SHALL return an error indicating the provider requires configuration
- **AND** the voice settings UI SHALL show the provider as `not_configured`

### Requirement: WebSocket Audio Streaming Endpoint
The system SHALL provide a WebSocket endpoint for real-time audio streaming and transcript delivery.

#### Scenario: WebSocket connection
- **WHEN** a client connects to `ws://{host}/ws/voice/stream`
- **THEN** the server SHALL authenticate the connection via `X-Admin-Key` in the initial handshake query params
- **AND** establish a streaming session with the configured cloud STT provider

#### Scenario: Authentication required
- **WHEN** a WebSocket connection is attempted without a valid `X-Admin-Key`
- **THEN** the server SHALL reject the connection with a 401 close code

#### Scenario: Send audio chunk
- **WHEN** the client sends a binary WebSocket message containing audio data (PCM 16-bit mono 16kHz)
- **THEN** the server SHALL forward the audio chunk to the cloud STT provider's streaming API

#### Scenario: Receive interim transcript
- **WHEN** the cloud STT provider returns an interim (non-final) transcript result
- **THEN** the server SHALL send a JSON WebSocket message: `{ "type": "interim", "text": "partial transcript" }`

#### Scenario: Receive final transcript
- **WHEN** the cloud STT provider returns a final transcript result
- **THEN** the server SHALL send a JSON WebSocket message: `{ "type": "final", "text": "complete transcript" }`

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
The system SHALL register cloud STT as a configurable pipeline step in the model configuration system.

#### Scenario: ModelStep registration
- **WHEN** the application starts
- **THEN** `CLOUD_STT` SHALL be registered in the `ModelStep` enum
- **AND** the default model SHALL be defined in `model_registry.yaml` under `default_models.cloud_stt`

#### Scenario: Model selection
- **WHEN** the cloud STT provider/model is not explicitly configured
- **THEN** the system SHALL use the `CLOUD_STT` pipeline step default (e.g., `whisper-1` for OpenAI)
- **AND** the model SHALL be overridable via env var `MODEL_CLOUD_STT`, DB override, or YAML default

#### Scenario: Settings UI display
- **WHEN** the Model Configuration section of the Settings page renders
- **THEN** `CLOUD_STT` SHALL appear as a configurable pipeline step
- **AND** available models SHALL be listed per the configured provider

### Requirement: Cloud STT Language Configuration
The system SHALL support language selection for cloud STT transcription.

#### Scenario: Language setting
- **WHEN** a language is configured for cloud STT
- **THEN** the language SHALL be passed to the cloud STT provider for improved accuracy

#### Scenario: Auto-detect language
- **WHEN** no language is explicitly configured
- **THEN** the system SHALL use the provider's automatic language detection
- **AND** default to `"en"` if the provider does not support auto-detection
