## Context

The `add-voice-input` change provides browser-native STT via the Web Speech API, but it has two gaps: no Firefox support and no offline capability (Chrome sends audio to Google's servers). On-device STT fills both gaps by running a Whisper model directly in the browser via WebAssembly or WebGPU. The existing `useVoiceInput` hook needs an engine abstraction so both backends can be swapped transparently.

Key constraints:
- Model files are 40-500MB — must be downloaded once and cached persistently
- Transcription is CPU/GPU intensive — must run in a Web Worker to avoid blocking the UI
- WebGPU is faster but not universally available — WASM is the universal fallback
- The `voice-input` hook already handles transcript state, error handling, and UI integration — this change adds an alternative audio source and transcription backend

## Goals / Non-Goals

**Goals:**
- Provide offline-capable, private STT that works in all modern browsers (including Firefox)
- Run transcription in a Web Worker so the UI remains responsive
- Cache models persistently so the download cost is paid once
- Integrate cleanly with the existing `useVoiceInput` hook via an engine abstraction
- Expose engine preference and model size in the settings UI

**Non-Goals:**
- Real-time streaming transcription (Whisper processes audio in chunks; near-real-time is fine)
- Server-side Whisper inference (all processing stays in-browser)
- Training or fine-tuning models
- Supporting models larger than `base` (244M params) — `small`/`medium`/`large` are too slow for browser use
- Speaker diarization or multi-speaker separation

## Decisions

### 1. Whisper.cpp WASM as primary engine

**Choice**: Use a Whisper.cpp WebAssembly build (via `whisper-turbo` or `@nicktomlin/whisper.cpp`) with optional WebGPU acceleration.

**Alternatives considered**:
- **Transformers.js (Hugging Face)**: Good WebGPU support via ONNX Runtime Web, but larger bundle and more complex initialization. Better suited for a future upgrade if WebGPU adoption increases.
- **Vosk (WASM)**: Lighter models (~50MB), supports streaming, but lower accuracy than Whisper for English dictation.
- **Mozilla DeepSpeech**: Deprecated, no longer maintained.

**Rationale**: Whisper.cpp has the best accuracy-to-size ratio for dictation, mature WASM builds, and the community is actively maintaining browser-compatible builds. WebGPU acceleration is available for Chrome/Edge, with WASM fallback for Firefox/Safari.

### 2. Web Worker for transcription

**Choice**: Run all Whisper model loading and inference in a dedicated Web Worker. Communication via `postMessage` with typed messages.

**Rationale**: Whisper inference on a 40MB model takes 1-5 seconds per utterance (WASM). Running on the main thread would freeze the UI. A Web Worker isolates this completely. The worker loads the model once and keeps it in memory for subsequent transcriptions.

### 3. MediaRecorder for audio capture

**Choice**: Use `navigator.mediaDevices.getUserMedia()` + `MediaRecorder` API to capture microphone audio, then pass audio buffers to the Web Worker.

**Alternatives considered**:
- **AudioWorklet**: Lower-level, provides raw PCM samples in real-time. More complex but enables streaming transcription. Overkill for chunk-based Whisper.
- **ScriptProcessorNode**: Deprecated, replaced by AudioWorklet.

**Rationale**: MediaRecorder is the simplest API for capturing audio blobs. Whisper processes complete audio segments, so the chunk-based model of MediaRecorder (capture → stop → send blob to worker) aligns naturally.

### 4. Cache API for model storage

**Choice**: Store downloaded GGML model files in the browser's Cache API (via `caches.open()`).

**Alternatives considered**:
- **IndexedDB**: Works but has more complex API and 50MB+ blob storage can be slow on some browsers.
- **Origin Private File System (OPFS)**: Best performance for large files but limited browser support.

**Rationale**: Cache API is designed for large binary assets, has wide browser support, and integrates naturally with service workers for the existing PWA infrastructure.

### 5. Engine abstraction in useVoiceInput

**Choice**: Add an `engine` option to `useVoiceInput`: `"browser"` (Web Speech API), `"on-device"` (Whisper WASM), or `"auto"` (prefer browser, fallback to on-device).

**Rationale**: Clean separation — the hook's consumers (ChatInput, search) don't need to know which engine is active. The `auto` mode provides the best default experience: fast cloud STT when available, private on-device when not.

## Risks / Trade-offs

- **Initial model download size (~40-80MB for tiny/base)**: → Mitigated by download progress UI, persistent caching, and making download opt-in (user must enable on-device STT in settings).
- **Transcription latency (1-5s per utterance on WASM)**: → Mitigated by showing a "Processing..." indicator. WebGPU path reduces this to <1s. Acceptable for non-real-time dictation.
- **WebGPU availability (~70% of users)**: → WASM fallback is universal. WebGPU is an optional acceleration, not a requirement.
- **Memory usage (~200-500MB during inference)**: → Only tiny/base models supported in-browser. Settings show memory estimate before download.
- **Browser storage quotas**: → Cache API has generous limits (typically 50% of disk space). Model download UI warns if storage is low.
- **WASM build compatibility**: → Pin specific versions of whisper-turbo. Test across Chrome, Firefox, Safari.

## Open Questions

- Should model download happen automatically on first voice input attempt, or require explicit user action in settings? (Leaning: explicit — users should consent to a 40MB download.)
- Should we support the `tiny` model only initially (39MB, fastest, lower accuracy) or also offer `base` (74MB, better accuracy)? (Leaning: offer both, default to `tiny`.)
