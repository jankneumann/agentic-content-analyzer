# Design: Infrastructure Cost Predictions

## Architecture Overview

```
settings/pricing.yaml  ─────────────────────────────────┐
                                                         │
                                      ┌──────────────────▼──────────────────┐
                                      │  InfrastructurePricingService       │
                                      │  (src/services/infrastructure_      │
                                      │   pricing_service.py)               │
                                      │                                     │
                                      │  estimate_neon_cost()               │
                                      │  estimate_resend_cost()             │
                                      │  estimate_llm_cost()  ──────────┐   │
                                      │  predict_monthly_costs()        │   │
                                      │  compare_neon_plans()           │   │
                                      │  compare_resend_plans()         │   │
                                      └────────────┬────────────────────┘   │
                                                   │                        │
                                      ┌────────────▼────────────┐   ┌──────▼──────────┐
                                      │  pricing_routes.py      │   │  ModelConfig     │
                                      │  /api/v1/pricing/*      │   │  .get_cost_      │
                                      │                         │   │  estimate()      │
                                      │  GET  /predict          │   └─────────────────┘
                                      │  GET  /neon             │
                                      │  GET  /resend           │
                                      │  GET  /neon/compare     │
                                      │  GET  /resend/compare   │
                                      │  POST /refresh          │
                                      │  GET  /refresh/status   │
                                      └────────────┬────────────┘
                                                   │ (POST /refresh)
                                      ┌────────────▼────────────────────────┐
                                      │  InfrastructurePricingExtractor     │
                                      │  (src/services/infrastructure_      │
                                      │   pricing_extractor.py)             │
                                      │                                     │
                                      │  fetch (reuses fetch_pricing_page)  │
                                      │  extract (LLM via LLMRouter)        │
                                      │  diff (field-level comparison)      │
                                      │  apply (targeted YAML edits)        │
                                      └─────────────────────────────────────┘
```

## Design Decisions

### D1: Separate YAML File vs. Extending models.yaml

**Decision**: Use a dedicated `settings/pricing.yaml` file.

**Rationale**: Infrastructure pricing (plan tiers with flat monthly/per-unit costs) is structurally different from LLM pricing (per-token costs across provider×model matrix). Merging them into `models.yaml` would violate single responsibility and make the file harder to maintain. Separate files also allow independent refresh cadences.

**Trade-off**: Two files to keep updated vs. one. Mitigated by automated extraction.

### D2: Reuse `fetch_pricing_page` vs. Duplicating HTTP Logic

**Decision**: Import `fetch_pricing_page` from `model_pricing_extractor.py`.

**Rationale**: The function is domain-agnostic (httpx with browser UA + trafilatura HTML→markdown). Duplicating it would create drift. The function is already well-tested through the model extraction pipeline.

**Trade-off**: Creates a coupling between the two extractor modules. Acceptable because the shared dependency is stable and purely about HTTP fetching.

### D3: Service-Specific LLM Prompts vs. Generic Extraction

**Decision**: Use separate, purpose-built prompts for Neon and Resend extraction.

**Rationale**: Neon pricing involves compute hours, storage tiers, PITR, and snapshots. Resend pricing involves email volumes, overage buckets, and marketing add-ons. A generic prompt would produce unreliable extractions. Tailored prompts with explicit JSON schemas yield deterministic output.

### D4: Module-Level State for Last Refresh Report

**Decision**: Store last refresh report as module-level variable (same pattern as `model_registry_service.py`).

**Rationale**: Pricing refresh is infrequent (manual trigger) and the report only needs to survive for the process lifetime. Database persistence would be over-engineering for a status endpoint.

### D5: ConfigRegistry Domain Registration (Refinement)

**Decision**: Register `pricing` as a ConfigRegistry domain so `pricing.yaml` benefits from the same lifecycle as `models.yaml`.

**Rationale**: Currently `pricing.yaml` is loaded via direct file read fallback. Registering it enables: centralized initialization at startup, consistent error handling, potential for live reload without restart.

**Status**: Not yet implemented — identified as a refinement task.

## Data Models

### NeonCostBreakdown
```python
plan: str                    # "free" | "launch" | "scale"
base_price: float            # Minimum spend
compute_cost: float          # CU-hours × rate
storage_cost: float          # GB × tiered rate
pitr_cost: float             # History storage
snapshot_cost: float         # Snapshot storage
total: float                 # max(usage, minimum_spend)
compute_hours_per_month: float
storage_gb: float
pitr_gb: float
snapshot_gb: float
```

### ResendCostBreakdown
```python
plan: str                    # "free" | "pro" | "scale"
base_price: float            # Monthly subscription
overage_cost: float          # ceil(overage / 1000) × bucket_rate
total: float                 # base + overage
emails_per_month: int
included_emails: int
overage_emails: int
```

### CostPrediction
```python
neon: NeonCostBreakdown
resend: ResendCostBreakdown
llm: LLMCostBreakdown
grand_total: float           # Sum of all service totals
```

### PlanComparison
```python
service: str                 # "neon" | "resend"
plans: dict[str, float]      # plan_name → monthly_cost
recommended: str             # Best plan for usage
recommendation_reason: str   # Why this plan
```
