# Design: OpenBao Secrets Management Integration

## Architecture Decisions

### D1: Pydantic Settings Source over Dedicated Service

**Decision**: Implement OpenBao as a `PydanticBaseSettingsSource` rather than a standalone `SecretsService`.

**Rationale**: The codebase already uses Pydantic `BaseSettings` with a custom 5-source chain (`settings_customise_sources`). Adding a 6th source is a minimal, non-breaking change. All existing code that reads `Settings` fields or calls `resolve_secret()` automatically gains OpenBao support without modification. A dedicated service would require refactoring every component that reads secrets.

**Trade-off**: All secrets are loaded at startup (not lazy per-key). With ~30 secrets this is a single HTTP call, so the trade-off is acceptable.

### D2: Process-Level Caching with Background Refresh

**Decision**: Cache all secrets in a module-level dict on first access. For long-running processes (API server), refresh the token and re-fetch secrets when 75% of the token TTL has elapsed.

**Rationale**: The newsletter aggregator runs as both short-lived CLI commands (ingest, summarize) and a long-running FastAPI server. CLI processes don't need refresh (they complete in minutes). The API server needs refresh to handle token expiry during multi-hour uptime.

**Rejected alternative**: Per-request vault lookups — adds ~10ms latency per secret per request with no benefit (secrets change at most daily during rotation).

### D3: Separate Seeding Script (not extending coordinator's)

**Decision**: Create `scripts/bao_seed_newsletter.py` as a standalone script, independent of `.claude/skills/bao-vault/scripts/bao_seed.py`.

**Rationale**: The coordinator's script is designed for its own `agents.yaml`-based AppRole model. The newsletter project has different seeding needs (shared keys, newsletter-specific DB engine roles). Keeping them separate avoids coupling the two projects' deployment lifecycles.

### D4: Graceful Degradation as Default

**Decision**: If `BAO_ADDR` is not set, `hvac` is not installed, or OpenBao is unreachable, the module silently falls through to the next source in the chain. No exceptions, no startup failures.

**Rationale**: OpenBao is an optional enhancement. The existing `.secrets.yaml` + env var flow must remain fully functional for developers who don't run OpenBao locally. This matches the codebase's existing optional-provider pattern (see `OBSERVABILITY_PROVIDER=noop`).

### D5: Structured Audit Logging (not external audit backend)

**Decision**: Use Python's `logging` module with structured key-value log messages for audit events, rather than writing to a dedicated audit database or OpenBao's own audit backend.

**Rationale**: OpenBao has its own audit device that logs all vault operations server-side. The application-level audit logging complements this by recording *which application component* triggered the access. Using `logging` keeps this within the existing observability pipeline (logs → stdout → Railway/Docker log aggregation).

## Module Design

### src/config/bao_secrets.py

```
┌─────────────────────────────────────────────────┐
│                 bao_secrets.py                   │
│                                                  │
│  ┌────────────────┐  ┌────────────────────────┐ │
│  │ _load_bao_     │  │ BaoSettingsSource      │ │
│  │  secrets()     │  │                        │ │
│  │  ─ auth        │  │  get_field_value()     │ │
│  │  ─ KV v2 read  │──│  __call__()            │ │
│  │  ─ cache       │  │                        │ │
│  └────────────────┘  └────────────────────────┘ │
│                                                  │
│  ┌────────────────┐  ┌────────────────────────┐ │
│  │ _BaoTokenMgr   │  │ Public API             │ │
│  │  ─ refresh()   │  │  get_bao_secret()      │ │
│  │  ─ schedule()  │  │  clear_bao_cache()     │ │
│  │  ─ stop()      │  │  is_bao_configured()   │ │
│  └────────────────┘  └────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

**Key components**:

1. **`_load_bao_secrets()`** — Core loader. Authenticates (AppRole or token), reads KV v2, caches result. Called once per process unless refresh triggers.

2. **`BaoSettingsSource`** — Implements Pydantic settings source protocol. Maps UPPER_CASE vault keys to lower_case field names via `{k.lower(): v}`.

3. **`_BaoTokenManager`** — Background token lifecycle for long-running processes. Uses `threading.Timer` to schedule refresh at 75% of TTL. Only activates when AppRole auth is used (token auth in dev mode has no TTL).

4. **`get_bao_secret(key)`** — Direct lookup for use in `resolve_secret()` and other non-Settings contexts.

5. **`clear_bao_cache()`** — Test utility to reset cached state between test runs.

### Token Refresh Flow

```
Start ──► AppRole login ──► Get token (TTL=3600s)
                                    │
                                    ▼
                           Schedule timer at 75% TTL (2700s)
                                    │
                                    ▼ (2700s later)
                           Re-authenticate via AppRole
                           Re-read KV v2 secrets
                           Update cache atomically
                           Schedule next timer
```

Token auth (`BAO_TOKEN`) skips the refresh loop — it's for dev mode where the dev server token never expires.

### Settings Integration Point

```python
# src/config/settings.py — settings_customise_sources()
return (
    init_settings,       # 1. Constructor args
    env_settings,        # 2. Environment variables
    bao_settings,        # 3. OpenBao KV v2 (NEW)
    profile_settings,    # 4. profiles/{name}.yaml
    dotenv_settings,     # 5. .env file
    file_secret_settings,# 6. Pydantic file secrets
)
```

### Seeding Script Design

```
bao_seed_newsletter.py
  ├── seed_secrets()        ─ .secrets.yaml → secret/newsletter/
  ├── seed_shared_keys()    ─ selected keys → secret/shared/ (merge)
  ├── seed_approle()        ─ newsletter-read policy + newsletter-app role
  └── seed_db_engine()      ─ PostgreSQL dynamic credentials
```

The script reads `.secrets.yaml` from the project root (not the coordinator's). Shared key seeding **merges** with existing `secret/shared/` data — newsletter values win on key conflicts, but keys from other projects (e.g., coordinator) are preserved.

## Thread Safety

`_load_bao_secrets()` uses a `threading.Lock` to ensure only one thread fetches from OpenBao during initial load. The cache dict is replaced atomically (reference swap, not mutation) during both initial load and token-refresh cycles, ensuring threads reading the cache never see a partially-updated state.

## File Changes

| File | Change |
|------|--------|
| `src/config/bao_secrets.py` | **New** — Core module (auth, cache, thread safety, BaoSettingsSource, token manager, audit) |
| `src/config/secrets.py` | **Modify** — Add OpenBao tier to `resolve_secret()` |
| `src/config/settings.py` | **Modify** — Wire `BaoSettingsSource` into source chain as priority 3 |
| `scripts/bao_seed_newsletter.py` | **New** — Seeding script with merge semantics for shared keys |
| `docker-compose.openbao.yml` | **New** — Docker overlay for local dev |
| `profiles/local-openbao.yaml` | **New** — Dev profile extending `local` |
| `pyproject.toml` | **Modify** — Add `[vault]` optional dependency (`hvac>=2.1.0`) |
| `CLAUDE.md` | **Modify** — Add docs/OPENBAO.md to doc index |
| `.secrets.yaml.example` | **Modify** — Add `BAO_*` variable examples in comments |
| `docs/OPENBAO.md` | **New** — Integration documentation with audit event reference |
| `tests/test_config/test_bao_secrets.py` | **New** — Unit tests (auth, cache, thread safety, degradation) |
| `tests/test_config/test_bao_settings_integration.py` | **New** — Integration tests (settings chain, resolve_secret) |
| `tests/test_config/test_bao_seeding.py` | **New** — Seeding script tests (merge, AppRole, DB engine, failures) |
