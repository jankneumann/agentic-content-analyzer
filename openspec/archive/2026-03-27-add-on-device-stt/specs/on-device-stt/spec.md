# on-device-stt Specification

## Purpose
On-device speech-to-text using WebAssembly/WebGPU compiled Whisper models, enabling private, offline-capable voice input in all modern browsers.

## ADDED Requirements

### Requirement: STT Engine Abstraction
The system SHALL provide an engine abstraction that allows switching between Web Speech API and on-device Whisper STT transparently.

#### Scenario: Browser engine selection
- **WHEN** the voice input engine is set to `"browser"`
- **THEN** the system SHALL use the Web Speech API for speech recognition
- **AND** behave identically to the base `add-voice-input` implementation

#### Scenario: On-device engine selection
- **WHEN** the voice input engine is set to `"on-device"`
- **THEN** the system SHALL use the Whisper WASM/WebGPU engine for speech recognition
- **AND** all audio processing SHALL occur locally in the browser

#### Scenario: Auto engine selection
- **WHEN** the voice input engine is set to `"auto"` (default)
- **AND** the Web Speech API is available and the device is online
- **THEN** the system SHALL use the `"browser"` engine

#### Scenario: Auto engine fallback
- **WHEN** the voice input engine is set to `"auto"`
- **AND** the Web Speech API is unavailable OR the device is offline
- **AND** an on-device model is cached
- **THEN** the system SHALL fall back to the `"on-device"` engine

#### Scenario: No engine available
- **WHEN** the voice input engine is set to `"auto"`
- **AND** the Web Speech API is unavailable
- **AND** no on-device model is cached
- **THEN** voice input SHALL be disabled with a message prompting the user to download an on-device model

### Requirement: Whisper Model Management
The system SHALL manage downloading, caching, and loading Whisper GGML model files.

#### Scenario: Download model
- **WHEN** the user initiates a model download from the settings UI
- **THEN** the system SHALL download the selected model (tiny or base) from a CDN
- **AND** display a progress bar showing download percentage
- **AND** store the model in the Cache API upon completion

#### Scenario: Model already cached
- **WHEN** a model download is requested
- **AND** the model is already present in the Cache API
- **THEN** the system SHALL skip the download and report the model as ready

#### Scenario: Delete cached model
- **WHEN** the user requests model deletion from the settings UI
- **THEN** the system SHALL remove the model from the Cache API
- **AND** update the UI to show no model is available

#### Scenario: Model size information
- **WHEN** the model download UI is displayed
- **THEN** it SHALL show the model name, file size, and estimated memory usage
- **AND** the tiny model SHALL be listed as ~39MB download / ~200MB memory
- **AND** the base model SHALL be listed as ~74MB download / ~500MB memory

#### Scenario: Download failure
- **WHEN** a model download fails due to network error
- **THEN** the system SHALL display an error message
- **AND** allow the user to retry the download
- **AND** clean up any partial download data

### Requirement: Web Worker Transcription
The system SHALL run Whisper model inference in a dedicated Web Worker to prevent UI thread blocking.

#### Scenario: Worker initialization
- **WHEN** on-device STT is activated for the first time
- **THEN** the system SHALL spawn a Web Worker
- **AND** load the cached Whisper model into the worker's memory

#### Scenario: Transcribe audio
- **WHEN** an audio buffer is sent to the Web Worker
- **THEN** the worker SHALL run Whisper inference on the audio
- **AND** return the transcription result via `postMessage`

#### Scenario: Worker keeps model loaded
- **WHEN** the first transcription completes
- **THEN** the worker SHALL keep the model in memory
- **AND** subsequent transcriptions SHALL not require re-loading the model

#### Scenario: Worker error handling
- **WHEN** the Web Worker encounters an error during inference
- **THEN** it SHALL send an error message back to the main thread
- **AND** the error SHALL be displayed to the user via toast notification

### Requirement: Audio Recording
The system SHALL capture microphone audio using the MediaRecorder API for on-device transcription.

#### Scenario: Start recording
- **WHEN** on-device voice input is activated
- **THEN** the system SHALL request microphone access via `getUserMedia`
- **AND** start a MediaRecorder to capture audio

#### Scenario: Stop recording and transcribe
- **WHEN** the user stops on-device voice input
- **THEN** the MediaRecorder SHALL stop
- **AND** the captured audio blob SHALL be sent to the Web Worker for transcription
- **AND** a "Processing..." indicator SHALL be shown until the result arrives

#### Scenario: Microphone permission denied
- **WHEN** `getUserMedia` is denied by the user
- **THEN** the system SHALL display an error explaining microphone permission is required
- **AND** voice input SHALL not start

### Requirement: Transcription Progress Indicator
The system SHALL show a processing indicator while on-device transcription is in progress.

#### Scenario: Processing state
- **WHEN** audio has been sent to the Web Worker for transcription
- **AND** the result has not yet returned
- **THEN** the voice input button SHALL show a processing/spinner animation
- **AND** the associated input field SHALL show a "Transcribing..." placeholder

#### Scenario: Processing complete
- **WHEN** the Web Worker returns a transcription result
- **THEN** the processing indicator SHALL be replaced with the transcript text
- **AND** the transcript SHALL be inserted into the target input field
