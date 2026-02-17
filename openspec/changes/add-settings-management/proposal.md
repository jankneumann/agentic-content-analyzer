# Change: Build out Settings page with model, voice, and connection management

## Why

The Settings page has three stubbed sections labeled "coming in Phase 3" — Model Configuration, Voice Configuration, and API Connections. Meanwhile, the prompt management section is fully functional. Users currently need SSH/env-var access to change which LLM model runs each pipeline step or which TTS voice narrates audio digests. This blocks non-technical operators from tuning the system and forces redeployment for simple config changes.

## What Changes

### 1. Settings Override System (foundation)
- New `settings_overrides` database table (key/value with versioning, identical pattern to `prompt_overrides`)
- New `SettingsService` that layers DB overrides on top of env-var defaults
- API endpoints under `/api/v1/settings/overrides` (admin-key protected)

### 2. Model Configuration UI
- Dropdown selectors for each pipeline step (summarization, theme_analysis, digest_creation, etc.)
- Choices populated from `model_registry.yaml` (shows model name, family, vision/video support)
- Wire `settings.get_model_config()` to read DB overrides, falling back to YAML defaults
- Show current effective model per step with source indicator (env var / DB override / default)

### 3. Voice Configuration UI
- TTS provider selector (openai, elevenlabs)
- Voice preset picker (professional, warm, energetic, calm) with provider-specific voice IDs
- Speed slider (0.5–2.0) for audio digest playback
- Wire `settings.get_audio_digest_voice_id()` to read DB overrides

### 4. API Connection Status Dashboard
- Read-only status cards for all configured backends
- Connection health checks: PostgreSQL, Neo4j, LLM providers (Anthropic/OpenAI/Google AI), TTS providers (OpenAI/ElevenLabs), embedding provider
- New `/api/v1/settings/connections` endpoint reusing health-check logic from `/ready`
- Auto-refresh with 30s polling interval

### 5. CLI Integration
- `aca settings list [--prefix]` / `get <key>` / `set <key> <value>` / `reset <key>` commands
- Provides command-line access to the same settings override system

## Impact

- Affected specs: new `settings-management` capability
- Affected code:
  - Backend: new route files (`settings_override_routes.py`, `model_settings_routes.py`, `voice_settings_routes.py`, `connection_status_routes.py`), `src/config/settings.py`, `src/services/settings_service.py`, `src/services/connection_checker.py`
  - Frontend: `web/src/routes/settings.tsx`, new components in `web/src/components/settings/`
  - Types: `web/src/types/settings.ts`, `web/src/lib/api/settings.ts`, `web/src/hooks/use-settings.ts`
  - CLI: `src/cli/settings_commands.py`
  - Tests: `tests/api/test_settings_override_api.py`, `tests/api/test_model_settings_api.py`, `tests/api/test_voice_settings_api.py`, `tests/api/test_connection_status_api.py`, `tests/cli/test_settings_commands.py`, `web/tests/e2e/settings/`
