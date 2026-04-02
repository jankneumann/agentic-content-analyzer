# Spec: Model Registry API

**Capability**: `model-registry-api`
**Status**: Draft

## Overview

Expose the model registry (models, provider configs, pricing) and pricing
extraction through CLI, REST API, and MCP tool interfaces. A shared
`ModelRegistryService` provides the business logic; each interface is a thin adapter.

## Scenarios

### model-registry-api.1 — List all models

**Given** the model registry is loaded from `settings/models.yaml`
**When** a client requests the model list (CLI/API/MCP)
**Then** the response SHALL include all models with:
  - `id`, `name`, `family`, capability flags (`supports_vision`, `supports_video`, `supports_audio`)
  - `default_version`
  - List of providers that offer this model
  - Default pricing (from the primary provider)
**And** the list MAY be filtered by `family` (e.g., "claude", "gemini", "gpt")

### model-registry-api.2 — Get model detail with provider pricing

**Given** a valid `model_id` (e.g., "claude-sonnet-4-5")
**When** a client requests model details
**Then** the response SHALL include the model info AND all provider configurations:
  - Per provider: `provider_model_id`, `cost_per_mtok_input`, `cost_per_mtok_output`, `context_window`, `max_output_tokens`, `tier`
**And** if the `model_id` is not found, the response SHALL return 404 / error message

### model-registry-api.3 — Trigger pricing refresh

**Given** valid admin credentials
**When** a client triggers a pricing refresh (optionally limited to specific providers)
**Then** the system SHALL:
  1. Fetch pricing pages from the specified (or all) providers
  2. Extract structured pricing via LLM
  3. Diff against the current registry
  4. Return a report with diffs, new models, and errors
**And** if `dry_run=true` (default), the system SHALL NOT modify `models.yaml`
**And** if `dry_run=false`, the system SHALL apply changes to `models.yaml`

### model-registry-api.4 — Pricing refresh status

**Given** a pricing refresh has been previously executed
**When** a client requests refresh status
**Then** the response SHALL include the last refresh timestamp and summary
**And** if no refresh has been executed, the response SHALL indicate that

### model-registry-api.5 — CLI list-models tabular output

**Given** the user runs `aca manage list-models`
**Then** the output SHALL display a formatted table with model ID, family, name, capabilities
**And** with `--json` flag, SHALL output the same data as JSON
**And** with `--family <name>` flag, SHALL filter to that family only

### model-registry-api.6 — CLI model-info detail output

**Given** the user runs `aca manage model-info <model-id>`
**Then** the output SHALL display model info followed by a pricing table showing each provider
**And** with `--json` flag, SHALL output as JSON
**And** if the model is not found, SHALL display an error and exit with code 1

### model-registry-api.7 — MCP tools

**Given** the MCP server is running
**Then** it SHALL expose:
  - `list_models(family?: str)` → JSON array of model summaries
  - `get_model_pricing(model_id: str)` → JSON with model detail + provider pricing
  - `refresh_model_pricing(providers?: list[str], dry_run?: bool)` → JSON refresh report

## Non-Functional Requirements

- API response time for read endpoints SHALL be < 50ms (in-memory registry)
- Pricing refresh SHALL timeout at 120s max
- All endpoints SHALL require admin authentication (`verify_admin_key`)
