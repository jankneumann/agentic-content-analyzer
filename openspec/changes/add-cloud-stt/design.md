## Context

The voice input system has three existing engine options: `"browser"` (Web Speech API), `"on-device"` (Whisper WASM), and `"native"` (Capacitor plugin). Each has trade-offs:

| Engine | Accuracy | Latency | Privacy | Offline | Browser Support |
|--------|----------|---------|---------|---------|-----------------|
| Browser | Good | Real-time | Low (Google) | No | Chrome/Edge/Safari |
| On-device | Moderate | 1-5s batch | High | Yes | All |
| Native | Good | Real-time | Moderate | Partial | Capacitor only |
| **Cloud** | **Best** | **Real-time** | **Low** | **No** | **All** |

Cloud STT fills the gap for users who want the highest accuracy with real-time streaming and don't mind sending audio to a provider they control (and pay for). Unlike the Web Speech API (which silently uses Google), cloud STT lets users choose their provider and manage their own API keys.

Key existing touchpoints:
- `STTEngine` interface (from `add-on-device-stt`) — the engine abstraction
- `useVoiceInput` hook — consumes engines, manages transcript state
- Voice settings routes — 3-tier config (env → db → default)
- `ModelStep` enum / `model_registry.yaml` — pipeline step configuration
- `src/api/app.py` — FastAPI app with WebSocket support available

## Goals / Non-Goals

**Goals:**
- Add real-time audio streaming from browser to backend via WebSocket
- Support multiple cloud STT providers (OpenAI Whisper, Google Cloud Speech, Deepgram)
- Provide interim transcript results with <500ms latency
- Make cloud STT a configurable pipeline step (provider/model selection in settings UI)
- Integrate cleanly with the existing engine abstraction (`STTEngine` interface)

**Non-Goals:**
- Speaker diarization (future enhancement per provider capability)
- Custom vocabulary / phrase boosting (provider-specific, defer to future)
- Audio recording/playback (only streaming transcription)
- Replacing existing engines — cloud is additive, not a replacement
- Client-side audio processing (noise cancellation, VAD) — rely on provider-side

## Decisions

### 1. WebSocket for audio streaming (not REST)

**Choice**: Add a `ws://` endpoint at `/ws/voice/stream` that accepts audio chunks and streams transcript results back in real-time.

**Alternatives considered**:
- **REST batch upload**: Simple but adds 1-5s latency per utterance. Defeats the purpose of real-time streaming.
- **Server-Sent Events (SSE)**: One-directional (server → client). Can't stream audio client → server.
- **WebRTC**: Overkill for single-direction audio. Complex NAT traversal, unnecessary for server-mediated flow.

**Rationale**: WebSocket is the natural fit for bidirectional streaming: audio chunks flow client → server, transcript results flow server → client. FastAPI supports WebSocket endpoints natively. All target browsers support WebSocket. The on-device STT change already uses MediaRecorder for audio capture — we reuse that, but instead of sending blobs to a Web Worker, we stream chunks over WebSocket.

### 2. Backend proxy architecture (not direct client → provider)

**Choice**: Audio streams from browser → backend WebSocket → cloud provider API. The backend proxies the audio and manages the provider connection.

**Alternatives considered**:
- **Direct client → provider**: Lower latency but exposes API keys in the browser, requires CORS, and different providers have incompatible streaming protocols.

**Rationale**: The backend proxy keeps API keys server-side (security), normalizes provider differences behind a single WebSocket protocol (simplicity), and enables server-side logging/metrics (observability). The ~10-20ms proxy overhead is negligible compared to provider processing time.

### 3. Provider abstraction with factory pattern

**Choice**: Define a `CloudSTTProvider` interface with `start_stream()`, `send_audio()`, `get_results()`, `stop_stream()` methods. Implement per provider (OpenAI, Google, Deepgram). Use factory pattern matching the existing `TTS_PROVIDERS` pattern in `tts_service.py`.

**Rationale**: Follows the project's existing provider patterns (database providers, storage providers, TTS providers). Adding a new provider means implementing one class, no changes to the WebSocket endpoint.

### 4. OpenAI Whisper API as default provider

**Choice**: Default to OpenAI Whisper API since the project already has `openai` SDK installed and `OPENAI_API_KEY` is commonly configured for TTS.

**Alternatives considered**:
- **Deepgram**: Best real-time streaming support and lowest cost ($0.0043/min), but requires a separate API key. Excellent choice as second provider.
- **Google Cloud Speech-to-Text**: Strong multi-language, but more complex auth (service account JSON vs API key).

**Rationale**: OpenAI Whisper shares the existing `OPENAI_API_KEY`, so users who already have TTS configured get cloud STT with zero additional setup. Deepgram is offered as an optional provider for users who want lower cost or better streaming.

### 5. CLOUD_STT as a pipeline step in ModelConfig

**Choice**: Register `CLOUD_STT` in the `ModelStep` enum and `model_registry.yaml`, using the same 3-tier precedence as other steps.

**Rationale**: Matches the `VOICE_CLEANUP` pattern from `add-voice-input`. Users can select the cloud STT provider/model via the Model Configuration section in Settings. The env var `MODEL_CLOUD_STT` provides deployment-level control.

### 6. Audio format: PCM 16-bit mono 16kHz

**Choice**: Capture audio as PCM 16-bit mono at 16kHz sample rate. Convert from MediaRecorder's default format (typically opus/webm) using AudioContext.

**Rationale**: PCM 16kHz is the universal format accepted by all cloud STT providers. Some providers accept opus/webm directly, but PCM eliminates format negotiation complexity.

## Risks / Trade-offs

- **WebSocket connection management**: Reconnection on network drops, handling multiple concurrent sessions. → Mitigated by automatic reconnection with exponential backoff; single session per user.
- **Audio streaming privacy**: Audio is sent to a third-party cloud provider. → Documented clearly in settings UI; users can choose on-device STT for privacy.
- **Cost per minute**: Cloud STT charges per audio minute. → Show cost estimate in settings; default to cheaper providers; users opt in explicitly.
- **Provider API differences**: Each provider has different streaming protocols and response formats. → Normalized behind `CloudSTTProvider` interface; provider-specific adapters.
- **Backend WebSocket scaling**: Each streaming session holds a WebSocket connection. → Acceptable for single-user deployment; for multi-user, consider connection pooling.
- **Audio format conversion overhead**: Converting MediaRecorder output to PCM in the browser. → AudioContext processing is lightweight; runs in main thread with negligible CPU impact.

## Open Questions

- Should the WebSocket endpoint require authentication (API key in query params or initial handshake)? (Leaning: yes, use `X-Admin-Key` in the WebSocket handshake.)
- Should we support Deepgram as the default instead of OpenAI for better real-time streaming? (Leaning: OpenAI default for zero-config, Deepgram as recommended alternative.)
