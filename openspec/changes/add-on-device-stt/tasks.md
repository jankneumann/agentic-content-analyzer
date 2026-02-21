## 1. STT Engine Abstraction

- [ ] 1.1 Create `web/src/lib/voice/engine.ts` with `STTEngine` interface (`start`, `stop`, `onResult`, `onError`)
- [ ] 1.2 Implement `BrowserSTTEngine` class wrapping SpeechRecognition (extract from `useVoiceInput`)
- [ ] 1.3 Implement `OnDeviceSTTEngine` class wrapping Whisper Web Worker communication
- [ ] 1.4 Implement `AutoSTTEngine` that selects browser or on-device based on availability and connectivity
- [ ] 1.5 Refactor `useVoiceInput` hook to accept `engine` option and delegate to the engine abstraction

## 2. Whisper WASM Integration

- [ ] 2.1 Add Whisper WASM dependency (`whisper-turbo` or equivalent) to `web/package.json`
- [ ] 2.2 Configure Vite to handle WASM file imports and worker bundling
- [ ] 2.3 Create `web/src/lib/voice/whisper-worker.ts` Web Worker for model loading and inference
- [ ] 2.4 Define typed message protocol between main thread and worker (`load-model`, `transcribe`, `result`, `error`, `progress`)
- [ ] 2.5 Implement model loading in worker (initialize Whisper from cached model bytes)
- [ ] 2.6 Implement audio transcription in worker (accept Float32Array, return transcript string)

## 3. Model Management

- [ ] 3.1 Create `web/src/lib/voice/model-cache.ts` with Cache API operations (`downloadModel`, `isModelCached`, `deleteModel`, `getCachedModelInfo`)
- [ ] 3.2 Implement model download with progress tracking via fetch + ReadableStream
- [ ] 3.3 Implement persistent model storage in Cache API
- [ ] 3.4 Add model size constants (tiny: 39MB, base: 74MB) and CDN URLs
- [ ] 3.5 Implement download retry logic with cleanup of partial downloads on failure

## 4. Audio Recording

- [ ] 4.1 Create `web/src/lib/voice/audio-recorder.ts` with `getUserMedia` + `MediaRecorder` wrapper
- [ ] 4.2 Implement start/stop recording with audio blob capture
- [ ] 4.3 Implement audio format conversion (MediaRecorder blob → Float32Array for Whisper)
- [ ] 4.4 Handle microphone permission denial with user-facing error message

## 5. Backend STT Settings

- [ ] 5.1 Extend `voice_settings_routes.py` to include `stt_engine` and `stt_model_size` fields
- [ ] 5.2 Add defaults: `stt_engine="auto"`, `stt_model_size="tiny"`
- [ ] 5.3 Add `PUT /api/v1/settings/voice/stt_engine` with validation (`auto`, `browser`, `on-device`)
- [ ] 5.4 Add `PUT /api/v1/settings/voice/stt_model_size` with validation (`tiny`, `base`)
- [ ] 5.5 Add corresponding `DELETE` endpoints for reset

## 6. Frontend STT Settings UI

- [ ] 6.1 Add STT Engine subsection to `VoiceConfigurator.tsx`
- [ ] 6.2 Add engine selector dropdown (Auto / Browser / On-Device)
- [ ] 6.3 Add model size selector (Tiny ~39MB / Base ~74MB)
- [ ] 6.4 Add model download button with progress bar
- [ ] 6.5 Add model status indicator (cached model name, size, delete button)
- [ ] 6.6 Wire settings to `use-settings.ts` hooks

## 7. Processing Indicator

- [ ] 7.1 Add "Processing..." state to `VoiceInputButton` (spinner animation during on-device transcription)
- [ ] 7.2 Add "Transcribing..." placeholder to input field during on-device processing
- [ ] 7.3 Replace indicator with transcript text when processing completes

## 8. Testing

- [ ] 8.1 Add unit tests for engine abstraction (mock SpeechRecognition and Whisper worker)
- [ ] 8.2 Add unit tests for model cache operations (mock Cache API)
- [ ] 8.3 Add E2E test for STT engine settings UI
- [ ] 8.4 Add E2E test for model download/delete flow (mocked)
- [ ] 8.5 Add backend tests for STT engine settings API endpoints
