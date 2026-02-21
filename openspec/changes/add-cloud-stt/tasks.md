## 1. Cloud STT Provider Abstraction

- [ ] 1.1 Create `src/services/cloud_stt/` package with `CloudSTTProvider` interface (`start_stream`, `send_audio`, `get_results`, `stop_stream`)
- [ ] 1.2 Implement `OpenAIWhisperProvider` using the OpenAI Whisper API
- [ ] 1.3 Implement `DeepgramProvider` using Deepgram's streaming WebSocket API
- [ ] 1.4 Implement `GoogleCloudSpeechProvider` using Google Cloud Speech-to-Text streaming API
- [ ] 1.5 Create provider factory with `get_cloud_stt_provider(provider_name)` function
- [ ] 1.6 Define common transcript result model: `{ type: "interim"|"final"|"error", text: str, confidence?: float }`

## 2. Pipeline Step Registration

- [ ] 2.1 Add `CLOUD_STT = "cloud_stt"` to `ModelStep` enum in `src/config/models.py`
- [ ] 2.2 Add `cloud_stt` default to `model_registry.yaml` under `default_models`
- [ ] 2.3 Add cloud STT model entries (whisper-1, deepgram-nova-3, google-chirp) to `model_registry.yaml`
- [ ] 2.4 Add `cloud_stt` parameter to `ModelConfig.__init__()` and wire to `self._models`
- [ ] 2.5 Update model settings test step count assertion

## 3. WebSocket Streaming Endpoint

- [ ] 3.1 Create `src/api/voice_stream_routes.py` with WebSocket endpoint at `/ws/voice/stream`
- [ ] 3.2 Implement WebSocket authentication via `X-Admin-Key` query parameter in handshake
- [ ] 3.3 Accept binary audio chunks (PCM 16-bit mono 16kHz) and forward to cloud STT provider
- [ ] 3.4 Stream interim/final transcript results back as JSON WebSocket messages
- [ ] 3.5 Handle provider errors and send error messages to client
- [ ] 3.6 Implement clean connection teardown (stop provider stream on WebSocket close)
- [ ] 3.7 Register WebSocket route in `src/api/app.py`

## 4. Frontend Cloud STT Engine

- [ ] 4.1 Create `CloudSTTEngine` class implementing the `STTEngine` interface
- [ ] 4.2 Implement MediaRecorder-based audio capture with AudioContext PCM conversion
- [ ] 4.3 Implement WebSocket connection to `/ws/voice/stream` with auth query param
- [ ] 4.4 Stream audio chunks at 100-250ms intervals via WebSocket binary messages
- [ ] 4.5 Parse incoming JSON messages and emit interim/final transcript events
- [ ] 4.6 Implement WebSocket reconnection with exponential backoff (1s, 2s, 4s, max 3 retries)
- [ ] 4.7 Add "Reconnecting..." state to voice input UI during reconnection attempts

## 5. Engine Preference Order

- [ ] 5.1 Update `AutoSTTEngine` to support configurable preference order (default: cloud → native → browser → on-device)
- [ ] 5.2 Add `cloudAvailable` to feature detection (check API key via settings API)
- [ ] 5.3 Skip unavailable engines in the preference order automatically
- [ ] 5.4 Refactor `useVoiceInput` to read engine preference from settings

## 6. Backend Cloud STT Settings

- [ ] 6.1 Extend `voice_settings_routes.py` to include `cloud_stt_provider`, `cloud_stt_language`, `engine_preference_order`
- [ ] 6.2 Add defaults: `cloud_stt_provider="openai"`, `cloud_stt_language="auto"`, `engine_preference_order="cloud,native,browser,on-device"`
- [ ] 6.3 Add `PUT` endpoints with validation for each cloud STT field
- [ ] 6.4 Add `DELETE` endpoints for reset to defaults
- [ ] 6.5 Add cloud STT provider connection check to connection status API

## 7. Frontend Cloud STT Settings UI

- [ ] 7.1 Add Cloud STT subsection to `VoiceConfigurator.tsx`
- [ ] 7.2 Add provider selector dropdown (OpenAI / Deepgram / Google) with configuration status indicator
- [ ] 7.3 Add language selector (Auto, English US, English UK, Spanish, French, German, Japanese, Chinese)
- [ ] 7.4 Add engine preference order list with drag-and-drop reordering
- [ ] 7.5 Wire settings to `use-settings.ts` hooks
- [ ] 7.6 Add source badges (env/db/default) for cloud STT settings

## 8. Testing

- [ ] 8.1 Add unit tests for cloud STT provider abstraction (mock provider APIs)
- [ ] 8.2 Add integration tests for WebSocket endpoint (mock provider, verify message flow)
- [ ] 8.3 Add unit tests for audio format conversion (PCM 16-bit mono)
- [ ] 8.4 Add backend tests for cloud STT settings API endpoints
- [ ] 8.5 Add E2E tests for cloud STT settings UI (provider selection, preference order)
- [ ] 8.6 Add E2E tests for WebSocket reconnection behavior (mocked)
- [ ] 8.7 Update model settings test step count assertion
