# Proposal: Model Pricing Interfaces

**Change ID**: `model-pricing-interfaces`
**Status**: Proposed
**Date**: 2026-04-02

## Why

Keeping `settings/models.yaml` up to date with the latest model availability and pricing across Anthropic, OpenAI, Google AI, and AWS Bedrock is a manual, error-prone process. The system already has a `ModelPricingExtractor` service that can fetch pricing pages, extract structured data via LLM, and diff/apply changes to the YAML.

However, the extractor is only accessible via a single CLI command. To make model pricing information genuinely useful across the system, we need:

1. **CLI** — Enhanced commands for both querying model info and triggering pricing refreshes
2. **API** — REST endpoints so the frontend and external tools can display model info and costs
3. **MCP** — Tools so AI agents can query model pricing and trigger updates programmatically

## What Changes

### 1. CLI Interface (Enhancement)

Extend `src/cli/manage_commands.py` with additional commands:
- `aca manage list-models` — tabular listing of all models with family, capabilities, default provider
- `aca manage model-info <model-id>` — detailed view of a model including per-provider pricing
- `aca manage update-model-pricing` — already exists; no changes needed

### 2. API Interface (New)

New FastAPI router at `src/api/model_routes.py` under `/api/v1/models/`:
- `GET /api/v1/models/` — list all models in the registry
- `GET /api/v1/models/{model_id}` — model details + provider configs
- `GET /api/v1/models/{model_id}/pricing` — pricing breakdown across providers
- `POST /api/v1/models/pricing/refresh` — trigger pricing extraction (synchronous, admin-only)
- `GET /api/v1/models/pricing/status` — last refresh report/status

All endpoints require admin auth (via `verify_admin_key` dependency).

### 3. MCP Interface (New)

Add tools to `src/mcp_server.py`:
- `list_models` — list models with optional family filter
- `get_model_pricing` — get pricing for a specific model across providers
- `refresh_model_pricing` — trigger extraction from provider pages (dry-run by default)

### 4. Shared Service Layer

Create `src/services/model_registry_service.py` — a thin service layer that wraps `src/config/models.py` registry access and `ModelPricingExtractor` into a unified API. All three interfaces (CLI, API, MCP) delegate to this service.

## Approaches Considered

### Approach A: Thin Service + Three Interfaces (Recommended)

**Description**: Create a `ModelRegistryService` that wraps the existing config module and pricing extractor. Each interface (CLI, API, MCP) is a thin adapter calling into this service. The service returns Pydantic models that the API can serialize directly, the CLI can format as tables, and MCP can return as JSON.

**Pros**:
- Single source of truth for business logic
- Follows existing Client-Service pattern in the codebase
- Easy to test: mock one service for all interface tests
- Pydantic models auto-generate OpenAPI docs

**Cons**:
- One additional abstraction layer over the config module
- Service mostly delegates to existing code initially

**Effort**: M

### Approach B: Direct Config Access Per Interface

**Description**: Each interface directly imports from `src/config/models.py` and `ModelPricingExtractor`. No intermediate service layer. API routes construct Pydantic response models inline.

**Pros**:
- Fewer files, less indirection
- Faster to implement initially

**Cons**:
- Duplicated logic across CLI, API, and MCP (e.g., filtering by family, formatting pricing comparisons)
- Harder to test: must mock config module in three places
- Any change to data presentation must be updated in three places

**Effort**: S

### Approach C: Full CRUD with Database-Backed Registry

**Description**: Migrate the YAML registry into a database table. The service writes pricing data to the DB, and the YAML becomes a seed file. API supports full CRUD (add/edit/delete models).

**Pros**:
- More flexible: supports runtime model additions without YAML editing
- Fits naturally with database-backed settings pattern
- History tracking via DB

**Cons**:
- Significant migration effort (Alembic migration, seed data, etc.)
- Overkill for current needs (14 models, 23 configs)
- Breaks the simple "edit YAML, restart" workflow
- Adds DB dependency to model resolution hot path

**Effort**: L

### Selected Approach

**Approach A: Thin Service + Three Interfaces** — best balance of clean architecture and pragmatism. The shared service layer prevents duplication across three interfaces without over-engineering into a full database migration. The existing YAML-based workflow stays intact.

## Scope

### In Scope
- ModelRegistryService with Pydantic response models
- CLI commands: `list-models`, `model-info`
- API router: 5 endpoints under `/api/v1/models/`
- MCP tools: 3 tools added to existing `mcp_server.py`
- Unit tests for service, API, and CLI
- JSON output support for all CLI commands

### Out of Scope
- Database-backed model registry (future consideration)
- Frontend UI for model pricing display (separate change)
- Automated scheduling of pricing refresh (can use existing cron/Celery later)
- Changes to how `ModelConfig` resolves models at runtime
