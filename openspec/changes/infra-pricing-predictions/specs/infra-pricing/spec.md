# infra-pricing Specification

## Purpose

Provide unified monthly cost predictions for Neon Postgres, Resend email, and LLM API services, with automated pricing extraction from live provider pages.

## ADDED Requirements

### Requirement: Neon Cost Estimation

The `InfrastructurePricingService` SHALL estimate monthly Neon Postgres costs based on plan tier and usage parameters.

#### Scenario: Free tier estimation
- **WHEN** `estimate_neon_cost(plan="free")` is called
- **THEN** it SHALL return a `NeonCostBreakdown` with `total=0.0`
- **AND** compute hours SHALL be capped at the free tier's `included_compute_hours`
- **AND** storage SHALL be capped at the free tier's `max_storage_gb`

#### Scenario: Launch plan usage-based estimation
- **WHEN** `estimate_neon_cost(plan="launch", compute_hours_per_day=2, storage_gb=5)` is called
- **THEN** `compute_cost` SHALL equal `(2 * 30) * cost_per_compute_hour` from pricing.yaml
- **AND** `storage_cost` SHALL equal `5 * cost_per_storage_gb` from pricing.yaml
- **AND** `total` SHALL be the maximum of (usage total, monthly_price minimum spend)

#### Scenario: Tiered storage pricing above 50 GB
- **WHEN** `estimate_neon_cost(plan="launch", storage_gb=80)` is called
- **THEN** storage cost SHALL be `50 * cost_per_storage_gb + 30 * cost_per_storage_gb_over_50`

#### Scenario: Minimum spend enforcement
- **WHEN** usage total is less than the plan's `monthly_price`
- **THEN** `total` SHALL equal the plan's `monthly_price` (not the usage total)

#### Scenario: Default parameters from YAML
- **WHEN** `estimate_neon_cost()` is called with no arguments
- **THEN** it SHALL use default values from the `neon.defaults` section of pricing.yaml

### Requirement: Resend Cost Estimation

The `InfrastructurePricingService` SHALL estimate monthly Resend email costs based on plan tier and email volume.

#### Scenario: Free tier within limits
- **WHEN** `estimate_resend_cost(plan="free", emails_per_month=500)` is called
- **THEN** it SHALL return `total=0.0` and `overage_cost=0.0`
- **AND** `included_emails` SHALL be the free tier's `emails_per_month` from pricing.yaml

#### Scenario: Pro plan with overage
- **WHEN** `estimate_resend_cost(plan="pro", emails_per_month=55000)` is called
- **AND** the pro plan includes 50000 emails per month
- **THEN** `overage_emails` SHALL be 5000
- **AND** `overage_cost` SHALL be `ceil(5000 / 1000) * overage_per_1000_emails`
- **AND** `total` SHALL be `monthly_price + overage_cost`

#### Scenario: Overage billed in 1000-email buckets
- **WHEN** overage emails is 1 (one email over quota)
- **THEN** the system SHALL charge for a full bucket of 1000 emails

#### Scenario: Free tier has no pay-as-you-go
- **WHEN** `estimate_resend_cost(plan="free", emails_per_month=5000)` is called
- **AND** the free tier has `pay_as_you_go: false`
- **THEN** `overage_cost` SHALL be 0.0

### Requirement: Combined Cost Prediction

The `InfrastructurePricingService` SHALL produce a unified cost prediction combining Neon, Resend, and LLM costs.

#### Scenario: Full prediction with defaults
- **WHEN** `predict_monthly_costs()` is called with no arguments
- **THEN** it SHALL return a `CostPrediction` with `neon`, `resend`, and `llm` breakdowns
- **AND** `grand_total` SHALL equal the sum of all three service totals

#### Scenario: LLM costs delegate to ModelConfig
- **WHEN** `estimate_llm_cost()` is called
- **THEN** it SHALL delegate to `ModelConfig.get_cost_estimate()`
- **AND** wrap the result into a structured `LLMCostBreakdown`

#### Scenario: Custom parameters flow through
- **WHEN** `predict_monthly_costs(neon_plan="scale", resend_plan="pro", emails_per_month=80000)` is called
- **THEN** each sub-estimate SHALL use the provided parameters
- **AND** non-provided parameters SHALL use their respective defaults

### Requirement: Plan Comparison

The service SHALL compare costs across plan tiers and recommend the most cost-effective option.

#### Scenario: Neon plan comparison
- **WHEN** `compare_neon_plans(compute_hours_per_day=1, storage_gb=3)` is called
- **THEN** it SHALL return a `PlanComparison` with costs for all Neon plans
- **AND** if usage fits within free tier limits, `recommended` SHALL be "free"

#### Scenario: Neon comparison exceeding free tier
- **WHEN** usage exceeds free tier's `included_compute_hours` or `max_storage_gb`
- **THEN** `recommended` SHALL be the cheapest paid plan

#### Scenario: Resend plan comparison
- **WHEN** `compare_resend_plans(emails_per_month=500)` is called
- **THEN** it SHALL return costs for all non-enterprise Resend plans
- **AND** `recommended` SHALL be the plan with the lowest total cost

### Requirement: Pricing YAML Configuration

Infrastructure pricing SHALL be stored in `settings/pricing.yaml` with a defined structure.

#### Scenario: Neon section structure
- **GIVEN** `settings/pricing.yaml`
- **THEN** it SHALL have a `neon` section with `plans` (keyed by tier), and `defaults`
- **AND** each paid plan SHALL include: `monthly_price`, `cost_per_compute_hour`, `cost_per_storage_gb`, `cost_per_pitr_gb`

#### Scenario: Resend section structure
- **GIVEN** `settings/pricing.yaml`
- **THEN** it SHALL have a `resend` section with `plans` (keyed by tier), `marketing`, `overage_cap_multiplier`, and `defaults`
- **AND** each paid plan with pay-as-you-go SHALL include `overage_per_1000_emails`

#### Scenario: Last updated timestamp
- **GIVEN** `settings/pricing.yaml`
- **THEN** it SHALL contain a `# Last updated:` comment line for tracking currency

### Requirement: Pricing API Endpoints

The system SHALL expose cost prediction and plan comparison via REST API under `/api/v1/pricing/`.

#### Scenario: Predict total costs
- **WHEN** `GET /api/v1/pricing/predict` is called
- **THEN** it SHALL return a `CostPrediction` JSON object
- **AND** all query parameters SHALL be optional with YAML defaults

#### Scenario: Per-service estimates
- **WHEN** `GET /api/v1/pricing/neon` or `GET /api/v1/pricing/resend` is called
- **THEN** it SHALL return the respective service cost breakdown

#### Scenario: Plan comparisons
- **WHEN** `GET /api/v1/pricing/neon/compare` or `GET /api/v1/pricing/resend/compare` is called
- **THEN** it SHALL return a `PlanComparison` with per-plan costs and a recommendation

#### Scenario: Authentication required
- **WHEN** any `/api/v1/pricing/` endpoint is called without a valid admin API key
- **THEN** it SHALL return 401 Unauthorized

### Requirement: Automated Pricing Extraction

The `InfrastructurePricingExtractor` SHALL fetch live pricing from Neon and Resend pages and diff against `settings/pricing.yaml`.

#### Scenario: Fetch with agent-friendly URLs first
- **WHEN** extraction runs for a service
- **THEN** it SHALL try `.md` URLs before falling back to HTML URLs
- **AND** concatenate all successfully fetched pages

#### Scenario: LLM-based structured extraction
- **WHEN** page markdown is fetched
- **THEN** it SHALL send service-specific prompts to the LLM via `LLMRouter`
- **AND** parse the response as structured JSON with plan tiers and costs

#### Scenario: Diff against current YAML
- **WHEN** extracted pricing differs from current `pricing.yaml` values
- **THEN** it SHALL produce `InfraPricingDiff` entries with service, plan, field, current_value, extracted_value

#### Scenario: Dry run mode (default)
- **WHEN** `run(dry_run=True)` is called
- **THEN** it SHALL report diffs without modifying `pricing.yaml`

#### Scenario: Apply mode updates YAML
- **WHEN** `run(dry_run=False)` is called with diffs
- **THEN** it SHALL apply targeted line-level edits to `pricing.yaml`
- **AND** preserve comments and formatting
- **AND** update the `# Last updated:` timestamp

#### Scenario: Reuse shared fetch infrastructure
- **WHEN** the extractor fetches pricing pages
- **THEN** it SHALL import and use `fetch_pricing_page` from `model_pricing_extractor`
- **AND** NOT duplicate the httpx + trafilatura pipeline

### Requirement: Pricing Refresh API

The system SHALL expose pricing extraction via REST API.

#### Scenario: Trigger refresh
- **WHEN** `POST /api/v1/pricing/refresh` is called with `{"dry_run": true}`
- **THEN** it SHALL run the extractor and return an `InfraPricingRefreshReport`

#### Scenario: Get last refresh status
- **WHEN** `GET /api/v1/pricing/refresh/status` is called
- **AND** a refresh has been executed in this process
- **THEN** it SHALL return the last `InfraPricingRefreshReport`

#### Scenario: No prior refresh
- **WHEN** `GET /api/v1/pricing/refresh/status` is called
- **AND** no refresh has been executed
- **THEN** it SHALL return a message indicating no refresh has been run
