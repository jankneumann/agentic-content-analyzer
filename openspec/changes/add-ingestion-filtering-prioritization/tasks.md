# Tasks: Ingestion Filtering and Prioritization

Tasks are ordered phase-by-phase. Within each phase, **test tasks come first** and implementation tasks depend on them (TDD: RED → GREEN).

## Phase 1 — Contracts and data model

- [ ] 1.1 Write tests for migration: new columns present with correct types, `FILTERED_OUT` enum value exists, indexes created
  **Spec scenarios**: ingestion-filtering.persistence.kept, ingestion-filtering.persistence.skipped
  **Contracts**: contracts/db/schema.sql
  **Design decisions**: D4 (two-step enum migration), D9 (keep rows, no delete)
  **Dependencies**: None

- [ ] 1.2 Write Alembic migration A (standalone): `ALTER TYPE content_status ADD VALUE 'FILTERED_OUT'`
  **Dependencies**: 1.1

- [ ] 1.3 Write Alembic migration B (transactional): add columns `filter_score`, `filter_decision`, `filter_tier`, `filter_reason`, `priority_bucket`, `filtered_at` to `contents`; add indexes `ix_contents_status_filter_score`, `ix_contents_filter_decision_ingested`
  **Contracts**: contracts/db/schema.sql
  **Dependencies**: 1.1

- [ ] 1.4 Write Alembic migration C: create tables `persona_filter_profiles` and `filter_feedback_events`
  **Contracts**: contracts/db/schema.sql
  **Dependencies**: 1.1

- [ ] 1.5 Extend `ContentStatus` StrEnum in `src/models/content.py` with `FILTERED_OUT`; add the new columns to the `Content` ORM model
  **Design decisions**: D4
  **Dependencies**: 1.2, 1.3

- [ ] 1.6 Create `src/models/persona_filter_profile.py` and `src/models/filter_feedback_event.py` ORM models matching migration C
  **Dependencies**: 1.4

## Phase 2 — Service skeleton and tier 1 (heuristic)

- [ ] 2.1 Write unit tests for `FilterDecision` dataclass and `FilterTier` enum shape
  **Spec scenarios**: ingestion-filtering.persistence.kept, ingestion-filtering.persistence.skipped
  **Dependencies**: 1.5

- [ ] 2.2 Write unit tests for tier 1 heuristic: must_include / must_exclude / min_word_count / language gate short-circuits
  **Spec scenarios**: ingestion-filtering.tier1.must_include, ingestion-filtering.tier1.must_exclude
  **Design decisions**: D2 (strict tier order)
  **Dependencies**: 2.1

- [ ] 2.3 Create `src/services/ingestion_filter.py` with `IngestionFilterService`, `FilterDecision`, `FilterTier`, and `_run_heuristic_tier()` implementation
  **Dependencies**: 2.2

- [ ] 2.4 Wire `ConfigRegistry` to load `settings/filtering.yaml` as a new domain; add `settings/filtering.yaml` with shipped defaults
  **Design decisions**: D5 (three-layer override)
  **Dependencies**: 2.3

## Phase 3 — Persona profile encoding and tier 2 (embedding)

- [ ] 3.1 Write unit tests for `PersonaProfileCache`: hash-based invalidation, re-encode on description change, lookup by `(persona_id, provider, model)`
  **Spec scenarios**: ingestion-filtering.persona.loaded, ingestion-filtering.persona.reloaded
  **Design decisions**: D3 (cache profile vectors in Postgres)
  **Dependencies**: 1.6

- [ ] 3.2 Create `src/services/persona_profile_cache.py` implementing the cache against `persona_filter_profiles`
  **Dependencies**: 3.1

- [ ] 3.3 Extend persona YAML schema loader to accept `filter_profile` block; fall back to `description` when missing
  **Spec scenarios**: ingestion-filtering.persona.fallback
  **Dependencies**: 3.2

- [ ] 3.4 Write unit tests for tier 2 embedding: score above high → keep+high, below low → skip, in band → returns borderline sentinel for tier 3
  **Spec scenarios**: ingestion-filtering.tier2.above_high, ingestion-filtering.tier2.below_low, ingestion-filtering.tier2.borderline
  **Dependencies**: 3.2

- [ ] 3.5 Implement `_run_embedding_tier()` in `IngestionFilterService` using `EmbeddingProvider` and `PersonaProfileCache`
  **Dependencies**: 3.4

- [ ] 3.6 Write tests for fail-open behavior when embedding provider raises
  **Spec scenarios**: (design D2 failure mode — covered by unit test reference to "embedding.error" in reason)
  **Design decisions**: D2, failure modes section of design.md
  **Dependencies**: 3.5

## Phase 4 — Tier 3 LLM + prompt wiring

- [ ] 4.1 Write unit tests for tier 3 LLM: routes through `LLMProviderRouter`, parses structured response, handles malformed responses defensively
  **Spec scenarios**: ingestion-filtering.tier2.borderline (triggers tier 3), ingestion-filtering.tier3.disabled
  **Design decisions**: D6 (route via LLMProviderRouter), failure modes
  **Dependencies**: 3.5

- [ ] 4.2 Add `pipeline.filter.system` and `pipeline.filter.user_template` entries to `settings/prompts.yaml`
  **Dependencies**: None

- [ ] 4.3 Add `MODEL_CONTENT_FILTER` to model registry and default to `claude-haiku-4-5`; update `settings/models.yaml`
  **Design decisions**: D6
  **Dependencies**: None

- [ ] 4.4 Implement `_run_llm_tier()` in `IngestionFilterService` — prompt construction, provider routing, response parsing
  **Dependencies**: 4.1, 4.2, 4.3

- [ ] 4.5 Write tests for source override `filter.override_tier_3: false` — service must never call the LLM for that source even if band matches
  **Spec scenarios**: ingestion-filtering.tier3.disabled
  **Dependencies**: 4.4

## Phase 5 — Orchestrator integration

- [ ] 5.1 Write tests for orchestrator hook: `filter()` is called after persist, before summarization enqueue, exactly once per new `Content`
  **Spec scenarios**: ingestion-filtering.hook.invoked
  **Contracts**: contracts/events/filter.decision.schema.json
  **Design decisions**: D1 (synchronous hook), D7 (adapter-agnostic)
  **Dependencies**: 4.4

- [ ] 5.2 Write tests for `filtering.enabled=false` bypass — filter service not called, summarization enqueued as before, no `filter_*` columns written
  **Spec scenarios**: ingestion-filtering.hook.disabled
  **Dependencies**: 5.1

- [ ] 5.3 Write tests for per-source bypass via `sources.d/*.yaml` `filter.enabled: false`
  **Spec scenarios**: ingestion-filtering.hook.source_disabled
  **Dependencies**: 5.1

- [ ] 5.4 Modify `src/ingestion/orchestrator.py` to call `IngestionFilterService.filter(content_id)` in the post-persist hook; wrap with `@observe(name="ingestion.filter")`
  **Dependencies**: 5.1, 5.2, 5.3

- [ ] 5.5 Update `status=FILTERED_OUT` logic — summarization enqueue path must skip those rows
  **Spec scenarios**: ingestion-filtering.hook.invoked
  **Dependencies**: 5.4

## Phase 6 — CLI, API, dry-run

- [ ] 6.1 Write tests for `aca ingest <source> --filter-dry-run` and `--no-filter` flags
  **Spec scenarios**: ingestion-filtering.dry_run
  **Dependencies**: 5.4

- [ ] 6.2 Implement `--filter-dry-run` and `--no-filter` in `src/cli/ingest_commands.py`
  **Dependencies**: 6.1

- [ ] 6.3 Write tests for new CLI group `aca filter`: `explain`, `rerun`, `stats`
  **Spec scenarios**: ingestion-filtering.explain, ingestion-filtering.rerun
  **Dependencies**: 5.4

- [ ] 6.4 Create `src/cli/filter_commands.py` implementing the `aca filter` group
  **Dependencies**: 6.3

- [ ] 6.5 Write tests for `GET /api/v1/contents?filter_decision=...&priority_bucket=...`
  **Spec scenarios**: ingestion-filtering.api.query
  **Contracts**: contracts/openapi/v1.yaml
  **Dependencies**: 1.5

- [ ] 6.6 Extend contents query endpoint and serializer in `src/api/contents.py` with the new filter fields and query params
  **Dependencies**: 6.5

## Phase 7 — Feedback events

- [ ] 7.1 Write tests for `filter.review.feedback` event emission when a reviewer approves/rejects in the digest review UI; verify `filter_feedback_events` row is written
  **Spec scenarios**: ingestion-filtering.feedback.emitted
  **Contracts**: contracts/events/filter.review.feedback.schema.json
  **Design decisions**: D8 (fire-and-forget in v1)
  **Dependencies**: 1.6

- [ ] 7.2 Hook the review action handler to emit the event and persist the row
  **Dependencies**: 7.1

## Phase 8 — Regression and rollout safety

- [ ] 8.1 Add regression test: daily pipeline end-to-end with `filtering.enabled=false` produces identical output to pre-change (byte-for-byte on summary ids/counts)
  **Dependencies**: 5.4

- [ ] 8.2 Add regression test: daily pipeline with `filtering.enabled=true` drops a seeded noise item and keeps a seeded signal item
  **Spec scenarios**: ingestion-filtering.tier1.must_exclude, ingestion-filtering.tier2.above_high
  **Dependencies**: 5.4, 5.5

- [ ] 8.3 Update docs: `docs/ARCHITECTURE.md` (new stage), `docs/MODEL_CONFIGURATION.md` (`MODEL_CONTENT_FILTER`), `CLAUDE.md` quick-ref table entry
  **Dependencies**: 5.4

- [ ] 8.4 Run `openspec validate add-ingestion-filtering-prioritization --strict`; fix any validation errors
  **Dependencies**: all prior
