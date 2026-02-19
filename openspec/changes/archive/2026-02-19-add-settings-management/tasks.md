## 1. Settings Override Foundation

- [x] 1.1 Create Alembic migration for `settings_overrides` table (key, value, version, description, timestamps)
- [x] 1.2 Add `SettingsOverride` SQLAlchemy model in `src/models/settings_override.py`
- [x] 1.3 Implement `SettingsService` in `src/services/settings_service.py` (get/set/delete/list by prefix, version increment on update)
- [x] 1.4 Write unit tests for `SettingsService` CRUD operations (including edge cases: delete non-existent, empty prefix results, version incrementing)
- [x] 1.5 Add settings override API routes in `src/api/settings_override_routes.py` (`GET/PUT/DELETE /api/v1/settings/overrides/{key}`, `GET /api/v1/settings/overrides?prefix=model`). Include key format validation (must match `namespace.name` pattern). Register in `src/api/router.py`.
- [x] 1.6 Write API tests for settings override endpoints in `tests/api/test_settings_override_api.py` (auth 401, CRUD, prefix filtering, key validation 400)

## 2. Model Configuration Backend

- [x] 2.1 Add `GET /api/v1/settings/models` endpoint in `src/api/model_settings_routes.py` — returns available models from registry + current selection per step with source indicator (env/db/default). Register in `src/api/router.py`.
- [x] 2.2 Wire `settings.get_model_config()` in `src/config/settings.py` to check `SettingsService` for `model.<step>` overrides before YAML defaults
- [x] 2.3 Add model ID validation in `src/api/model_settings_routes.py`: reject IDs not in `model_registry.yaml` with 400 + valid IDs list
- [x] 2.4 Write tests for model override resolution (env var > DB > YAML default) and validation (invalid model ID → 400) in `tests/api/test_model_settings_api.py`

## 3. Voice Configuration Backend

- [x] 3.1 Add `GET /api/v1/settings/voice` endpoint in `src/api/voice_settings_routes.py` — returns current voice config (provider, voice, speed, presets) with source indicators. Register in `src/api/router.py`.
- [x] 3.2 Wire `settings.get_audio_digest_voice_id()` in `src/config/settings.py` to check `SettingsService` for `voice.*` overrides
- [x] 3.3 Add voice validation in `src/api/voice_settings_routes.py`: reject unknown providers (400), speed outside 0.5–2.0 (400)
- [x] 3.4 Write tests for voice override resolution and validation in `tests/api/test_voice_settings_api.py`

## 4. Connection Status Backend

- [x] 4.1 Add `GET /api/v1/settings/connections` endpoint in `src/api/connection_status_routes.py` — returns health status for all configured services. Register in `src/api/router.py`.
- [x] 4.2 Implement connection check functions in `src/services/connection_checker.py`: PostgreSQL (reuse existing `db_health_check`), Neo4j (bolt ping), LLM providers (Anthropic/OpenAI/Google AI key validation), TTS providers (OpenAI/ElevenLabs key check), embedding provider
- [x] 4.3 Add per-service timeout handling (default from `health_check_timeout_seconds`) with `asyncio.wait_for()` — timeout → `unavailable`, missing credentials → `not_configured`
- [x] 4.4 Write tests with mocked backends in `tests/api/test_connection_status_api.py` for each status (ok, unavailable, not_configured, partial failure, timeout)

## 5. Frontend: Shared Infrastructure

- [x] 5.1 Add TypeScript types in `web/src/types/settings.ts` (ModelStepConfig, VoiceConfig, ConnectionStatus, SettingsOverride)
- [x] 5.2 Add API client functions in `web/src/lib/api/settings.ts` (fetchModels, fetchVoice, fetchConnections, updateSetting, resetSetting)
- [x] 5.3 Add query keys in `web/src/lib/api/query-keys.ts` (settingsKeys: models, voice, connections, overrides)
- [x] 5.4 Add TanStack Query hooks in `web/src/hooks/use-settings.ts` (useModels, useVoice, useConnections, useUpdateSetting, useResetSetting)

## 6. Frontend: Model Configuration Section

- [x] 6.1 Create `ModelConfigurator` component in `web/src/components/settings/ModelConfigurator.tsx` — dropdown per pipeline step, shows current model + family badge, disabled state for env-var-controlled steps
- [x] 6.2 Add model info display (vision/video support, provider availability)
- [x] 6.3 Add save/reset-to-default actions per step with toast feedback (success + error)
- [x] 6.4 Replace Model Configuration stub in `settings.tsx` with `ModelConfigurator`

## 7. Frontend: Voice Configuration Section

- [x] 7.1 Create `VoiceConfigurator` component in `web/src/components/settings/VoiceConfigurator.tsx` — provider selector, voice/preset picker, speed slider (0.5–2.0)
- [x] 7.2 Add voice preview section (show current preset name + provider-specific voice ID mapping)
- [x] 7.3 Add save/reset-to-default actions with toast feedback (success + error)
- [x] 7.4 Replace Voice Configuration stub in `settings.tsx` with `VoiceConfigurator`

## 8. Frontend: Connection Status Section

- [x] 8.1 Create `ConnectionDashboard` component in `web/src/components/settings/ConnectionDashboard.tsx` — status cards per service with ok/degraded/unavailable/not_configured indicators (green/yellow/red/gray)
- [x] 8.2 Add auto-refresh with 30s polling interval via TanStack Query `refetchInterval`
- [x] 8.3 Add manual refresh button with loading indicator
- [x] 8.4 Replace API Connections stub in `settings.tsx` with `ConnectionDashboard`

## 9. E2E Testing

- [x] 9.1 Create mock data factories for model/voice/connection responses in `web/tests/e2e/fixtures/mock-data.ts`
- [x] 9.2 Write E2E tests for Model Configuration section (dropdown selection, save, reset, disabled env-var step, save error)
- [x] 9.3 Write E2E tests for Voice Configuration section (provider switch, speed slider, preset selection, save error)
- [x] 9.4 Write E2E tests for Connection Dashboard (status display, refresh, not_configured state, partial failure)

## 10. CLI Integration

- [x] 10.1 Add `aca settings list` and `aca settings list --prefix <prefix>` commands in `src/cli/settings_commands.py`
- [x] 10.2 Add `aca settings get <key>` / `aca settings set <key> <value>` / `aca settings reset <key>` commands
- [x] 10.3 Write CLI tests for settings commands in `tests/cli/test_settings_commands.py`

## Dependencies & Parallelism

- **Phase A (sequential):** Tasks 1.1–1.6 (foundation must be complete first)
- **Phase B (parallel after Phase A):** Tasks 2.x, 3.x, 4.x can run in parallel
  - 2.x modifies `src/api/model_settings_routes.py` and `src/config/settings.py` (get_model_config)
  - 3.x modifies `src/api/voice_settings_routes.py` and `src/config/settings.py` (get_audio_digest_voice_id)
  - 4.x modifies `src/api/connection_status_routes.py` and `src/services/connection_checker.py`
  - **Note:** 2.x and 3.x both touch `src/config/settings.py` but different functions — safe to parallelize
- **Phase C (parallel with Phase B):** Tasks 5.x (shared frontend infrastructure — no backend dependency)
- **Phase D (parallel after Phases B+C):** Tasks 6.x, 7.x, 8.x can run in parallel
  - Each creates its own component file; 6.4/7.4/8.4 all modify `settings.tsx` (coordinate merge)
- **Phase E (after Phase D):** Tasks 9.x (E2E tests require all UI components)
- **Phase F (parallel with Phase B):** Tasks 10.x (CLI, only depends on Phase A services)

### File Ownership

To avoid merge conflicts when parallelizing:

| File | Owning Task(s) |
|------|----------------|
| `alembic/versions/xxx_settings_overrides.py` | 1.1 |
| `src/models/settings_override.py` | 1.2 |
| `src/services/settings_service.py` | 1.3 |
| `src/api/settings_override_routes.py` | 1.5 |
| `src/api/model_settings_routes.py` | 2.1, 2.3 |
| `src/api/voice_settings_routes.py` | 3.1, 3.3 |
| `src/api/connection_status_routes.py` | 4.1 |
| `src/services/connection_checker.py` | 4.2, 4.3 |
| `src/config/settings.py` | 2.2 (get_model_config), 3.2 (get_audio_digest_voice_id) |
| `src/api/router.py` | 1.5, 2.1, 3.1, 4.1 (add include_router calls) |
| `web/src/routes/settings.tsx` | 6.4, 7.4, 8.4 (stub replacement — coordinate) |
| `src/cli/settings_commands.py` | 10.1, 10.2 |
