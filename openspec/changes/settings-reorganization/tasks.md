# Settings Reorganization — Tasks

## Phase 1: ConfigRegistry Service + YAML Directory

### Backend — ConfigRegistry

- [ ] 1.1 Write tests for ConfigRegistry — domain registration, get/list, cache, reload, error cases
  **Spec scenarios**: settings-mgmt.1 (registration), settings-mgmt.2 (resolution), settings-mgmt.3 (cache invalidation), settings-mgmt.4 (missing key), settings-mgmt.5 (list keys), settings-mgmt.6 (unregistered domain)
  **Design decisions**: D1 (thin coordinator), D2 (domain registration), D3 (lazy loading)
  **Dependencies**: None

- [ ] 1.2 Create `src/config/config_registry.py` — ConfigRegistry with ConfigDomain, register(), get(), list_keys(), reload()
  **Dependencies**: 1.1

- [ ] 1.3 Create `settings/` directory with YAML files
  - Move `src/config/prompts.yaml` to `settings/prompts.yaml`
  - Move `src/config/model_registry.yaml` to `settings/models.yaml`
  - Create `settings/voice.yaml` with defaults extracted from `Settings` class
  - Create `settings/notifications.yaml` with default event toggles
  **Spec scenarios**: settings-mgmt.7 (YAML files present)
  **Design decisions**: D4 (directory location), D7 (voice/notification YAML)
  **Dependencies**: None

- [ ] 1.4 Update `src/config/prompts.yaml` path references — symlink or update `PromptService._load_defaults()` to use registry
  **Spec scenarios**: settings-mgmt.8 (old paths resolve)
  **Dependencies**: 1.2, 1.3

- [ ] 1.5 Write tests for PromptService using ConfigRegistry — verify defaults load from new path, overrides still work
  **Spec scenarios**: settings-mgmt.2 (resolution), settings-mgmt.9 (precedence)
  **Design decisions**: D1 (thin coordinator — PromptService keeps template rendering)
  **Dependencies**: 1.2

- [ ] 1.6 Update `src/services/prompt_service.py` — use ConfigRegistry for YAML loading instead of direct file read
  **Dependencies**: 1.5, 1.4

- [ ] 1.7 Write tests for ModelConfig using ConfigRegistry — verify model registry loads from new path
  **Spec scenarios**: settings-mgmt.2 (resolution), settings-mgmt.10 (DB override wins)
  **Dependencies**: 1.2

- [ ] 1.8 Update `src/config/models.py` — use ConfigRegistry for `load_model_registry()` YAML loading
  **Dependencies**: 1.7, 1.3

- [ ] 1.9 Write tests for voice/notification defaults loading via registry
  **Spec scenarios**: settings-mgmt.9 (precedence), settings-mgmt.10 (DB override wins)
  **Dependencies**: 1.2, 1.3

- [ ] 1.10 Update voice settings routes and notification preferences routes to use ConfigRegistry for defaults
  **Dependencies**: 1.9

- [ ] 1.11 Register all domains at app startup — add registry initialization to FastAPI lifespan or module-level setup
  **Dependencies**: 1.2, 1.3

- [ ] 1.12 Update existing tests that reference old YAML paths (`src/config/prompts.yaml`, `src/config/model_registry.yaml`)
  **Dependencies**: 1.4, 1.8

## Phase 2: Frontend Tab Routing

### Frontend — Settings Layout

- [ ] 2.1 Write E2E tests for tabbed settings navigation — tab clicks, URL routing, direct navigation, default tab
  **Spec scenarios**: settings-mgmt.13 (tab navigation), settings-mgmt.14 (tab URL routing), settings-mgmt.15 (direct URL)
  **Design decisions**: D5 (React Router Outlet)
  **Dependencies**: None

- [ ] 2.2 Create `web/src/routes/settings/` directory with sub-page components
  - Extract `PromptsSettings` from settings.tsx (wraps PromptManager)
  - Extract `ModelsSettings` from settings.tsx (wraps ModelConfigurator)
  - Extract `VoiceSettings` from settings.tsx (wraps VoiceConfigurator)
  - Extract `NotificationsSettings` from settings.tsx (wraps NotificationConfigurator + PushNotificationToggle)
  **Dependencies**: 2.1

- [ ] 2.3 Convert `web/src/routes/settings.tsx` to SettingsLayout with tab bar and Outlet
  **Dependencies**: 2.2

- [ ] 2.4 Update router configuration — add nested routes under `/settings` with index redirect to `/settings/prompts`
  **Dependencies**: 2.3

- [ ] 2.5 Update navigation links — sidebar/header links to `/settings` should still work (layout handles redirect)
  **Dependencies**: 2.4

## Phase 3: Status Page + Connection Endpoint Migration

### Backend — Status Endpoint

- [ ] 3.1 Write tests for new status endpoint and redirect
  **Spec scenarios**: settings-mgmt.11 (new endpoint), settings-mgmt.12 (redirect)
  **Design decisions**: D6 (connection status moves to /status)
  **Dependencies**: None

- [ ] 3.2 Create `src/api/status_routes.py` — move connection health endpoint to `/api/v1/status/connections`
  **Dependencies**: 3.1

- [ ] 3.3 Add 307 redirect from `/api/v1/settings/connections` to `/api/v1/status/connections` in `connection_status_routes.py`
  **Dependencies**: 3.2

- [ ] 3.4 Register new status router in `src/api/app.py`
  **Dependencies**: 3.2

### Frontend — Status Page

- [ ] 3.5 Write E2E test for `/status` page — dashboard renders, auto-refresh works
  **Spec scenarios**: settings-mgmt.16 (top-level status page)
  **Dependencies**: None

- [ ] 3.6 Create `web/src/routes/status.tsx` — move ConnectionDashboard to top-level page
  **Dependencies**: 3.5

- [ ] 3.7 Update frontend API client — change connection status endpoint to `/api/v1/status/connections`
  **Dependencies**: 3.3

- [ ] 3.8 Add `/status` route to router and update navigation (sidebar/header)
  **Dependencies**: 3.6

- [ ] 3.9 Remove ConnectionDashboard from settings tabs (it's now on /status)
  **Dependencies**: 3.6, 2.3

## Phase 4: Documentation and Cleanup

- [ ] 4.1 Update `CLAUDE.md` configuration section to reference `settings/` directory
  **Dependencies**: 1.3

- [ ] 4.2 Update `docs/SETUP.md` and `docs/MODEL_CONFIGURATION.md` to reference new YAML paths
  **Dependencies**: 1.3

- [ ] 4.3 Remove old YAML files from `src/config/` if symlinks were not used (or verify symlinks work)
  **Dependencies**: 1.12

- [ ] 4.4 Update `docs/GOTCHAS.md` if any new gotchas emerge from the migration
  **Dependencies**: All previous tasks
