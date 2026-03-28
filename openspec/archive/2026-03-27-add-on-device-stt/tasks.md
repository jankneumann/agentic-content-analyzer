## 1. STT Engine Abstraction

- [x] 1.1 Create `web/src/lib/voice/engine.ts` with `STTEngine` interface (`start`, `stop`, `onResult`, `onError`)
- [x] 1.2 Implement `BrowserSTTEngine` class wrapping SpeechRecognition (extract from `useVoiceInput`)
- [x] 1.3 Implement `OnDeviceSTTEngine` class wrapping Whisper Web Worker communication
- [x] 1.4 Implement `AutoSTTEngine` that selects browser or on-device based on availability and connectivity
- [x] 1.5 Refactor `useVoiceInput` hook to accept `engine` option and delegate to the engine abstraction

## 2. Whisper WASM Integration

- [x] 2.1 Add Whisper WASM dependency (`whisper-turbo` or equivalent) to `web/package.json`
- [x] 2.2 Configure Vite to handle WASM file imports and worker bundling
- [x] 2.3 Create `web/src/lib/voice/whisper-worker.ts` Web Worker for model loading and inference
- [x] 2.4 Define typed message protocol between main thread and worker (`load-model`, `transcribe`, `result`, `error`, `progress`)
- [x] 2.5 Implement model loading in worker (initialize Whisper from cached model bytes)
- [x] 2.6 Implement audio transcription in worker (accept Float32Array, return transcript string)

## 3. Model Management

- [x] 3.1 Create `web/src/lib/voice/model-cache.ts` with Cache API operations (`downloadModel`, `isModelCached`, `deleteModel`, `getCachedModelInfo`)
- [x] 3.2 Implement model download with progress tracking via fetch + ReadableStream
- [x] 3.3 Implement persistent model storage in Cache API
- [x] 3.4 Add model size constants (tiny: 39MB, base: 74MB) and CDN URLs
- [x] 3.5 Implement download retry logic with cleanup of partial downloads on failure

## 4. Audio Recording

- [x] 4.1 Create `web/src/lib/voice/audio-recorder.ts` with `getUserMedia` + `MediaRecorder` wrapper
- [x] 4.2 Implement start/stop recording with audio blob capture
- [x] 4.3 Implement audio format conversion (MediaRecorder blob → Float32Array for Whisper)
- [x] 4.4 Handle microphone permission denial with user-facing error message

## 5. Backend STT Settings

- [x] 5.1 Extend `voice_settings_routes.py` to include `stt_engine` and `stt_model_size` fields
- [x] 5.2 Add defaults: `stt_engine="auto"`, `stt_model_size="tiny"`
- [x] 5.3 Add `PUT /api/v1/settings/voice/stt_engine` with validation (`auto`, `browser`, `on-device`)
- [x] 5.4 Add `PUT /api/v1/settings/voice/stt_model_size` with validation (`tiny`, `base`)
- [x] 5.5 Add corresponding `DELETE` endpoints for reset

## 6. Frontend STT Settings UI

- [x] 6.1 Add STT Engine subsection to `VoiceConfigurator.tsx`
- [x] 6.2 Add engine selector dropdown (Auto / Browser / On-Device)
- [x] 6.3 Add model size selector (Tiny ~39MB / Base ~74MB)
- [x] 6.4 Add model download button with progress bar
- [x] 6.5 Add model status indicator (cached model name, size, delete button)
- [x] 6.6 Wire settings to `use-settings.ts` hooks

## 7. Processing Indicator

- [x] 7.1 Add "Processing..." state to `VoiceInputButton` (spinner animation during on-device transcription)
- [x] 7.2 Add "Transcribing..." placeholder to input field during on-device processing
- [x] 7.3 Replace indicator with transcript text when processing completes

## 8. Testing

- [x] 8.1 Add unit tests for engine abstraction (mock SpeechRecognition and Whisper worker)
- [x] 8.2 Add unit tests for model cache operations (mock Cache API)
- [x] 8.3 Add E2E test for STT engine settings UI
- [x] 8.4 Add E2E test for model download/delete flow (mocked)
- [x] 8.5 Add backend tests for STT engine settings API endpoints
