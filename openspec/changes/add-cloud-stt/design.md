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
- Support multiple cloud STT providers (Gemini, OpenAI Whisper, Deepgram)
- Provide interim transcript results with <500ms latency
- Return clean, structured text directly from cloud STT (built-in cleanup via transcription prompt) — bypassing the separate `VOICE_CLEANUP` step
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

### 4. Gemini Flash 3.0 as default provider with built-in cleanup

**Choice**: Default to Google Gemini Flash 3.0's native audio input. The transcription prompt includes cleanup instructions (fix grammar, remove filler words, structure text), so cloud STT returns clean text in a single API call — bypassing the separate `VOICE_CLEANUP` pipeline step entirely.

**Alternatives considered**:
- **OpenAI Whisper API + separate VOICE_CLEANUP**: Whisper is purpose-built for STT, but requires two sequential API calls (transcription + LLM cleanup). Higher latency, higher cost (~$0.36/hr Whisper + cleanup tokens), and loses audio context after the STT step — the cleanup LLM only sees lossy text.
- **Deepgram**: Best real-time streaming support and lowest cost ($0.0043/min), but no built-in cleanup — would still need the `VOICE_CLEANUP` step. Offered as an alternative provider for users who want raw transcripts or lower cost.
- **Google Cloud Speech-to-Text**: Strong multi-language but more complex auth (service account JSON). No built-in cleanup.

**Rationale**: Gemini Flash 3.0 with native audio input is strictly superior for the combined transcription+cleanup use case:
- **Single API call**: ~200-500ms for transcription + cleanup vs ~2-4s for Whisper + separate LLM call
- **Audio context preserved**: Gemini "hears" the audio — can distinguish meaningful pauses from filler, understand emphasis and tone — producing better cleanup than a text-only LLM working from lossy STT output
- **Cost**: ~$0.10/hr audio input + negligible output tokens vs ~$0.36/hr for Whisper + cleanup tokens
- **Already in stack**: The project uses Gemini for YouTube video processing (`MODEL_YOUTUBE_PROCESSING`), so the API key and SDK are already configured
- **The separate `VOICE_CLEANUP` step remains valuable** for browser STT (Web Speech API) and on-device STT (Whisper WASM), which return raw transcripts without cleanup

OpenAI Whisper and Deepgram are offered as alternative providers for users who prefer raw transcripts, need specific streaming behavior, or already have those API keys configured.

### 5. CLOUD_STT as a pipeline step — provider selection via ModelStep config dialog

**Choice**: Register `CLOUD_STT` in the `ModelStep` enum and `model_registry.yaml` with `gemini-2.5-flash` as the default, using the same 3-tier precedence as other steps. The cloud STT provider is determined implicitly by the model family — selecting a Gemini model uses the Gemini API, selecting `whisper-1` uses the OpenAI API, selecting `deepgram-nova-3` uses the Deepgram API. There is no separate "cloud STT provider" setting. Provider/model selection happens in the existing Model Configuration dialog alongside all other pipeline steps.

**Alternatives considered**:
- **Separate `voice.cloud_stt_provider` setting with its own UI selector**: Introduces a parallel provider selection mechanism outside the ModelStep system, duplicating configuration concerns and fragmenting the UX.

**Rationale**: Every other pipeline step (summarization, theme analysis, YouTube processing, etc.) uses the same ModelStep config dialog for model selection. Cloud STT should be no different. The factory pattern maps model family → provider adapter: `gemini` family → `GeminiSTTProvider`, `whisper` family → `WhisperSTTProvider`, `deepgram` family → `DeepgramSTTProvider`. Only models with `supports_audio: true` are shown as options for the CLOUD_STT step. The env var `MODEL_CLOUD_STT` provides deployment-level control. Switching providers is a one-dropdown change in the Model Configuration dialog.

### 5a. `supports_audio` capability indicator in model registry

**Choice**: Add a `supports_audio: boolean` field to model definitions in `model_registry.yaml`, analogous to the existing `supports_video` field. This flag indicates whether a model can accept audio input for transcription.

**Rationale**: The model registry already uses capability flags (`supports_vision`, `supports_video`) to indicate what input modalities a model supports. Audio input is a distinct capability — only certain models (Gemini with native audio, Whisper, Deepgram) can accept raw audio. The CLOUD_STT pipeline step uses this flag to filter the model selector to only show audio-capable models. The `ModelInfo` dataclass and `load_model_registry()` parser gain a `supports_audio` field following the exact pattern of `supports_video`.

### 6. Cloud STT bypasses VOICE_CLEANUP step

**Choice**: When the cloud STT engine is active and the provider supports built-in cleanup (Gemini), the transcript is returned already cleaned. The frontend skips the separate `VOICE_CLEANUP` API call. The cleanup button in ChatInput remains available for manual re-cleanup if the user wants to refine further.

**Alternatives considered**:
- **Always run VOICE_CLEANUP regardless of engine**: Consistent behavior, but adds 1-3s latency and cost for no quality benefit when Gemini already cleaned the text.
- **Remove VOICE_CLEANUP entirely**: Too aggressive — browser STT and on-device STT still produce raw transcripts that benefit from separate cleanup.

**Rationale**: The `CloudSTTEngine` returns a `{ cleaned: boolean }` flag alongside the transcript. When `cleaned: true`, the frontend knows to skip the automatic cleanup step. Users can still manually trigger cleanup via the sparkle button if they want to refine further.

### 7. Audio format: PCM 16-bit mono 16kHz

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
- Should providers that don't support built-in cleanup (Deepgram, Whisper) auto-trigger the `VOICE_CLEANUP` step, or let the user decide? (Leaning: auto-trigger when available, with a setting to disable.)
