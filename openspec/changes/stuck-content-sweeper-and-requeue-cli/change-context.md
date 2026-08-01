# Change Context: stuck-content-sweeper-and-requeue-cli

## Requirement Traceability Matrix

| Req ID | Spec Source | Description | Contract Ref | Design Decision | Files Changed | Test(s) | Evidence |
|--------|------------|-------------|-------------|----------------|---------------|---------|----------|
| content-state-reconciliation.1 | `specs/content-state-reconciliation/spec.md` — Scanning and reports are strictly bounded | One page is limited to 1..100 candidates and reports expose only a closed, non-sensitive projection with a keyset continuation. | `openspec/contracts/content-workflows/openapi/v1.yaml#/components/schemas/ContentReconciliationReport` | D10 | `openspec/contracts/content-workflows/openapi/v1.yaml`; generated Python/TypeScript mirrors; `tests/contract/test_canonical_workflow_contracts.py` | `test_content_reconciliation_openapi_matches_change_contract`, `test_content_reconciliation_contract_is_closed_bounded_and_safe` | --- |
| content-state-reconciliation.2 | `specs/content-state-reconciliation/spec.md` — Dry-run is reconciliation-read-only | HTTP and CLI default to dry-run, represented by an optional `apply=false` request field and explicit report mode. | `openspec/contracts/content-workflows/openapi/v1.yaml#/components/schemas/ContentReconciliationRequest` | D8 | `openspec/contracts/content-workflows/openapi/v1.yaml`; generated Python/TypeScript mirrors; `tests/contract/test_canonical_workflow_contracts.py` | `test_content_reconciliation_request_defaults_to_one_bounded_dry_run_page`, `test_generated_reconciliation_models_are_strict_and_default_to_dry_run` | --- |
| content-state-reconciliation.3 | `specs/content-state-reconciliation/spec.md` — Apply action evidence is atomic | Report items carry explicit before/after content, operation, and retry projections plus closed actions and reasons. | `openspec/contracts/content-workflows/openapi/v1.yaml#/components/schemas/ContentReconciliationItem` | D9 | `openspec/contracts/content-workflows/openapi/v1.yaml`; generated Python/TypeScript mirrors; `scripts/generate_workflow_contracts.py`; `tests/contract/test_canonical_workflow_contracts.py` | `test_content_reconciliation_openapi_matches_change_contract`, `test_content_reconciliation_contract_is_closed_bounded_and_safe`, `test_generated_reconciliation_models_are_strict_and_default_to_dry_run` | --- |
| content-state-reconciliation.4 | `specs/content-state-reconciliation/spec.md` — Canonical remote controls expose reconciliation | The authenticated operation API exposes a synchronous bounded `POST /api/v1/operations/reconcile-content` contract with 200/401/403/422/503 responses. | `openspec/contracts/content-workflows/openapi/v1.yaml#/paths/~1api~1v1~1operations~1reconcile-content` | D11 | `openspec/contracts/content-workflows/openapi/v1.yaml`; `tests/contract/test_canonical_workflow_contracts.py` | `test_content_reconciliation_endpoint_has_exact_response_semantics` | --- |
| content-state-reconciliation.5 | `specs/content-state-reconciliation/spec.md` — Retry is canonical and atomically budgeted | Reconciliation retry budget defaults to 3 and is bounded to 0..20. | --- | D7 | `src/config/settings.py`; `tests/config/test_settings.py` | `test_content_reconciliation_policy_defaults_are_safe_and_bounded`, `test_content_reconciliation_policy_rejects_out_of_bounds_values` | --- |
| content-state-reconciliation.6 | `specs/content-state-reconciliation/spec.md` — Stale apply is locked and protocol-gated | Staleness, page, lock, and statement limits are bounded; statement timeout cannot be below lock timeout; apply defaults off. | --- | D7, D11 | `src/config/settings.py`; `tests/config/test_settings.py` | `test_content_reconciliation_policy_defaults_are_safe_and_bounded`, `test_content_reconciliation_policy_rejects_out_of_bounds_values`, `test_content_reconciliation_statement_timeout_cannot_be_shorter_than_lock_timeout` | --- |

## Design Decision Trace

| Decision | Rationale | Implementation | Why This Approach |
|----------|-----------|----------------|-------------------|
| D7 | Bound stale detection, batch work, lock waits, statements, and retry attempts. | Validated `Settings` fields with documented safe defaults and one timeout-order validator. | Direct Pydantic constraints keep policy validation at process startup and avoid a second configuration layer. |
| D8 | Keep preview persistence-free and distinguish proposed from observed results. | Request defaults `apply` to false; report mode and item projection use closed enums. | The wire contract makes dry-run explicit without adding a reconciliation operation lifecycle. |
| D9 | Make every applied mutation externally auditable without leaking payload data. | Closed item fields include before/after state and retry counts; actions and reasons are enumerated. | A strict schema provides an allowlist that generated clients share. |
| D10 | Ensure deterministic bounded scans and safe continuation. | Request/report bounds cap pages at 100 and use positive content IDs for keyset continuation. | Contract-level limits prevent transports from requesting unbounded work. |
| D11 | Fail closed during rollout. | Apply defaults off in settings and request schema; the endpoint declares a 503 problem response. | A default-off server gate preserves existing behavior and gives rollback a single switch. |

## Review Findings Summary

| Finding ID | Package | Type | Criticality | Disposition | Resolution |
|------------|---------|------|-------------|-------------|------------|

## Coverage Summary

- **Requirements traced**: 6/6 package requirements
- **Tests mapped**: 6 requirements have at least one planned test
- **Evidence collected**: 0/6 requirements have pass/fail evidence
- **Gaps identified**: Package implementation is GREEN; validation evidence is deferred to the validation phase
- **Deferred items**: Non-contract reconciliation behavior belongs to downstream packages
