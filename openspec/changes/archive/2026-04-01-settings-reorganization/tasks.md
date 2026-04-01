# Settings Reorganization — Tasks

## Phase 1: ConfigRegistry Service + YAML Directory

### Backend — ConfigRegistry

- [ ] 1.1 Write tests for ConfigRegistry — registration, get, list_keys, cache, reload, error handling
  **Spec scenarios**:
    - settings-mgmt.1 → test_register_domain_lazy_no_file_read()
    - settings-mgmt.1a → test_register_duplicate_domain_raises_valueerror()
    - settings-mgmt.2 → test_get_nested_key_returns_leaf_value()
    - settings-mgmt.3 → test_reload_invalidates_cache_reads_fresh()
    - settings-mgmt.4 → test_get_missing_key_returns_none()
    - settings-mgmt.4a → test_get_null_yaml_value_returns_none()
    - settings-mgmt.5 → test_list_keys_returns_only_leaf_paths()
    - settings-mgmt.6 → test_get_unregistered_domain_raises_valueerror()
    - settings-mgmt.6a → test_get_malformed_yaml_raises_yamlerror()
    - settings-mgmt.6b → test_get_missing_file_raises_filenotfounderror()
  **Design decisions**: D1 (thin coordinator), D2 (domain registration), D3 (lazy loading)
  **Note**: Tests SHALL use a temporary `settings/` directory created via pytest `tmp_path` fixture with mock YAML data. Do not depend on actual repo YAML files.
  **Dependencies**: None

- [ ] 1.2 Create `src/config/config_registry.py` — ConfigRegistry with ConfigDomain dataclass, register(), get(), list_keys(), reload(), reload_all()
  **Spec scenarios**: settings-mgmt.1, 1a, 2, 3, 4, 4a, 5, 6, 6a, 6b (implementation of all registry scenarios)
  **Design decisions**: D1 (thin coordinator), D2 (registration pattern), D3 (lazy loading)
  **Dependencies**: 1.1

- [ ] 1.3a Create `settings/` directory and move existing YAML files
  - Move `src/config/prompts.yaml` to `settings/prompts.yaml`
  - Move `src/config/model_registry.yaml` to `settings/models.yaml`
  **Spec scenarios**: settings-mgmt.7 (YAML files present)
  **Design decisions**: D4 (directory location), D8 (no symlinks)
  **Dependencies**: None

- [ ] 1.3b Extract voice defaults from Settings class and create `settings/voice.yaml`
  - Map Settings fields: `audio_digest_provider`, `audio_digest_default_voice`, `audio_digest_speed`, `audio_digest_max_duration_minutes`, `AUDIO_DIGEST_VOICE_PRESETS`
  - Verify extracted YAML defaults match current Settings class defaults exactly
  **Spec scenarios**: settings-mgmt.7 (YAML files present), settings-mgmt.10a (voice defaults)
  **Design decisions**: D7 (voice YAML)
  **Dependencies**: None

- [ ] 1.3c Extract notification defaults and create `settings/notifications.yaml`
  - Define default enabled state for all event types: batch_summary, theme_analysis, digest_creation, script_generation, audio_generation, pipeline_completion, job_failure
  **Spec scenarios**: settings-mgmt.7 (YAML files present), settings-mgmt.10b (notification defaults)
  **Design decisions**: D7 (notification YAML)
  **Dependencies**: None

- [ ] 1.3d Write tests verifying all 4 YAML files are valid and loadable via ConfigRegistry
  **Spec scenarios**: settings-mgmt.7 (all files present and valid), settings-mgmt.10a, settings-mgmt.10b
  **Dependencies**: 1.2, 1.3a, 1.3b, 1.3c

- [ ] 1.5 Write tests for PromptService using ConfigRegistry — defaults load from registry, template rendering still works, overrides still work
  **Spec scenarios**: settings-mgmt.2 (resolution), settings-mgmt.9 (precedence)
  **Design decisions**: D1 (PromptService keeps template rendering, registry only provides YAML)
  **Dependencies**: 1.2

- [ ] 1.6 Update `src/services/prompt_service.py` — replace `_load_defaults()` direct file read with `ConfigRegistry.get()` calls
  **Spec scenarios**: settings-mgmt.8 (old paths removed — no more direct file reads)
  **Design decisions**: D8 (no symlinks — all code uses registry)
  **Dependencies**: 1.5, 1.3a

- [ ] 1.7 Write tests for ModelConfig using ConfigRegistry — model registry loads from new path, env/DB precedence works
  **Spec scenarios**: settings-mgmt.2 (resolution), settings-mgmt.10 (DB override wins)
  **Dependencies**: 1.2

- [ ] 1.8 Update `src/config/models.py` — replace `load_model_registry()` direct YAML read with ConfigRegistry
  **Spec scenarios**: settings-mgmt.8 (old paths removed)
  **Design decisions**: D8 (no symlinks)
  **Dependencies**: 1.7, 1.3a

- [ ] 1.9 Write tests for voice/notification defaults loading via registry — verify extracted defaults match Settings class behavior
  **Spec scenarios**: settings-mgmt.9 (precedence), settings-mgmt.10 (DB override wins), settings-mgmt.10a (voice defaults), settings-mgmt.10b (notification defaults)
  **Dependencies**: 1.2, 1.3b, 1.3c

- [ ] 1.10 Update voice settings routes and notification preferences routes to use ConfigRegistry for defaults
  **Spec scenarios**: settings-mgmt.10a (voice defaults via registry), settings-mgmt.10b (notification defaults via registry)
  **Design decisions**: D1 (routes keep domain logic, registry provides YAML defaults)
  **Dependencies**: 1.9

- [ ] 1.11 Register all 4 domains at app startup — add to FastAPI lifespan or module-level init in `src/config/config_registry.py`
  **Spec scenarios**: settings-mgmt.17 (startup registration)
  **Dependencies**: 1.2, 1.3a, 1.3b, 1.3c

- [ ] 1.12 Update existing tests that reference old YAML paths (`src/config/prompts.yaml`, `src/config/model_registry.yaml`) to use ConfigRegistry or new paths
  **Spec scenarios**: settings-mgmt.8 (old paths removed)
  **Dependencies**: 1.6, 1.8

## Phase 2: Frontend Tab Routing

### Frontend — Settings Layout

- [ ] 2.1 Write E2E tests for tabbed settings navigation
  **Spec scenarios**:
    - settings-mgmt.13 → test_settings_page_shows_4_tabs_prompts_default()
    - settings-mgmt.14 → test_click_models_tab_changes_url_and_loads_only_models_data()
    - settings-mgmt.15 → test_direct_navigate_to_voice_shows_voice_tab_active()
    - settings-mgmt.15a → test_invalid_tab_url_redirects_to_prompts()
    - settings-mgmt.16a → test_no_connections_tab_in_settings()
  **Design decisions**: D5 (React Router Outlet)
  **Routes tested** (per D5): `/settings` → redirect → `/settings/prompts`, `/settings/models`, `/settings/voice`, `/settings/notifications`
  **Dependencies**: None

- [ ] 2.2a Extract `PromptsSettings` component from settings.tsx (wraps PromptManager)
  **Dependencies**: 2.1

- [ ] 2.2b Extract `ModelsSettings` component from settings.tsx (wraps ModelConfigurator)
  **Dependencies**: 2.1

- [ ] 2.2c Extract `VoiceSettings` component from settings.tsx (wraps VoiceConfigurator)
  **Dependencies**: 2.1

- [ ] 2.2d Extract `NotificationsSettings` component from settings.tsx (wraps NotificationConfigurator + PushNotificationToggle)
  **Dependencies**: 2.1

- [ ] 2.3 Convert `web/src/routes/settings.tsx` to SettingsLayout with `<nav role="tablist">`, NavLink tabs, and `<Outlet />`
  **Spec scenarios**: settings-mgmt.13 (tab bar structure), settings-mgmt.15 (aria-selected)
  **Dependencies**: 2.2a, 2.2b, 2.2c, 2.2d

- [ ] 2.4 Update router configuration — add nested routes under `/settings` with index redirect to `/settings/prompts`, catch-all redirect for invalid tabs
  **Spec scenarios**: settings-mgmt.13 (default tab), settings-mgmt.15a (invalid tab redirect)
  **Dependencies**: 2.3

- [ ] 2.5 Update navigation links — sidebar/header links to `/settings` should still work (layout handles redirect)
  **Dependencies**: 2.4

## Phase 3: Status Page + Connection Endpoint Migration

### Backend — Status Endpoint

- [ ] 3.1 Write tests for new status endpoint and redirect
  **Spec scenarios**:
    - settings-mgmt.11 → test_get_status_connections_returns_200_with_services()
    - settings-mgmt.11 → test_status_response_includes_status_and_latency_per_service()
    - settings-mgmt.12 → test_old_settings_connections_returns_307_redirect()
    - settings-mgmt.12 → test_redirect_preserves_auth_headers()
  **Dependencies**: None

- [ ] 3.2 Create `src/api/status_routes.py` — move connection health handler to `/api/v1/status/connections`
  **Spec scenarios**: settings-mgmt.11 (new endpoint)
  **Dependencies**: 3.1

- [ ] 3.3 Add 307 redirect from `/api/v1/settings/connections` to `/api/v1/status/connections` in `connection_status_routes.py`
  **Spec scenarios**: settings-mgmt.12 (redirect)
  **Dependencies**: 3.2

- [ ] 3.4 Register new status router in `src/api/app.py`
  **Spec scenarios**: settings-mgmt.11 (endpoint accessible)
  **Note**: Coordinate merge order with `add-api-versioning` if both modify `app.py` router registration
  **Dependencies**: 3.2

### Frontend — Status Page

- [ ] 3.5 Write E2E tests for `/status` page
  **Spec scenarios**:
    - settings-mgmt.16 → test_status_page_renders_health_dashboard_with_service_rows()
    - settings-mgmt.16a → test_connections_not_accessible_under_settings()
  **Dependencies**: None

- [ ] 3.6 Create `web/src/routes/status.tsx` — extract ConnectionDashboard from settings into top-level page
  **Spec scenarios**: settings-mgmt.16 (top-level status page)
  **Dependencies**: 3.5

- [ ] 3.7 Update frontend API client — change connection status endpoint to `/api/v1/status/connections`
  **Dependencies**: 3.3

- [ ] 3.8 Add `/status` route to router and update navigation (sidebar/header)
  **Spec scenarios**: settings-mgmt.16 (navigable)
  **Dependencies**: 3.6

- [ ] 3.9 Remove ConnectionDashboard import from settings.tsx (extracted in 3.6)
  **Spec scenarios**: settings-mgmt.16a (connections not in settings, tab count = 4)
  **Dependencies**: 3.6, 2.3

## Phase 4: Documentation and Cleanup

- [ ] 4.1 Update `CLAUDE.md` configuration section to reference `settings/` directory
  **Dependencies**: 1.3a

- [ ] 4.2 Update `docs/SETUP.md` and `docs/MODEL_CONFIGURATION.md` to reference new YAML paths
  **Dependencies**: 1.3a

- [ ] 4.3 Delete old YAML files from `src/config/` — `prompts.yaml` and `model_registry.yaml` (per D8, no symlinks)
  **Spec scenarios**: settings-mgmt.8 (old paths removed)
  **Dependencies**: 1.6, 1.8, 1.12

- [ ] 4.4 Update `docs/GOTCHAS.md` if any new gotchas emerge from the migration
  **Dependencies**: All previous tasks
