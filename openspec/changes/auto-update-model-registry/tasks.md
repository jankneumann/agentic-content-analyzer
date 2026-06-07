# Tasks: Auto-update model registry

**Change ID**: `auto-update-model-registry`

## Parallelizability Notes

Phase 1 (discovery) and the writeback parts of Phase 2 are independent. The gate
(Phase 3) depends on discovery + enrichment. Scheduling/CLI (Phase 4) depends on
the services. Tests precede their implementations (TDD). Max parallel width: ~2.

---

## Phase 1: Catalog discovery

- [x] 1.1 Write tests for catalog discovery (candidate detection, missing-key skip, known-model exclusion)
  **Spec scenarios**: New model discovered, Discovery degrades without a key, Known models not re-reported
  **Files**: `tests/services/test_model_catalog_discovery.py` (new)
  **Dependencies**: none

- [x] 1.2 Implement `model_catalog_discovery.py` (live provider list-models + registry diff)
  **Spec scenarios**: New model discovered, Discovery degrades without a key, Known models not re-reported
  **Design decisions**: D2
  **Files**: `src/services/model_catalog_discovery.py` (new)
  **Dependencies**: 1.1

- [x] 1.3 Reuse pricing extractor to enrich candidates with cost + capability flags
  **Spec scenarios**: Candidate enriched with pricing and capabilities
  **Design decisions**: D2
  **Files**: `src/services/model_catalog_discovery.py`, `src/services/model_pricing_extractor.py` (modified)
  **Dependencies**: 1.2

- [x] Checkpoint: run tests, review diff, verify scope

## Phase 2: Risk-gated writeback

- [x] 2.1 Write tests for writeback (dry-run vs apply, version bump, default-swap blocked, YAML round-trip)
  **Spec scenarios**: Pricing diff auto-applies, Default swap requires approval, Dry-run by default
  **Files**: `tests/services/test_registry_writeback.py` (new)
  **Dependencies**: none

- [x] 2.2 Implement registry writeback in `model_registry_service` (apply diffs/candidates, version + audit, ConfigRegistry reload)
  **Spec scenarios**: Pricing diff auto-applies, Dry-run by default
  **Design decisions**: D5, D6
  **Files**: `src/services/model_registry_service.py` (modified)
  **Dependencies**: 2.1

- [x] 2.3 Add risk tiers to `approval.yaml` and enforce on writeback
  **Spec scenarios**: Default swap requires approval
  **Design decisions**: D3
  **Files**: `settings/approval.yaml`, `src/services/model_registry_service.py` (modified)
  **Dependencies**: 2.2

- [x] Checkpoint: run tests, review diff, verify scope

## Phase 3: Validate-before-promote gate

- [x] 3.1 Write tests for the promotion gate (pass/fail vs synthetic consensus, cost budget)
  **Spec scenarios**: Candidate passes the gate, Candidate fails the gate
  **Files**: `tests/services/test_model_promotion_gate.py` (new)
  **Dependencies**: none

- [x] 3.2 Implement the promotion gate over the eval harness (dataset build + consensus + recommendation)
  **Spec scenarios**: Candidate passes the gate, Candidate fails the gate
  **Design decisions**: D4
  **Files**: `src/services/model_registry_service.py` or `src/services/model_promotion_service.py` (new)
  **Dependencies**: 3.1, 1.3

- [x] Checkpoint: run tests, review diff, verify scope

## Phase 4: Scheduling & CLI

- [x] 4.1 Write tests for scheduled refresh (cron match enqueues once/minute)
  **Spec scenarios**: Scheduled job enqueues a refresh
  **Files**: `tests/agents/test_schedule_refresh.py` (new)
  **Dependencies**: none

- [x] 4.2 Add `refresh_models` schedule entry (enqueues `actions:[refresh_models]`)
  **Spec scenarios**: Scheduled job enqueues a refresh
  **Design decisions**: D1
  **Files**: `settings/schedule.yaml`, `tests/agents/scheduler/test_refresh_models_schedule.py`
  **Note**: Execution follows the existing agent-driven maintenance convention
  (like `knowledge_maintenance`'s `prune_stale` etc., the action is carried on the
  enqueued task for the conductor — there is no separate concrete action-runner in
  the codebase to extend). Entry is `enabled: false` by default (Rule 4).
  **Dependencies**: 4.1, 2.2, 3.2

- [x] 4.3 Add `aca models discover|refresh|propose-default` CLI commands
  **Spec scenarios**: New model discovered, Pricing diff auto-applies, Candidate passes the gate
  **Files**: `src/cli/` (new model_commands.py), CLI registration
  **Dependencies**: 1.2, 2.2, 3.2

- [x] 4.4 Docs: MODEL_CONFIGURATION.md (freshness flow), CLAUDE.md command table
  **Spec scenarios**: (documentation)
  **Files**: `docs/MODEL_CONFIGURATION.md`, `CLAUDE.md` (modified)
  **Dependencies**: 4.3
