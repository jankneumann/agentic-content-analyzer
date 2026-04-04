# Proposal: Infrastructure Cost Predictions (Neon + Resend)

## Change ID
`infra-pricing-predictions`

## Status
Draft

## Why

The newsletter aggregator runs on a multi-service stack (Neon Postgres, email delivery, LLM APIs), but there is no unified way to predict monthly infrastructure costs. The existing `ModelConfig.get_cost_estimate()` covers LLM token costs, but ignores database compute/storage and email delivery — two significant cost drivers in production.

Operators need to:
1. **Predict costs before scaling** — understand the monthly bill impact of increasing ingestion volume, storage, or email subscribers.
2. **Compare plan tiers** — determine whether the free tier suffices or a paid plan is needed for their usage profile.
3. **Keep pricing current** — Neon and Resend update pricing periodically (Neon dropped 25% after the Databricks acquisition). Manual YAML edits are error-prone.

## What Changes

### 1. Pricing Configuration (`settings/pricing.yaml`)
A YAML-based pricing registry for Neon and Resend, following the same pattern as `settings/models.yaml`. Contains plan tiers, per-unit costs, overage rates, and default usage assumptions.

### 2. Cost Prediction Service (`src/services/infrastructure_pricing_service.py`)
Calculates monthly cost estimates for Neon (compute hours, storage, PITR, snapshots), Resend (email volume with tiered overage), and LLM (wrapping existing `ModelConfig.get_cost_estimate()`). Returns structured breakdowns and a grand total.

### 3. Pricing Extractor (`src/services/infrastructure_pricing_extractor.py`)
Automated pricing extraction from Neon/Resend pricing pages. Reuses `fetch_pricing_page()` from `model_pricing_extractor.py` and follows the same fetch → LLM extract → diff/apply pattern with service-specific prompts.

### 4. API Routes (`src/api/pricing_routes.py`)
Seven endpoints under `/api/v1/pricing/` for cost prediction, per-service estimates, plan comparisons, and pricing refresh.

### Scope Boundaries
- **In scope**: Cost prediction, plan comparison, automated pricing extraction for Neon and Resend.
- **Out of scope**: Resend email delivery integration (codebase uses Gmail API), actual usage tracking/billing, frontend dashboard.

## Approaches Considered

### Approach A: Standalone Service with YAML Config (Recommended)

**Description**: Separate `InfrastructurePricingService` with its own YAML config (`settings/pricing.yaml`), independent of `ModelConfig`. Extraction follows the same pattern as `ModelPricingExtractor` but as a separate class importing shared utilities.

**Pros**:
- Clean separation of concerns — infrastructure pricing vs. LLM pricing
- YAML config is independently editable without touching model configuration
- Extraction can be triggered independently (infrastructure pricing changes less frequently)
- Follows existing project patterns (YAML → Service → API)

**Cons**:
- Two separate refresh endpoints to manage
- Pricing YAML is not yet registered as a ConfigRegistry domain (needs refinement)

**Effort**: S (implementation exists, needs ConfigRegistry registration + tests)

### Approach B: Extend ModelConfig with Infrastructure Costs

**Description**: Add Neon/Resend pricing to `settings/models.yaml` and extend `ModelConfig.get_cost_estimate()` to include infrastructure costs alongside LLM estimates.

**Pros**:
- Single source of truth for all cost data
- One refresh endpoint covers everything
- `get_cost_estimate()` returns truly "total" costs

**Cons**:
- Violates single responsibility — `ModelConfig` becomes a god object for all pricing
- `models.yaml` grows with unrelated infrastructure config
- Infrastructure pricing structure (plan tiers) is fundamentally different from LLM pricing (per-token)
- Harder to test — infrastructure changes require loading the full model registry

**Effort**: M (refactoring existing code + merging data models)

### Approach C: Database-Backed Pricing with Admin UI

**Description**: Store pricing tiers in PostgreSQL tables with an admin UI for editing. Extraction writes to DB instead of YAML. API reads from DB.

**Pros**:
- Runtime-editable without redeployment
- Audit trail for pricing changes
- Natural fit for the admin panel

**Cons**:
- Requires database migration (new tables)
- Over-engineered for relatively static data (Neon/Resend change pricing rarely)
- Loses the simplicity of YAML config that matches the rest of the settings pattern
- More complex deployment (migration step)

**Effort**: L (DB models, migrations, admin UI, extraction rewrite)

### Selected Approach

**Approach A: Standalone Service with YAML Config** — selected because it follows the existing project conventions (YAML-driven config, service layer, API routes), keeps infrastructure pricing cleanly separated from LLM pricing, and the implementation already exists. Refinements needed: ConfigRegistry domain registration and test coverage.

## Dependencies

- `src/services/model_pricing_extractor.py` — reuses `fetch_pricing_page()` function
- `src/services/llm_router.py` — used by extractor for LLM-based pricing extraction
- `src/config/models.py` — `ModelConfig.get_cost_estimate()` wrapped for LLM cost component
- `settings/` directory — follows conventions established by `models.yaml`, `voice.yaml`, etc.

## Risks

| Risk | Mitigation |
|------|------------|
| Neon/Resend block automated page scraping | Extractor tries `.md` agent-friendly URLs first, falls back to HTML. `fetch_pricing_page` uses browser-like user-agent. |
| Pricing page structure changes break LLM extraction | Extraction runs in dry_run mode by default. Diffs are reviewed before applying. |
| YAML config drift from actual prices | Refresh endpoint + clear "Last updated" timestamp in YAML header. |
