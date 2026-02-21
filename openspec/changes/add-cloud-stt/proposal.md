## Why

The existing voice input proposals cover browser-native STT (Web Speech API) and on-device STT (Whisper WASM), but both have limitations: the Web Speech API only works online in Chrome and offers no provider choice, while on-device Whisper has higher latency and limited accuracy compared to cloud services. Cloud STT providers (OpenAI Whisper API, Google Cloud Speech-to-Text, Deepgram, AssemblyAI) offer superior accuracy, real-time audio streaming, speaker diarization, and multi-language support — critical for power users who need high-fidelity transcription. Adding configurable cloud STT as another engine option gives users the flexibility to choose their accuracy/privacy/cost trade-off.

## What Changes

- Add a cloud STT engine abstraction supporting multiple providers (OpenAI Whisper API, Google Cloud Speech-to-Text, Deepgram)
- Implement real-time audio streaming from browser to backend via WebSocket, enabling low-latency interim results
- Add a backend WebSocket endpoint that proxies audio chunks to the configured cloud STT provider and streams transcript results back
- Implement MediaRecorder-based audio capture on the frontend that streams chunks via WebSocket (not batch upload)
- Add cloud STT provider configuration to the settings system (provider, API key, language, model variant)
- Register `CLOUD_STT` as a pipeline step in the model configuration system for provider/model selection
- Extend the voice input engine abstraction (from `add-on-device-stt`) with a `"cloud"` engine option
- Update `"auto"` engine selection to support a configurable preference order (e.g., cloud → browser → on-device)

## Capabilities

### New Capabilities
- `cloud-stt`: Cloud-based speech-to-text with real-time audio streaming via WebSocket, supporting multiple providers (OpenAI, Google, Deepgram), configurable as a pipeline step

### Modified Capabilities
- `voice-input`: Add `"cloud"` engine option and configurable engine preference order in `"auto"` mode
- `settings-management`: Add cloud STT provider configuration (provider, API key, language, model variant) to voice settings

## Impact

- **Frontend**: MediaRecorder → WebSocket streaming, new engine class, settings UI for cloud STT provider
- **Backend**: New WebSocket endpoint (`/ws/voice/stream`), cloud STT provider abstraction, API key management
- **Dependencies**: Provider SDKs — `openai` (already installed), `google-cloud-speech`, `deepgram-sdk` (optional)
- **APIs**: New WebSocket endpoint for audio streaming; extended voice settings for cloud STT config
- **Cost**: Per-minute cloud STT pricing ($0.006/min OpenAI, $0.016/min Google, $0.0043/min Deepgram)
- **Latency**: Real-time streaming provides ~200-500ms interim results vs 1-5s batch with on-device
- **Privacy**: Audio is sent to cloud provider — users who need privacy should use on-device STT instead
