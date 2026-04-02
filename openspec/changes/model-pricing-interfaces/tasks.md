# Tasks: Model Pricing Interfaces

**Change ID**: `model-pricing-interfaces`
**Selected Approach**: A — Thin Service + Three Interfaces

## Phase 1: Shared Service Layer

- [ ] 1.1 Write tests for ModelRegistryService — list models, get detail, pricing refresh delegation
  **Spec scenarios**: model-registry-api.1 (list models), model-registry-api.2 (model detail), model-registry-api.3 (pricing refresh)
  **Design decisions**: D1 (Pydantic response models)
  **Dependencies**: None

- [ ] 1.2 Create `src/services/model_registry_service.py` — ModelRegistryService with Pydantic response models
  - `ModelSummary` — id, name, family, capabilities, providers list, default cost
  - `ProviderPricingInfo` — provider, provider_model_id, costs, context_window, max_output, tier
  - `ModelDetail` — ModelSummary + list of ProviderPricingInfo
  - `PricingRefreshReport` — Pydantic wrapper around extractor's PricingReport
  - `list_models(family?: str)` → list[ModelSummary]
  - `get_model(model_id: str)` → ModelDetail | None
  - `refresh_pricing(providers?: list[str], dry_run: bool)` → PricingRefreshReport
  - `get_last_refresh()` → PricingRefreshReport | None
  **Dependencies**: 1.1

## Phase 2: API Interface

- [ ] 2.1 Write tests for model registry API routes — all 5 endpoints, auth, error cases
  **Spec scenarios**: model-registry-api.1, .2, .3, .4
  **Design decisions**: D2 (complement not replace model_settings_routes), D3 (sync refresh)
  **Dependencies**: 1.2

- [ ] 2.2 Create `src/api/model_registry_routes.py` — FastAPI router
  - `GET /api/v1/models/` → list models (optional `family` query param)
  - `GET /api/v1/models/{model_id}` → model detail with provider pricing
  - `GET /api/v1/models/{model_id}/pricing` → pricing-only view across providers
  - `POST /api/v1/models/pricing/refresh` → trigger extraction (body: providers, dry_run)
  - `GET /api/v1/models/pricing/status` → last refresh report
  - All endpoints use `dependencies=[Depends(verify_admin_key)]`
  **Dependencies**: 2.1

- [ ] 2.3 Register router in `src/api/app.py`
  - Import and include `model_registry_router`
  **Dependencies**: 2.2

## Phase 3: CLI Interface

- [ ] 3.1 Write tests for CLI list-models and model-info commands
  **Spec scenarios**: model-registry-api.5 (list-models), model-registry-api.6 (model-info)
  **Dependencies**: 1.2

- [ ] 3.2 Add `list-models` command to `src/cli/manage_commands.py`
  - Table output using Rich: ID, Family, Name, Vision, Video, Audio, Providers
  - `--family` filter option
  - `--json` output via `is_json_mode()`
  **Dependencies**: 3.1

- [ ] 3.3 Add `model-info` command to `src/cli/manage_commands.py`
  - Model summary header
  - Provider pricing table: Provider, API ID, Input $/MTok, Output $/MTok, Context, Max Output
  - Error if model not found (exit code 1)
  - `--json` output via `is_json_mode()`
  **Dependencies**: 3.1

## Phase 4: MCP Interface

- [ ] 4.1 Add `list_models` tool to `src/mcp_server.py`
  - Optional `family` parameter
  - Returns `_serialize()` of model summaries
  **Spec scenarios**: model-registry-api.7
  **Dependencies**: 1.2

- [ ] 4.2 Add `get_model_pricing` tool to `src/mcp_server.py`
  - Required `model_id` parameter
  - Returns model detail with all provider pricing
  **Spec scenarios**: model-registry-api.7
  **Dependencies**: 1.2

- [ ] 4.3 Add `refresh_model_pricing` tool to `src/mcp_server.py`
  - Optional `providers` (comma-separated string), `dry_run` (default True)
  - Returns refresh report
  **Spec scenarios**: model-registry-api.3, model-registry-api.7
  **Dependencies**: 1.2

## Phase 5: Integration Verification

- [ ] 5.1 Run full test suite and fix any failures
  **Dependencies**: 2.3, 3.3, 4.3

- [ ] 5.2 Verify CLI commands work end-to-end (manual smoke test)
  - `aca manage list-models`
  - `aca manage list-models --family claude`
  - `aca manage model-info claude-sonnet-4-5`
  - `aca manage model-info nonexistent-model` (should error)
  **Dependencies**: 5.1
