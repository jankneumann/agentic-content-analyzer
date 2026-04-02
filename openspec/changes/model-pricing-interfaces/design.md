# Design: Model Pricing Interfaces

**Change ID**: `model-pricing-interfaces`

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Interfaces                           │
│  ┌─────────┐   ┌──────────────┐   ┌──────────────────┐  │
│  │   CLI   │   │   FastAPI    │   │    MCP Server    │  │
│  │ manage  │   │ /api/v1/     │   │  mcp_server.py   │  │
│  │ commands│   │ models/      │   │                  │  │
│  └────┬────┘   └──────┬───────┘   └────────┬─────────┘  │
│       │               │                    │             │
│       └───────────────┼────────────────────┘             │
│                       ▼                                  │
│           ┌───────────────────────┐                      │
│           │ ModelRegistryService  │  ← Shared service    │
│           │ (Pydantic models)     │                      │
│           └───────┬───────────────┘                      │
│                   │                                      │
│       ┌───────────┼──────────────┐                       │
│       ▼                          ▼                       │
│  ┌──────────┐          ┌──────────────────┐              │
│  │ models.py│          │ ModelPricing-    │              │
│  │ (config) │          │ Extractor        │              │
│  │ Registry │          │ (fetch+LLM)     │              │
│  └──────────┘          └──────────────────┘              │
│       │                        │                         │
│       ▼                        ▼                         │
│  settings/              Provider pricing                 │
│  models.yaml            pages (HTTP)                     │
└──────────────────────────────────────────────────────────┘
```

## Design Decisions

### D1: Shared Pydantic response models

The `ModelRegistryService` returns Pydantic models (`ModelSummary`, `ModelDetail`,
`ProviderPricingInfo`, `PricingRefreshReport`). These are directly serializable
by FastAPI, convertible to dicts for MCP `_serialize()`, and formattable by the
CLI with Rich tables.

**Rejected alternative**: Returning plain dicts. Dicts have no schema
validation, no auto-generated OpenAPI docs, and require ad-hoc formatting in
each interface.

### D2: Complement existing model_settings_routes, don't replace

`src/api/model_settings_routes.py` already serves `/api/v1/settings/models`
for managing model-per-step assignments. Our new router lives at
`/api/v1/models/` and focuses on the registry catalog and pricing extraction.
These are orthogonal concerns — step assignment vs. model catalog.

**Rejected alternative**: Extending model_settings_routes. That file focuses
on the settings CRUD pattern (get/set/reset per step). Adding catalog and
pricing extraction would violate SRP.

### D3: Synchronous pricing refresh

The pricing refresh endpoint runs synchronously with a 120s timeout. This is
acceptable because:
- It's admin-only (no user-facing latency concerns)
- The operation fetches 4 pages + 4 LLM calls (~30-60s typical)
- Adding Celery/queue complexity is not justified for a rarely-used operation

**Rejected alternative**: Background Celery task with status polling. Over-
engineered for a task run manually every few weeks.

### D4: In-memory last-refresh state

The last pricing refresh report is stored in a module-level variable
(`_last_refresh_report`). This is simple and sufficient since:
- Only one refresh runs at a time
- The report is informational, not critical state
- Server restart clears it (acceptable — refreshes are rare)

**Rejected alternative**: Database-persisted refresh history. Adds a migration
and table for data that's only useful for the current session.

## File Changes

### New Files
| File | Purpose |
|------|---------|
| `src/services/model_registry_service.py` | Shared service with Pydantic response models |
| `src/api/model_registry_routes.py` | FastAPI router for `/api/v1/models/` |

### Modified Files
| File | Change |
|------|--------|
| `src/cli/manage_commands.py` | Add `list-models` and `model-info` commands |
| `src/mcp_server.py` | Add 3 model/pricing tools |
| `src/api/app.py` | Register new `model_registry_router` |

### Test Files
| File | Purpose |
|------|---------|
| `tests/test_services/test_model_registry_service.py` | Service unit tests |
| `tests/api/test_model_registry_routes.py` | API endpoint tests |
