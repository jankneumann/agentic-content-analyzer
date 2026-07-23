# Spec Delta: Ingestion Filtering and Prioritization

## ADDED Requirements

### Requirement: Post-ingest filter stage invocation

The system SHALL invoke `IngestionFilterService.filter(content_id)` synchronously after any ingestion adapter persists a new `Content` row and before any summarization job is enqueued for that row. The invocation SHALL occur inside the ingestion orchestrator hook and SHALL be wrapped in an `@observe()` span named `ingestion.filter`.

#### Scenario: New RSS item is filtered before summarization

- **WHEN** the RSS adapter persists a new `Content` row with `status=PENDING` and commits the transaction
- **THEN** the orchestrator SHALL call `IngestionFilterService.filter(content_id)` before enqueueing a summarization job
- **AND** a Langfuse span named `ingestion.filter` SHALL be recorded with attributes `{source_type, decision, tier, score}`
- **AND** the summarization job SHALL NOT be enqueued if the final decision is `skip`

#### Scenario: Filter is globally disabled by config flag

- **WHEN** `filtering.enabled` is `false` in `settings/filtering.yaml` or the DB override
- **THEN** the orchestrator SHALL bypass `IngestionFilterService` entirely
- **AND** the summarization job SHALL be enqueued exactly as it is today
- **AND** no `filter_*` columns on `Content` SHALL be written

#### Scenario: Filter is per-source disabled via sources.d override

- **WHEN** the source adapter's `sources.d/*.yaml` entry sets `filter.enabled: false` in its `defaults` block
- **THEN** items from that source SHALL bypass the filter service
- **AND** their `Content` rows SHALL have `filter_decision = NULL` and `filter_score = NULL`

### Requirement: Three-tier filter evaluation

`IngestionFilterService` SHALL evaluate an ingested item through up to three tiers in order — heuristic, embedding, and LLM — short-circuiting as soon as a deterministic decision is reached.

#### Scenario: Tier-1 heuristic short-circuit on must-exclude keyword

- **GIVEN** a persona `filter_profile.must_exclude` contains the keyword `press release`
- **WHEN** an item with title `Acme Inc. Press Release: Q4 Results` is evaluated
- **THEN** Tier 1 SHALL return `{decision: skip, score: 0.0, reason: "heuristic.must_exclude:press release", tier: "heuristic"}`
- **AND** tiers 2 and 3 SHALL NOT run
- **AND** the `Content.status` SHALL be updated to `FILTERED_OUT`

#### Scenario: Tier-1 heuristic short-circuit on must-include keyword

- **GIVEN** a persona `filter_profile.must_include` contains the keyword `retrieval-augmented generation`
- **WHEN** an item whose markdown_content contains `retrieval-augmented generation` is evaluated
- **THEN** Tier 1 SHALL return `{decision: keep, score: 1.0, reason: "heuristic.must_include:retrieval-augmented generation", tier: "heuristic"}`
- **AND** tiers 2 and 3 SHALL NOT run
- **AND** `Content.priority_bucket` SHALL be set to `high`

#### Scenario: Tier-2 embedding score above high threshold

- **GIVEN** `filter_profile.borderline_band = {low: 0.45, high: 0.65}`
- **AND** Tier 1 did not short-circuit
- **WHEN** the cosine similarity between the item's title+lead embedding and the persona profile embedding is `0.72`
- **THEN** Tier 2 SHALL return `{decision: keep, score: 0.72, reason: "embedding.similarity:0.72", tier: "embedding"}`
- **AND** Tier 3 SHALL NOT run
- **AND** `Content.priority_bucket` SHALL be set to `high` (score ≥ high threshold) or `normal` otherwise

#### Scenario: Tier-2 embedding score below low threshold

- **GIVEN** `filter_profile.borderline_band = {low: 0.45, high: 0.65}`
- **WHEN** the cosine similarity is `0.31`
- **THEN** Tier 2 SHALL return `{decision: skip, score: 0.31, reason: "embedding.similarity:0.31<0.45", tier: "embedding"}`
- **AND** Tier 3 SHALL NOT run
- **AND** `Content.status` SHALL be updated to `FILTERED_OUT`

#### Scenario: Tier-2 borderline triggers Tier-3 LLM

- **GIVEN** `filter_profile.borderline_band = {low: 0.45, high: 0.65}`
- **WHEN** the cosine similarity is `0.55`
- **THEN** Tier 3 SHALL be invoked with the item and the persona interest description
- **AND** the LLM response SHALL be parsed as `{decision: keep|skip, score: float in [0,1], reason: str}`
- **AND** the final `filter_tier` value stored on `Content` SHALL be `llm`

#### Scenario: Tier-3 is disabled for the source

- **GIVEN** the source override sets `filter.override_tier_3: false`
- **WHEN** the item reaches the borderline band in Tier 2
- **THEN** the service SHALL treat the item as a `keep` with `priority_bucket = low` instead of invoking the LLM
- **AND** `filter_tier` SHALL be `embedding`

### Requirement: Filter decision persisted on Content

The `Content` model SHALL record the outcome of every filter evaluation.

#### Scenario: Kept item persistence

- **WHEN** the filter returns `decision=keep` with `score=0.72` via tier `embedding`
- **THEN** the row SHALL have `filter_decision='keep'`, `filter_score=0.72`, `filter_tier='embedding'`, `filter_reason='embedding.similarity:0.72'`, `priority_bucket='high'`, `filtered_at=<now>`
- **AND** `status` SHALL remain unchanged (still `PENDING` or `PARSED`)

#### Scenario: Skipped item persistence

- **WHEN** the filter returns `decision=skip`
- **THEN** the row SHALL have `filter_decision='skip'`, `filter_tier=<tier>`, `filter_reason=<reason>`, `priority_bucket=NULL`, `filtered_at=<now>`
- **AND** `status` SHALL be updated to `FILTERED_OUT`
- **AND** the row SHALL NOT be physically deleted

### Requirement: Persona-based filter profile

Each persona in `settings/personas/*.yaml` SHALL be able to declare a `filter_profile` block that drives filter behavior.

#### Scenario: Persona profile with interest description is loaded

- **GIVEN** a persona YAML contains `filter_profile.interest_description: "Engineering leadership, AI agents, production ML"`
- **WHEN** the persona is loaded at startup or reloaded after a file change
- **THEN** its interest description SHALL be encoded via the configured `EmbeddingProvider` with `is_query=False`
- **AND** the resulting vector SHALL be stored in `persona_filter_profiles` keyed by `(persona_id, embedding_provider, embedding_model)`
- **AND** subsequent filter calls for that persona SHALL reuse the stored vector without re-encoding

#### Scenario: Interest description changes and profile is recomputed

- **GIVEN** a persona's `filter_profile.interest_description` changes
- **WHEN** the persona file is reloaded
- **THEN** the stored profile vector for that persona SHALL be invalidated and recomputed
- **AND** `persona_filter_profiles.updated_at` SHALL be advanced to the current time

#### Scenario: Persona without filter_profile uses global defaults

- **GIVEN** a persona YAML does NOT declare `filter_profile`
- **WHEN** the filter runs for that persona
- **THEN** it SHALL fall back to `settings/filtering.yaml` defaults
- **AND** it SHALL use an embedding of the persona's `description` field as the interest vector

### Requirement: Dry-run mode

`IngestionFilterService` SHALL support a dry-run mode in which decisions are recorded but status transitions are suppressed.

#### Scenario: CLI dry-run flag

- **WHEN** an operator runs `aca ingest rss --filter-dry-run`
- **THEN** every ingested item SHALL be filtered normally and have `filter_decision`, `filter_score`, `filter_tier`, `filter_reason` populated
- **AND** `Content.status` SHALL NOT be set to `FILTERED_OUT` even for `skip` decisions
- **AND** the summarization job SHALL still be enqueued for every kept or would-be-skipped item

### Requirement: Explain and rerun operations

Operators SHALL be able to inspect and re-evaluate filter decisions.

#### Scenario: Explain a single content item

- **WHEN** an operator runs `aca filter explain <content-id>`
- **THEN** the CLI SHALL print the stored `filter_decision`, `filter_score`, `filter_tier`, `filter_reason`, and `priority_bucket`
- **AND** it SHALL print the per-tier intermediate values that were recorded on the Langfuse span

#### Scenario: Rerun filter over kept items after profile change

- **WHEN** an operator runs `aca filter rerun --persona ai-ml-technology --since 2026-04-01`
- **THEN** every `Content` row for that persona ingested after the date SHALL be re-evaluated
- **AND** rows whose decision flips SHALL have their `status`, `filter_*`, and `priority_bucket` fields updated accordingly
- **AND** rows already `COMPLETED` SHALL NOT have their `status` changed, but their `priority_bucket` MAY be updated

### Requirement: Content query and API expose filter state

Existing content list endpoints and CLI listings SHALL expose the new fields so operators can slice by filter decision and priority.

#### Scenario: API filter query parameters

- **WHEN** a client sends `GET /api/v1/contents?filter_decision=skip&priority_bucket=low`
- **THEN** the response SHALL include only rows matching both filters
- **AND** the response body for each row SHALL include `filter_decision`, `filter_score`, `filter_tier`, `priority_bucket`

### Requirement: Feedback event emission

Review actions on a digest or content row SHALL emit a structured feedback event that pairs the reviewer's decision with the original filter score.

#### Scenario: Reviewer approves a low-score item

- **GIVEN** a `Content` row has `filter_decision=keep`, `filter_score=0.48`, `priority_bucket=low`
- **WHEN** a reviewer approves that item in the digest review UI
- **THEN** an event `filter.review.feedback` SHALL be emitted with payload `{content_id, persona_id, original_score, original_decision, reviewer_decision: "approve", reviewed_at}`
- **AND** the event SHALL be logged but SHALL NOT modify any existing thresholds in v1
