# Tasks: Infrastructure Cost Predictions

## Phase 1: Core Implementation (Complete)

These tasks represent the existing implementation on branch `claude/add-pricing-cost-predictions-oE6oi`.

- [x] 1.1 Create `settings/pricing.yaml` with Neon and Resend pricing tiers
  **Spec scenarios**: infra-pricing — Pricing YAML Configuration (all scenarios)
  **Design decisions**: D1 (separate YAML file)
  **Dependencies**: None

- [x] 1.2 Create `src/services/infrastructure_pricing_service.py` — cost estimation engine
  **Spec scenarios**: infra-pricing — Neon Cost Estimation (all), Resend Cost Estimation (all), Combined Cost Prediction (all), Plan Comparison (all)
  **Design decisions**: D1 (separate service), D4 (module-level state)
  **Dependencies**: 1.1

- [x] 1.3 Create `src/services/infrastructure_pricing_extractor.py` — automated pricing extraction
  **Spec scenarios**: infra-pricing — Automated Pricing Extraction (all)
  **Design decisions**: D2 (reuse fetch_pricing_page), D3 (service-specific prompts)
  **Dependencies**: 1.1, model_pricing_extractor.py (existing)

- [x] 1.4 Create `src/api/pricing_routes.py` — seven API endpoints
  **Spec scenarios**: infra-pricing — Pricing API Endpoints (all), Pricing Refresh API (all)
  **Dependencies**: 1.2, 1.3

- [x] 1.5 Register pricing router in `src/api/app.py`
  **Dependencies**: 1.4

## Phase 2: Refinements (Pending)

### Test Coverage

- [ ] 2.1 Write unit tests for `InfrastructurePricingService` — Neon cost calculations
  **Spec scenarios**: infra-pricing — Neon Cost Estimation (all 5 scenarios)
  **Design decisions**: D1 (verify YAML loading isolation)
  **Dependencies**: 1.2
  **File**: `tests/test_services/test_infrastructure_pricing_service.py`

- [ ] 2.2 Write unit tests for `InfrastructurePricingService` — Resend cost calculations
  **Spec scenarios**: infra-pricing — Resend Cost Estimation (all 4 scenarios)
  **Dependencies**: 1.2
  **File**: `tests/test_services/test_infrastructure_pricing_service.py`

- [ ] 2.3 Write unit tests for `InfrastructurePricingService` — combined prediction + plan comparison
  **Spec scenarios**: infra-pricing — Combined Cost Prediction (all 3 scenarios), Plan Comparison (all 3 scenarios)
  **Dependencies**: 1.2
  **File**: `tests/test_services/test_infrastructure_pricing_service.py`

- [ ] 2.4 Write unit tests for `InfrastructurePricingExtractor` — diff logic and YAML apply
  **Spec scenarios**: infra-pricing — Automated Pricing Extraction (diff, dry run, apply scenarios)
  **Design decisions**: D3 (prompt-based extraction mocked)
  **Dependencies**: 1.3
  **File**: `tests/test_services/test_infrastructure_pricing_extractor.py`

- [ ] 2.5 Write API integration tests for pricing endpoints
  **Spec scenarios**: infra-pricing — Pricing API Endpoints (all), Pricing Refresh API (all)
  **Dependencies**: 1.4, 2.1, 2.2, 2.3
  **File**: `tests/api/test_pricing_routes.py`

### ConfigRegistry Integration

- [ ] 2.6 Register `pricing` as a ConfigRegistry domain
  **Spec scenarios**: infra-pricing — Pricing YAML Configuration (all — enables centralized loading)
  **Design decisions**: D5 (ConfigRegistry registration)
  **Dependencies**: 1.1
  **File**: `src/config/config_registry.py`

- [ ] 2.7 Update `InfrastructurePricingService` to prefer ConfigRegistry over direct YAML read
  **Spec scenarios**: infra-pricing — Pricing YAML Configuration
  **Design decisions**: D5
  **Dependencies**: 2.6
  **File**: `src/services/infrastructure_pricing_service.py`

### Validation and Error Handling

- [ ] 2.8 Add input validation for plan names in API endpoints
  **Spec scenarios**: infra-pricing — Pricing API Endpoints (unknown plan should return 400)
  **Dependencies**: 1.4
  **File**: `src/api/pricing_routes.py`

- [ ] 2.9 Add pricing.yaml schema validation on startup
  **Dependencies**: 2.6
  **File**: `src/services/infrastructure_pricing_service.py`
