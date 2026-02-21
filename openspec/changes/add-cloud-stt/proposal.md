## Why

The existing voice input proposals cover browser-native STT (Web Speech API) and on-device STT (Whisper WASM), but both have limitations: the Web Speech API only works online in Chrome and offers no provider choice, while on-device Whisper has higher latency and limited accuracy compared to cloud services. Google Gemini Flash 3.0 with native audio input can transcribe *and* clean up speech in a single API call — combining what currently takes two steps (STT + VOICE_CLEANUP) into one, with better accuracy because the model hears the original audio rather than working from lossy text. Alternative providers (OpenAI Whisper, Deepgram) are supported for users who prefer raw transcripts or specific streaming behavior.

## What Changes

- Add a cloud STT engine abstraction supporting multiple providers (Gemini default, OpenAI Whisper, Deepgram)
- Implement real-time audio streaming from browser to backend via WebSocket, enabling low-latency interim results
- Add a backend WebSocket endpoint that proxies audio chunks to the configured cloud STT provider and streams transcript results back
- Implement MediaRecorder-based audio capture on the frontend that streams chunks via WebSocket (not batch upload)
- Add `supports_audio` capability indicator to model definitions in `model_registry.yaml` (analogous to `supports_video`)
- Register `CLOUD_STT` as a pipeline step in the model configuration system — provider selection is implicit via model family (Gemini model → Gemini API, OpenAI model → Whisper API, etc.), displayed in the existing Model Configuration dialog alongside other steps
- Extend the voice input engine abstraction (from `add-on-device-stt`) with a `"cloud"` engine option
- Update `"auto"` engine selection to support a configurable preference order (e.g., cloud → browser → on-device)

## Capabilities

### New Capabilities
- `cloud-stt`: Cloud-based speech-to-text with real-time audio streaming via WebSocket, supporting multiple providers (Gemini default with built-in cleanup, OpenAI Whisper, Deepgram), configurable as a pipeline step

### Modified Capabilities
- `voice-input`: Add `"cloud"` engine option and configurable engine preference order in `"auto"` mode
- `settings-management`: Add cloud STT language and engine preference order to voice settings (provider/model selection handled via Model Configuration dialog)

## Impact

- **Frontend**: MediaRecorder → WebSocket streaming, new engine class, cloud STT model selection via existing Model Configuration dialog
- **Backend**: New WebSocket endpoint (`/ws/voice/stream`), cloud STT provider abstraction, API key management
- **Dependencies**: Provider SDKs — `google-generativeai` (already installed for YouTube), `openai` (already installed), `deepgram-sdk` (optional)
- **APIs**: New WebSocket endpoint for audio streaming; cloud STT language/engine settings; `supports_audio` model capability flag
- **Cost**: Gemini Flash ~$0.10/hr audio (with built-in cleanup); OpenAI Whisper $0.36/hr; Deepgram $0.26/hr
- **Latency**: Real-time streaming provides ~200-500ms interim results vs 1-5s batch with on-device
- **Privacy**: Audio is sent to cloud provider — users who need privacy should use on-device STT instead
