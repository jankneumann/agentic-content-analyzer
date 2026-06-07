# Design: Auto-update model registry

## Reuse map (what already exists)

| Capability | Existing asset | Action |
|---|---|---|
| Pricing/spec extraction + diff/new-model detection | `src/services/model_pricing_extractor.py` (`ExtractedModel`, `PricingReport`) | Reuse for enrichment |
| Refresh orchestration (dry-run) | `src/services/model_registry_service.py` `refresh_pricing()` | Extend with writeback + candidates |
| Model-vs-model scoring | `aca evaluate` (`create-dataset`/`run`/`calibrate`/`compare`), `evaluation_*` tables | Reuse as the promotion gate |
| Scheduling | `AgentScheduler` + `settings/schedule.yaml` | Add `refresh_models` entry + task |
| Runtime override + precedence | `settings_overrides`, `SettingsService`, `ModelConfig.get_model_for_step` (env > DB > YAML) | Reuse for staged defaults |
| Config reload | `ConfigRegistry.reload("models")` | Call after writeback |

## Flow (D1)

```
schedule.yaml: refresh_models (cron)
  └─ AgentScheduler.tick() → enqueue maintenance task
       └─ discover()        # NEW: provider list-models APIs
       └─ enrich()          # reuse model_pricing_extractor
       └─ for pricing/spec diffs on EXISTING models:
              apply (low risk, version-bumped, audited)        # NEW writeback
       └─ for NEW models / proposed step-default swaps:
              gate() via aca evaluate (incumbent vs candidate) # reuse harness
              if pass → record pending approval (approval.yaml)
              if approved → writeback + ConfigRegistry.reload
```

## Decisions

- **D1 — Strangler over rewrite**: extend existing services; do not duplicate
  extraction or scoring. (Approach A.)
- **D2 — Live APIs + scraping**: `model_catalog_discovery.py` calls provider
  list-models for *existence/ids*; `model_pricing_extractor` supplies cost +
  capabilities. APIs catch models before they appear on pricing pages; scraping
  fills metadata the API doesn't return.
- **D3 — Risk tiers (auto pricing, gated defaults)**: in `approval.yaml` —
  pricing-diff = low (auto-apply with `--apply`/scheduled), registry-add =
  medium, step-default swap = high (human approval). Defaults additionally
  require passing the eval gate.
- **D4 — Gate reuses eval consensus**: parity target + cost budget are config;
  the promotion recommendation is derived from `evaluation_consensus`
  agreement/preference, mirroring `calibrate`.
- **D5 — Staged defaults via settings_overrides**: an approved default swap is
  written as a `model.<step>` override (DB) first (instant, reversible), then
  optionally promoted into `models.yaml` `default_models`. This leverages the
  existing env>DB>YAML precedence so rollback is a row delete.
- **D6 — Audit + versioning**: every writeback bumps the override `version` and
  emits an audit record; `models.yaml` edits are mechanical and minimal-diff.

## Risks / open questions

1. **Provider SDK list-models surfaces differ** — confirm method names/shapes per
   installed SDK version (source-driven-development; sandbox cannot import them).
2. **Eval cost** — running the gate consumes judge tokens; restrict to candidates
   explicitly proposed for a step, not every discovered model.
3. **YAML writeback fidelity** — must preserve comments/ordering; prefer a
   structured loader that round-trips (e.g. ruamel) or targeted edits.
4. **Capability inference** — `supports_video/audio` may not be reliably scrapable;
   default unknown → conservative (treat as unsupported until confirmed).

## Test plan

- `test_model_catalog_discovery.py`: candidate detection, missing-key skip,
  known-model exclusion (mock provider clients).
- `test_model_promotion_gate.py`: pass/fail against synthetic consensus; cost
  budget enforcement.
- `test_registry_writeback.py`: dry-run vs `--apply`; version bump; default-swap
  blocked without approval; round-trip preserves YAML.
- `test_schedule_refresh.py`: cron match enqueues once per minute.
