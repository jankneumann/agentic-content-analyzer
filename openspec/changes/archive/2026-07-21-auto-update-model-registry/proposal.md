# Change: Auto-update model registry (catalog discovery + validate-before-promote)

**Change ID**: `auto-update-model-registry`
**Status**: Draft
**Created**: 2026-06-07

## Why

The model registry (`settings/models.yaml`) is hand-maintained. As providers ship
new models (e.g. the requested `gemini-3.1-flash-lite`, which is **not in the
registry today**), the pipeline keeps using older, more expensive, or less capable
models until someone manually edits YAML. We want the system to *regularly* adopt
the most appropriate models as they are released — safely.

Key finding from the codebase: **~70% of the machinery already exists.**
- `src/services/model_pricing_extractor.py` scrapes provider pricing pages and
  already detects `new_models` and field-level `diffs` (`PricingReport`).
- `src/services/model_registry_service.py` `refresh_pricing(dry_run=True)`
  orchestrates extraction into a `PricingRefreshReport`.
- `aca evaluate` (`src/cli/evaluate_commands.py`) provides `create-dataset` /
  `run` (LLM-judge consensus) / `calibrate` / `compare` — model-vs-model scoring
  on a pipeline step already exists.
- `AgentScheduler` + `settings/schedule.yaml` provide cron scheduling.
- `settings_overrides` table + `SettingsService` provide a DB override layer for
  `model.<step>` with versioning.

The **three gaps** this change closes:
1. **No live catalog enumeration** — only page scraping; provider `list-models`
   APIs are never called, so genuinely new model IDs can be missed.
2. **No writeback** — `refresh_pricing` is dry-run only; nothing applies diffs to
   `models.yaml` / `provider_model_configs`.
3. **No validate-before-promote gate** — nothing wires the eval harness to gate a
   candidate model becoming a step default.

## What Changes

### New components
1. **`src/services/model_catalog_discovery.py`** — enumerate live provider
   catalogs (`google-genai` `client.models.list()`, Anthropic
   `client.models.list()`, OpenAI `client.models.list()`); diff against the
   registry to produce a candidate set of new model IDs.
2. **Promotion gate** in `model_registry_service.py` (or a new
   `model_promotion_service.py`) — for a candidate proposed as a step default,
   auto-build an `evaluation_dataset` (incumbent vs candidate on that step), run
   `evaluate run` with N-judge consensus, compute quality parity + cost delta,
   and emit a promotion recommendation.
3. **Writeback** — implement `refresh_pricing(dry_run=False)` (and a
   `apply_candidates`) to patch `models.yaml` + `provider_model_configs`,
   version-bumped and audited; reload via `ConfigRegistry`.
4. **Scheduled task** — a `refresh_models` entry in `settings/schedule.yaml` +
   a maintenance task handler that runs discover → enrich → (gate) → apply/propose.
5. **CLI** — `aca models discover` (list candidates), `aca models refresh`
   (pricing/spec diffs, `--apply`), `aca models propose-default --step <step>
   --candidate <model>` (run the gate).

### Modified components
1. **`src/services/model_pricing_extractor.py`** — reuse for capability/cost
   enrichment of discovered candidates.
2. **`settings/approval.yaml`** — risk tiers: pricing-diff = low (auto-apply);
   new-model registry add = medium; step-default swap = high (human approval).
3. **`settings/schedule.yaml`** — add `refresh_models` cron entry.

## Approaches Considered

### A. Wire-existing strangler (Recommended)
Extend the existing extractor/service/eval/scheduler rather than build new.
- **Pros**: reuses proven code; smallest surface; eval harness supplies the
  quality bar for free.
- **Cons**: couples to current `PricingRefreshReport` shapes.
- **Effort**: M

### B. Standalone "model-ops" subsystem
New service + new tables + new scheduler path, independent of pricing extractor.
- **Pros**: clean separation.
- **Cons**: duplicates extraction + scoring; high effort; two code paths to
  maintain. **Rejected.**
- **Effort**: L

### C. Pricing-only autoupdate (no promotion gate)
Just apply pricing/spec diffs; never touch step defaults automatically.
- **Pros**: trivial; lowest risk.
- **Cons**: doesn't actually "adopt the most appropriate models" — the core ask.
- **Effort**: S

## Selected Approach (Gate 1)

Approach **A**, with the **auto pricing / gated defaults** policy: pricing & spec
diffs to existing models auto-apply (low risk); registry-adds and step-default
swaps require approval via `approval.yaml`; defaults only swap after the eval gate
passes parity + cost checks. Catalog source = **live provider APIs + page
scraping**.

## Impact

- **Safety**: defaults never change silently; all writebacks are versioned + audited.
- **Cost**: adopts cheaper/better models faster; eval gate prevents quality regressions.
- **Dependencies**: provider SDK `list-models` calls require provider API keys
  (already present for the providers in use); discovery degrades gracefully when a
  key is absent.
- **No DB schema change** required beyond reusing `settings_overrides` and the
  existing `evaluation_*` tables.
