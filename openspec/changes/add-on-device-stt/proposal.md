## Why

The `add-voice-input` change uses the Web Speech API, which requires an internet connection (Chrome sends audio to Google's servers) and is unavailable on Firefox. On-device STT provides a fully private, offline-capable alternative using WebAssembly-compiled speech recognition models (Whisper.cpp via WASM or Transformers.js). This enables voice input for privacy-conscious users, offline scenarios, and unsupported browsers — while also being the foundation for native STT in the Capacitor and Tauri proposals.

## What Changes

- Add an on-device STT engine abstraction layer that can load and run WASM/WebGPU speech models in the browser
- Integrate Whisper.cpp (via whisper-turbo or whisper.cpp WASM builds) as the primary on-device engine
- Add a model download and caching system using the Cache API / IndexedDB for persistent model storage
- Implement a Web Worker-based transcription pipeline to keep the UI thread responsive
- Extend the `useVoiceInput` hook (from `add-voice-input`) with an `engine` option: `"browser"` (Web Speech API) or `"on-device"` (WASM Whisper)
- Add audio recording via MediaRecorder API for capturing microphone input to feed the on-device engine
- Add STT engine settings to the voice configuration (engine preference, model size, auto-detect)
- Provide automatic engine fallback: prefer Web Speech API when available, fall back to on-device when offline or unsupported

## Capabilities

### New Capabilities
- `on-device-stt`: On-device speech-to-text using WebAssembly/WebGPU compiled models, including model management, audio recording, Web Worker transcription, and engine abstraction

### Modified Capabilities
- `voice-input`: Add engine selection (`browser` vs `on-device`) and automatic fallback logic to the voice input hook
- `settings-management`: Add STT engine preferences (engine choice, model size, auto-download) to voice settings

## Impact

- **Frontend**: New Web Worker for transcription, MediaRecorder integration, model download UI, ~40-80MB model download on first use (cached thereafter)
- **Backend**: Minor settings extension (same pattern as voice input settings)
- **Dependencies**: `@anthropic-ai/whisper-wasm` or `@nicktomlin/whisper-turbo` (WASM build), or `@huggingface/transformers` (Transformers.js with WebGPU)
- **Performance**: WebGPU path gives near-real-time; WASM fallback is ~2-5x slower but universally supported
- **Storage**: 40MB (tiny model) to 500MB (base model) cached in browser
- **Browser support**: All modern browsers (Chrome, Firefox, Safari, Edge) — fills the Firefox gap from `add-voice-input`
