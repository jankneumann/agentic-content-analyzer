# Settings Reorganization — Design

## Architecture Overview

```
settings/                          # Top-level YAML defaults
├── prompts.yaml                   # Moved from src/config/prompts.yaml
├── models.yaml                    # Moved from src/config/model_registry.yaml
├── voice.yaml                     # New — extracted from Settings class
└── notifications.yaml             # New — extracted from Settings class

src/config/
├── config_registry.py             # NEW — ConfigRegistry service
├── settings.py                    # Modified — delegates to registry
├── models.py                      # Modified — uses registry for YAML loading
└── prompts.py                     # Removed — absorbed into registry

src/services/
├── prompt_service.py              # Modified — uses registry for defaults
└── settings_service.py            # Modified — uses registry for defaults

src/api/
├── settings_routes.py             # Unchanged
├── model_settings_routes.py       # Unchanged
├── voice_settings_routes.py       # Unchanged
├── settings_override_routes.py    # Unchanged
├── notification_preferences_routes.py  # Unchanged
├── connection_status_routes.py    # Moved to status_routes.py
└── status_routes.py               # NEW — /api/v1/status/connections

web/src/
├── routes/
│   ├── settings.tsx               # Converted to layout with tab navigation
│   ├── settings/
│   │   ├── prompts.tsx            # NEW — extracted from settings.tsx
│   │   ├── models.tsx             # NEW — extracted from settings.tsx
│   │   ├── voice.tsx              # NEW — extracted from settings.tsx
│   │   └── notifications.tsx      # NEW — extracted from settings.tsx
│   └── status.tsx                 # NEW — connections health dashboard
```

## Design Decisions

### D1: ConfigRegistry as a Thin Coordinator, Not a God Object

The `ConfigRegistry` is **not** a replacement for `PromptService` or `ModelConfig`. It is a coordinator that:
- Owns YAML file loading and caching
- Provides a unified `get(domain, key)` interface for reading defaults
- Delegates DB override resolution to existing services
- Supports domain registration with validation schemas

**Why**: The existing services (`PromptService`, `SettingsService`) have domain-specific logic (template rendering, version tracking) that doesn't belong in a generic registry. The registry handles the common pattern (load YAML, cache, resolve defaults) and leaves domain logic to domain services.

**Rejected alternative**: Making `ConfigRegistry` handle DB overrides directly. This would duplicate the existing `SettingsService` and `PromptService` DB logic and create a single point of failure.

### D2: Domain Registration Pattern

Each settings domain registers with the registry at import time:

```python
class ConfigDomain:
    name: str                    # e.g., "prompts", "models", "voice", "notifications"
    yaml_file: str               # Relative path under settings/ directory
    schema: type[BaseModel] | None  # Optional Pydantic validation model
    key_separator: str = "."     # How to traverse nested YAML

registry = ConfigRegistry(settings_dir=Path("settings"))
registry.register(ConfigDomain(name="prompts", yaml_file="prompts.yaml"))
registry.register(ConfigDomain(name="models", yaml_file="models.yaml"))
registry.register(ConfigDomain(name="voice", yaml_file="voice.yaml"))
registry.register(ConfigDomain(name="notifications", yaml_file="notifications.yaml"))
```

**Why**: Declarative registration makes it trivial to add new domains. The `tree-index-chunking` feature can just add a `register()` call with its YAML file instead of creating new loading boilerplate.

### D3: Lazy Loading with Cache Invalidation

YAML files are loaded lazily on first access per domain, then cached. Cache invalidation happens via:
- `registry.reload(domain)` — explicit reload for a single domain
- `registry.reload_all()` — reload all domains
- File mtime checking (optional, for dev hot-reload)

```python
class ConfigRegistry:
    _cache: dict[str, tuple[float, dict]]  # domain -> (mtime, parsed_yaml)

    def get(self, domain: str, key: str) -> Any:
        self._ensure_loaded(domain)
        return self._resolve_key(domain, key)

    def _ensure_loaded(self, domain: str) -> None:
        if domain not in self._cache or self._is_stale(domain):
            self._load(domain)
```

**Why**: Lazy loading avoids startup penalty when not all domains are needed (e.g., CLI commands that only touch one domain). Mtime-based staleness checking enables hot-reload during development without requiring a restart.

**Rejected alternative**: Eager loading at startup. This would load all YAML files even for CLI commands that don't need them (e.g., `aca ingest gmail` doesn't need voice settings).

### D4: Settings Directory Location

The `settings/` directory lives at the project root (same level as `src/`, `profiles/`, `sources.d/`).

**Why**: It follows the established pattern — `profiles/` for environment profiles, `sources.d/` for source definitions, `settings/` for configurable defaults. Keeping it outside `src/` makes it clear these are data files, not code.

**Path resolution**: `ConfigRegistry` accepts a `settings_dir` parameter. Default is `Path(project_root) / "settings"`. Tests can pass a temp directory.

### D5: Frontend Tab Routing with React Router Outlet

The settings page becomes a layout route with child routes:

```tsx
// In router configuration
{
  path: "settings",
  element: <SettingsLayout />,
  children: [
    { index: true, element: <Navigate to="prompts" replace /> },
    { path: "prompts", element: <PromptsSettings /> },
    { path: "models", element: <ModelsSettings /> },
    { path: "voice", element: <VoiceSettings /> },
    { path: "notifications", element: <NotificationsSettings /> },
  ]
}
```

`SettingsLayout` renders a tab bar and an `<Outlet />` for child routes. Each tab is a `<NavLink>` that highlights when active.

**Why**: This is the standard React Router nested route pattern. Each sub-page loads its own data via existing React Query hooks, so navigating between tabs doesn't re-fetch everything.

### D6: Connection Status Moves to /status

The `ConnectionDashboard` component moves from a settings section to a top-level `/status` page. The backend endpoint moves from `/api/v1/settings/connections` to `/api/v1/status/connections`.

**Backwards compatibility**: The old endpoint returns a 307 redirect to the new path. The redirect can be removed after one release cycle.

**Why**: Connection health is read-only operational status, not a configurable setting. Moving it to `/status` makes the settings page purely about configuration.

### D7: Voice and Notification YAML Files

Currently, voice defaults are hardcoded in `Settings` class fields and `AUDIO_DIGEST_VOICE_PRESETS`. Notification defaults are implicit (all enabled by default). These get extracted to YAML:

**settings/voice.yaml:**
```yaml
provider: openai
default_voice: nova
speed: 1.0
max_duration_minutes: 30
presets:
  conversational:
    openai: nova
    elevenlabs: Rachel
  professional:
    openai: onyx
    elevenlabs: Daniel
  # ...
```

**settings/notifications.yaml:**
```yaml
defaults:
  batch_summary: true
  theme_analysis: true
  digest_creation: true
  script_generation: true
  audio_generation: true
  pipeline_completion: true
  job_failure: true
```

**Why**: Making defaults explicit in YAML means they can be reviewed and changed without code changes. This is consistent with how prompts and models already work.

## Non-Goals

- **No schema migration**: DB tables `prompt_overrides` and `settings_overrides` stay as-is
- **No profile system changes**: `profiles/*.yaml` is a separate concern
- **No new settings categories**: No sources management UI or new config domains
- **No settings import/export**: Could be added later via the registry, but out of scope
