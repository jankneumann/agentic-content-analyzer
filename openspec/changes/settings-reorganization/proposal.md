# Settings Reorganization

## Status
Approved (Gate 1)

## Why

The current settings system has grown organically and suffers from three problems:

1. **Overloaded frontend page**: A single `/settings` route contains 5 unrelated sections (Prompts, Models, Voice, Notifications, Connections) in one scrollable page. Users must scroll to find what they need, and the page loads all data upfront.

2. **No clear config-vs-override boundary**: YAML files (`prompts.yaml`, `model_registry.yaml`) define defaults, but they live in `src/config/` mixed with Python modules. There's no dedicated directory that says "these are the configurable defaults." Profile YAML files live in `profiles/`, source YAML files live in `sources.d/`, but settings YAML files have no home.

3. **Connections is not a setting**: The health/connections dashboard is read-only system status, not a configurable setting. It occupies space in the settings page where users expect to change things.

## What Changes

### Backend
- Create a top-level `settings/` directory with organized YAML files:
  - `settings/prompts.yaml` (moved from `src/config/prompts.yaml`)
  - `settings/models.yaml` (moved from `src/config/model_registry.yaml`)
  - `settings/voice.yaml` (new, defaults extracted from `Settings` class)
  - `settings/notifications.yaml` (new, defaults extracted from `Settings` class)
- Update all Python imports and file references to point to the new locations
- Keep both DB tables (`prompt_overrides`, `settings_overrides`) as-is
- Create a `ConfigRegistry` service that coordinates YAML file loading for all settings domains. Domain-specific logic (template rendering, DB override resolution) remains in `PromptService`, `SettingsService`, and route handlers — the registry only handles YAML loading, caching, and validation
- Create a new `/api/v1/status/connections` endpoint (moved from `/api/v1/settings/connections`)

### Frontend
- Convert monolithic `/settings` page into a tabbed sub-page layout:
  - `/settings` redirects to `/settings/prompts` (or shows tab overview)
  - `/settings/prompts` — LLM prompt template management
  - `/settings/models` — Model-per-step configuration
  - `/settings/voice` — TTS/STT configuration
  - `/settings/notifications` — Event notification toggles
- Create new top-level `/status` page for connections health dashboard
- Each settings tab lazy-loads its own data (no upfront load of all settings)

### Settings Precedence (unchanged)
env var > DB override > YAML default

## Approaches Considered

### Approach A: Incremental Migration (Recommended)

Move YAML files first, update references, then restructure frontend routes. Each step is independently deployable and testable.

**Phase 1**: Create `settings/` directory, move YAML files, update Python references. No API changes — just internal file reorganization.

**Phase 2**: Add frontend tab routing under `/settings`. Extract each section into its own route component. No backend API changes needed — same endpoints, different page structure.

**Phase 3**: Move connections endpoint from `/api/v1/settings/connections` to `/api/v1/status/connections` (keep old route as redirect for backwards compat). Create `/status` frontend page.

**Pros:**
- Each phase is a small, reviewable PR
- No API breaking changes (redirects preserve old paths)
- Frontend and backend changes are independent — can be parallelized
- Existing tests continue to pass at each phase

**Cons:**
- Takes more total steps (3 phases)
- Temporary state where YAML files exist but frontend hasn't caught up
- Old connection endpoint redirect adds minor complexity

**Effort:** M

### Approach B: Full Restructure in One Pass

Do everything at once: move YAML files, restructure frontend, move connections endpoint, update all tests.

**Pros:**
- Single coherent changeset — no intermediate states
- No backwards-compatibility redirects needed
- Fewer total PRs to review

**Cons:**
- Large PR that's harder to review
- Higher risk of merge conflicts with in-progress changes (add-api-versioning, tree-index-chunking)
- Frontend and backend must land together
- If any part fails review, the whole thing blocks

**Effort:** M

### Approach C: Config Registry Service

Instead of just moving files, create a `ConfigRegistry` service that abstracts over all YAML-based configuration. Each settings domain (prompts, models, voice, notifications) registers with the registry, which handles file loading, validation, and change notification.

**Pros:**
- Future-proof: adding new settings domains is trivial (register + YAML file)
- Single validation pipeline for all settings
- Could support hot-reload of YAML changes without restart
- Clean abstraction for testing

**Cons:**
- More engineering work than the problem requires today
- Adds an abstraction layer over what is currently simple file reads
- Over-engineers for 4 YAML files
- Higher risk — new service could have bugs in the registry logic itself

**Effort:** M

### Selected Approach: C (Config Registry Service)

Approach A was initially recommended for its simplicity and lower risk. However, the user chose Approach C for its future-proof extensibility after considering the trade-offs:

**Why Approach A was demoted**: While Approach A minimizes risk per phase, it doesn't address the root cause — the settings surface area is actively growing (tree-index-chunking adds 5+ settings, more features are planned). Each new domain would require its own ad-hoc YAML loading pattern, perpetuating the current fragmentation.

**Why Approach C was selected**: The `ConfigRegistry` service will make adding new settings domains trivial — just drop a YAML file and register a domain. The additional engineering effort is justified because:
1. The settings surface area is actively growing — a unified loading pattern pays for itself quickly
2. A registry abstraction centralizes validation, default resolution, and error handling
3. Clean testing story — mock the registry, not individual YAML file reads
4. Consistent domain-registration pattern for all future features

**Migration strategy**: All code will be updated to use ConfigRegistry directly. No symlinks from old YAML paths — old paths (`src/config/prompts.yaml`, `src/config/model_registry.yaml`) will be deleted after migration.

**Hot-reload**: Mtime-based cache invalidation is deferred to a future enhancement. Phase 1 uses explicit `reload()` calls only.

Implementation will follow an incremental delivery order despite the larger scope:
- Phase 1: `ConfigRegistry` service + `settings/` directory with migrated YAML files
- Phase 2: Frontend tab routing under `/settings`
- Phase 3: `/status` page for connections

**Demoted approaches:**
- **Approach A (Incremental):** Simpler but doesn't address growing settings sprawl — each new domain requires ad-hoc loading
- **Approach B (Full Restructure):** Same scope as C minus the registry — no future-proofing benefit

## Out of Scope
- Profile system reorganization (`profiles/*.yaml`) — separate concern
- Source configuration reorganization (`sources.d/*.yaml`) — already well-organized
- Unifying `prompt_overrides` and `settings_overrides` DB tables — user preference to keep separate
- Adding new settings categories (e.g., sources management in UI)
- Settings import/export functionality

## Dependencies
- SHALL coordinate with `add-api-versioning` if it modifies router registration in `app.py` — both changes register routers in `src/api/app.py`, so merge order must be explicit
- `tree-index-chunking` adds new settings that SHALL use the `settings/` YAML structure and register via `ConfigRegistry` once this change lands
