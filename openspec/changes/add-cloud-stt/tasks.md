## 1. Cloud STT Provider Abstraction

- [x] 1.1 Create `src/services/cloud_stt/` package with `CloudSTTProvider` interface (`start_stream`, `send_audio`, `get_results`, `stop_stream`) including `cleaned: bool` flag on results
- [x] 1.2 Implement `GeminiSTTProvider` (default) — native audio input with built-in cleanup prompt, returns `cleaned: true`
- [x] 1.3 Implement `OpenAIWhisperProvider` — raw transcription, returns `cleaned: false`
- [x] 1.4 Implement `DeepgramProvider` using Deepgram's streaming WebSocket API, returns `cleaned: false`
- [x] 1.5 Create provider factory that resolves adapter from model family: `gemini` → `GeminiSTTProvider`, `whisper` → `WhisperSTTProvider`, `deepgram` → `DeepgramSTTProvider`
- [x] 1.6 Define common transcript result model: `{ type: "interim"|"final"|"error", text: str, cleaned: bool, confidence?: float }`
- [x] 1.7 Add Gemini transcription+cleanup prompt template (fix grammar, remove filler words, structure text, preserve intent)

## 2. Pipeline Step Registration & Audio Capability

- [x] 2.1 Add `CLOUD_STT = "cloud_stt"` to `ModelStep` enum in `src/config/models.py`
- [x] 2.2 Add `supports_audio: bool` field to `ModelInfo` dataclass (analogous to `supports_video`)
- [x] 2.3 Update `load_model_registry()` to parse `supports_audio` from YAML model definitions
- [x] 2.4 Add `supports_audio: true` to Gemini family models (2.0+) in `model_registry.yaml`
- [x] 2.5 Add `supports_audio: false` to Claude, GPT models in `model_registry.yaml` (explicit for clarity)
- [x] 2.6 Add STT-specific model entries to `model_registry.yaml`: `whisper-1` (family: whisper, `supports_audio: true`) and `deepgram-nova-3` (family: deepgram, `supports_audio: true`)
- [x] 2.7 Add `whisper` and `deepgram` to `ModelFamily` enum in `src/config/models.py`
- [x] 2.8 Add `cloud_stt: gemini-2.5-flash` default to `model_registry.yaml` under `default_models`
- [x] 2.9 Add `cloud_stt` parameter to `ModelConfig.__init__()` and wire to `self._models`
- [x] 2.10 Update model settings test step count assertion

## 3. WebSocket Streaming Endpoint

- [x] 3.1 Create `src/api/voice_stream_routes.py` with WebSocket endpoint at `/ws/voice/stream`
- [x] 3.2 Implement WebSocket authentication via `X-Admin-Key` query parameter in handshake
- [x] 3.3 Resolve cloud STT provider adapter from `CLOUD_STT` pipeline step model family
- [x] 3.4 Accept binary audio chunks (PCM 16-bit mono 16kHz) and forward to resolved provider
- [x] 3.5 Stream interim/final transcript results back as JSON WebSocket messages (include `cleaned` flag on final results)
- [x] 3.6 Handle provider errors and send error messages to client
- [x] 3.7 Implement clean connection teardown (stop provider stream on WebSocket close)
- [x] 3.8 Register WebSocket route in `src/api/app.py`

## 4. Frontend Cloud STT Engine

- [x] 4.1 Create `CloudSTTEngine` class implementing the `STTEngine` interface
- [x] 4.2 Implement MediaRecorder-based audio capture with AudioContext PCM conversion
- [x] 4.3 Implement WebSocket connection to `/ws/voice/stream` with auth query param
- [x] 4.4 Stream audio chunks at 100-250ms intervals via WebSocket binary messages
- [x] 4.5 Parse incoming JSON messages, emit interim/final transcript events, and propagate `cleaned` flag
- [x] 4.6 Skip automatic `VOICE_CLEANUP` call when `cleaned: true` (Gemini); keep cleanup button available for manual use
- [x] 4.7 Implement WebSocket reconnection with exponential backoff (1s, 2s, 4s, max 3 retries)
- [x] 4.8 Add "Reconnecting..." state to voice input UI during reconnection attempts

## 5. Engine Preference Order

- [x] 5.1 Update `AutoSTTEngine` to support configurable preference order (default: cloud → native → browser → on-device)
- [x] 5.2 Add `cloudAvailable` to feature detection (check API key for current CLOUD_STT model's provider via settings API)
- [x] 5.3 Skip unavailable engines in the preference order automatically
- [x] 5.4 Refactor `useVoiceInput` to read engine preference from settings

## 6. Backend Cloud STT Settings

- [x] 6.1 Extend `voice_settings_routes.py` to include `cloud_stt_language`, `engine_preference_order` (provider/model handled by CLOUD_STT ModelStep)
- [x] 6.2 Add defaults: `cloud_stt_language="auto"`, `engine_preference_order="cloud,native,browser,on-device"`
- [x] 6.3 Add `PUT` endpoints with validation for `cloud_stt_language` and `engine_preference_order`
- [x] 6.4 Add `DELETE` endpoints for reset to defaults
- [x] 6.5 Include `cloud_stt_model` as read-only field in `GET /api/v1/settings/voice` response (referencing current CLOUD_STT pipeline step model)
- [x] 6.6 Add cloud STT provider API key status check to connection status API (resolved from CLOUD_STT model family)

## 7. Frontend Cloud STT Settings UI

- [x] 7.1 Add Cloud STT subsection to `VoiceConfigurator.tsx` (language + engine preference only — model selection is in Model Configuration dialog)
- [x] 7.2 Show current CLOUD_STT model as a read-only badge linking to Model Configuration dialog
- [x] 7.3 Show API key configuration status for the current model's provider with setup hint if unconfigured
- [x] 7.4 Add language selector (Auto, English US, English UK, Spanish, French, German, Japanese, Chinese)
- [x] 7.5 Add engine preference order list with drag-and-drop reordering
- [x] 7.6 Wire settings to `use-settings.ts` hooks
- [x] 7.7 Add source badges (env/db/default) for cloud STT settings
- [x] 7.8 In Model Configuration dialog, filter CLOUD_STT step selector to only show models with `supports_audio: true`

## 8. Testing

- [x] 8.1 Add unit tests for cloud STT provider abstraction (mock provider APIs)
- [x] 8.2 Add unit tests for model-family → provider resolution
- [x] 8.3 Add integration tests for WebSocket endpoint (mock provider, verify message flow)
- [x] 8.4 Add unit tests for audio format conversion (PCM 16-bit mono)
- [x] 8.5 Add backend tests for cloud STT settings API endpoints
- [x] 8.6 Add unit tests for `supports_audio` flag parsing in `load_model_registry()`
- [x] 8.7 Add E2E tests for cloud STT settings UI (language, engine preference, model badge link)
- [x] 8.8 Add E2E tests for CLOUD_STT model selector filtering (only `supports_audio: true` models)
- [x] 8.9 Add E2E tests for WebSocket reconnection behavior (mocked)
- [x] 8.10 Update model settings test step count assertion
