## Context

The Settings page currently has one fully-functional section (LLM Prompts) and three stubs. The prompt management pattern (YAML defaults + DB overrides + admin API + React UI) is proven and should be extended to model selection, voice configuration, and connection status.

**Constraints:**
- Single-user system (admin API key auth, no RBAC)
- Settings must survive redeployment (DB persistence)
- Env vars always win over DB overrides (operator escape hatch)
- Frontend must work with zero configuration (sensible defaults from YAML/code)

## Goals / Non-Goals

**Goals:**
- Model selection configurable per pipeline step without redeployment
- Voice/TTS settings configurable without redeployment
- Connection health visible at a glance from the UI
- Consistent pattern: env var > DB override > code default
- CLI access to the settings override system

**Non-Goals:**
- Multi-user/RBAC access control (single admin key suffices)
- Live model switching mid-pipeline-run (changes take effect on next run)
- API key management UI (keys stay in env vars / .secrets.yaml — no secret storage in DB)
- Provider failover configuration (keep using existing ModelConfig provider chain)

## Decisions

### Decision 1: Single `settings_overrides` table (not per-domain tables)

Use one key-value table for all settings overrides (models, voice, future settings). This mirrors `prompt_overrides` and avoids table proliferation.

**Alternatives considered:**
- Separate `model_overrides` + `voice_overrides` tables — more structured but adds migration burden for each new settings domain. Rejected: YAGNI, key-value is sufficient.
- JSON blob in a single row — simpler but no per-key versioning or atomic updates. Rejected: lose audit trail.

**Schema:**
```sql
CREATE TABLE settings_overrides (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) UNIQUE NOT NULL,   -- e.g., "model.summarization", "voice.provider"
    value TEXT NOT NULL,                 -- JSON-encoded for complex values, plain for strings
    version INTEGER DEFAULT 1,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ix_settings_overrides_key ON settings_overrides (key);
```

### Decision 2: Key namespace convention

Settings keys use dot-separated namespaces:
- `model.<step>` — e.g., `model.summarization`, `model.theme_analysis`
- `voice.<field>` — e.g., `voice.provider`, `voice.default_voice`, `voice.speed`

This enables listing/filtering by prefix and avoids collision with prompt keys (which use `chat.*` / `pipeline.*`).

### Decision 3: Precedence chain (env var > DB override > code default)

```
Effective value = env_var ?? db_override ?? code_default
```

- `SettingsService.get(key)` checks DB override
- `settings.get_model_config()` checks Settings fields (env vars) first, then SettingsService
- This means operators can always force a value via env var without touching the UI

### Decision 4: Connection status as read-only (no mutations)

The connections section only reads and displays status — no creating/deleting connections from UI. Connection configuration remains in env vars / profiles. This keeps the scope tight and avoids the security risk of storing credentials in the DB.

### Decision 5: Reuse existing health_check infrastructure

The `/ready` endpoint already checks database and queue. Extend this pattern to check additional backends (Neo4j, LLM API reachability, TTS provider, embedding provider). The new `/api/v1/settings/connections` endpoint returns richer per-service status.

### Decision 6: Separate route files per settings domain

Each settings domain gets its own route file to avoid merge conflicts during parallel development:
- `src/api/settings_override_routes.py` — generic CRUD for settings overrides
- `src/api/model_settings_routes.py` — model-specific endpoints with validation
- `src/api/voice_settings_routes.py` — voice-specific endpoints with validation
- `src/api/connection_status_routes.py` — connection health checks

All registered in `src/api/router.py`. This keeps the existing `settings_routes.py` (prompts) untouched.

## Risks / Trade-offs

- **Risk: Model registry stale in UI** — If `model_registry.yaml` is updated (new models), the UI dropdown refreshes on next page load. No migration needed.
  - Mitigation: Models endpoint reads YAML at request time (cached with TTL).

- **Risk: Invalid model selected** — User picks a model that isn't available from any configured provider.
  - Mitigation: Validate model ID against registry on save. Show provider availability indicator in UI.

- **Risk: Voice settings drift** — DB says "elevenlabs" but no API key configured.
  - Mitigation: Connection status section shows provider health. Voice save validates provider has API key.

- **Risk: Connection check latency** — Multiple backend checks could slow the endpoint.
  - Mitigation: `asyncio.gather()` runs all checks concurrently with per-service timeout from `health_check_timeout_seconds`.

## Migration Plan

1. Create `settings_overrides` Alembic migration (non-destructive, new table only)
2. Add backend `SettingsService` + override API endpoints
3. Add model, voice, and connection endpoints (parallel)
4. Wire `get_model_config()` and `get_audio_digest_voice_id()` to read DB overrides
5. Add frontend components (parallel with backend steps 3–4)
6. Add CLI commands (parallel with frontend)
7. E2E tests for each section

Rollback: Drop `settings_overrides` table. System falls back to env vars / code defaults. Zero data loss.

## Open Questions

None — all decisions align with existing patterns (prompt_overrides, admin key auth, health checks).
