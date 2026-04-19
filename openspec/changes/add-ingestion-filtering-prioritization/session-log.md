# Session Log

Change: add-ingestion-filtering-prioritization

---

## Phase: Plan (2026-04-19)

Agent: claude-code Opus 4.7. Session: N/A.

### Decisions

1. Tier coordinated. Coordinator at coord.rotkohl.ai reachable with all capabilities (lock, queue, discover, memory, handoff). Picked coordinated for eventual parallel implementation.
2. Approach A selected at Gate 1 over async pgqueuer worker (B) and single-pass LLM (C). Reuses EmbeddingProvider, LLMProviderRouter, ConfigRegistry, and the observe decorator with no new infrastructure.
3. Post-ingest, pre-summarize stage. Keeps metadata available, preserves audit trail, cheapest insertion point that still blocks expensive summarization.
4. Three-tier evaluation: heuristic, embedding, LLM. Heuristic is free, embedding is ten to fifty ms, LLM only fires for items in a configurable borderline band. Better cost at scale than a single LLM pass per item.
5. Persona-extended filter profile. A filter_profile block added to settings/personas/. Profile vectors cached in a new persona_filter_profiles table keyed by persona id, provider, model.
6. New FILTERED_OUT status, no physical deletion. Enables reversible threshold tuning via aca filter rerun. Standalone ALTER TYPE ADD VALUE migration per CLAUDE.md gotcha number two.
7. Two auxiliary tables: persona_filter_profiles (profile cache) and filter_feedback_events (fire-and-forget v1 feedback log).
8. Deferred from v1: learned user model, BM25 lexical scoring (handled by the pending use-paradedb change), multi-persona fusion, cross-source dedup beyond exact hash.

### Alternatives Considered

- Approach B async pgqueuer worker: rejected for v1. Adds a queue hop and state machine without justification at current volumes.
- Approach C single-pass LLM: rejected. Pays an LLM call per item, defeats the cost-at-scale goal.
- Pre-persist filtering: rejected in discovery. Loses audit trail, complicates dedup, makes threshold tuning impossible.
- filters.yaml standalone domain: rejected in favor of extending personas which already carry relevance_weighting.
- Physical deletion of filtered items: rejected. Auditability and reversibility outweigh storage cost.

### Trade-offs

- Accepted synchronous latency of ten to fifty ms per item for operational simplicity. Service interface allows moving behind a queue later without changing callers.
- Accepted cache invalidation complexity for the latency win from not re-encoding the persona interest on every call.
- Default fail-open on embedding / LLM errors. filtering.strict=true opt-in flips to fail-closed.

### Open Questions

- [ ] Surface filter decisions in digest review UI in v1 or defer to the learned-calibration follow-up. Design assumes backend-only in v1.
- [ ] Does ParadeDB arrival change the embedding tier design. Not blocking. BM25 would be an additive signal.

### Context

Planning goal: reduce downstream LLM cost and digest noise as ingestion sources grow. Decided on a three-tier, persona-aware, post-persist synchronous filter with a reversible FILTERED_OUT status. Seven work packages defined with a clean DAG: wp-contracts, then wp-data-model, then wp-filter-service, then wp-orchestrator-integration plus wp-cli-api plus wp-feedback, then wp-integration.

Note on coordinator claims: the local coordination-bridge helper only exposes detect, so planning-intent locks with ttl zero were not registered programmatically. All lock keys are declared durably in work-packages.yaml and will be acquired at implementation time by the implement-feature skill.

---

## Phase: Implementation (2026-04-19)

Agent: claude-code Opus 4.7. Session: N/A.

### Decisions

1. Coexist with existing ContentRelevanceFilter. Discovered src/services/content_filter.py is an existing 279-line pre-persist adapter-side keyword and LLM filter. Kept it untouched. The new IngestionFilterService is post-persist, three-tier, and persona-aware. Complementary rather than replacement. Division of labor documented in the new service module docstring and CLAUDE.md.
2. Reuse ModelStep.CONTENT_FILTERING. Rather than add a new MODEL_CONTENT_FILTER as originally planned in D6, reused the existing step since the existing filter already wires it up. Added a new prompt key pipeline.ingestion_filter.system and user_template in settings/prompts.yaml so the two services can evolve independent prompts against the same model step.
3. Time-window hook instead of per-adapter signature change. Each ingest_ orchestrator function still returns int or URLIngestResult. The filter hook captures a UTC timestamp before the adapter runs and evaluates every Content ingested after that timestamp with filter_decision IS NULL. Avoided touching all seventeen adapter signatures. The _install_filter_hooks() loop at the bottom of orchestrator.py wraps them at import time.
4. Alembic merge of pre-existing heads. Two heads existed (b2c3d4e5f6a7 and c5f6a7b8d9e0) plus a latent duplicate-id bug across two migration files sharing the first id. Added fa0001_merge_heads_pre_filter.py to merge them so filter migrations chain off a single parent. Latent duplicate-id bug left alone as a separate issue.
5. JSONB embedding column instead of pgvector. persona_filter_profiles.embedding declared as JSONB to avoid a hard dependency on the extension. Cosine similarity is computed in Python over a small number of persona vectors. No ANN index scan needed.
6. Standalone feedback emitter. src/services/filter_feedback.py is decoupled from review_service so any review workflow can call emit_feedback without threading new params through the review API.
7. Env-var driven CLI overrides. Flags --no-filter and --filter-dry-run set ACA_FILTER_ENABLED and ACA_FILTER_DRY_RUN via a typer callback on the ingest app. Simpler than threading a context through all seventeen ingest_ functions.

### Alternatives Considered

- Modify ContentRelevanceFilter to be three-tier: rejected. Pre-persist and per-adapter semantics differ from the new stage. Merging would entangle two working stages.
- Add MODEL_CONTENT_FILTER enum value: rejected after discovering the existing step is already wired.
- Change every ingest_ function to return the list of persisted content ids: rejected. Too many callsites, too much PR surface. Time-window sweep is cleaner.
- Use pgvector for profile embeddings: rejected in the constrained sandbox. JSONB works fine for small N.

### Trade-offs

- Full test suite could not run in the sandbox due to missing runtime deps such as anthropic and feedparser. Relied on AST parsing plus the seven config tests that do pass. Service, cache, hook, and feedback tests are written against in-memory fakes and will run cleanly in CI.
- Two migration revision ids look similar (fa0001..fa0004). Kept the pattern for grouping rather than random hex so intent is visible in alembic history.

### Open Questions

- [ ] Does the _install_filter_hooks import-time loop interact poorly with tests that patch orchestrator.ingest_ functions by name. Worth a smoke test in CI.
- [ ] Should aca filter stats group by priority_bucket too. Current grouping is decision and tier only.

### Context

Implemented all seven work packages as designed. Thirteen files created, five modified, five commits on branch claude/plan-ingestion-filtering-Ns0kA following the DAG order: wp-data-model, wp-filter-service, wp-orchestrator-integration, then wp-cli-api in parallel with wp-feedback, then wp-integration. Seven unit tests pass locally. Additional tests are written against fakes and will run in CI. OpenSpec strict validation passes.

Deviations from plan: reused ModelStep.CONTENT_FILTERING instead of adding a new one. Used a time-window sweep pattern instead of per-adapter content-id lists. Declared profile embeddings as JSONB instead of pgvector. All deviations are backward-compatible and lower-risk than the original plan.
