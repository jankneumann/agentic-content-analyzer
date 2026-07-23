# Add Ingestion-Time Filtering and Prioritization

## Why

The number of ingestion sources keeps growing — Gmail, RSS, Substack, YouTube, podcasts, X/Twitter, Perplexity, Scholar, arXiv, HuggingFace Papers, blog scrapers, file uploads, and direct URLs. Today every fetched item flows directly into `Content` with `status=PENDING` and is then handed to the (expensive) summarization, theme analysis, and digest stages. Two consequences:

1. **LLM cost grows linearly with source volume.** A noisy RSS feed of release notes pays the same Sonnet/Haiku tokens as a once-a-week strategic essay.
2. **Digest quality degrades as noise rises.** Theme analysis and digest creation must spend tokens deciding what to ignore instead of what to highlight.

The reference project (https://github.com/dp-pcs/second-brain-ingest) demonstrates the value of an early "is this worth my attention" gate, but its single-pass GPT-4o-mini design is too costly per item for streaming sources at our volume.

We need a **light, tiered, persona-aware filtering and prioritization stage** that sits between ingest and summarization. It must:

- Reject obvious noise cheaply (no LLM calls for things that fail length/language/keyword gates).
- Score remaining items against the active personas' interests using embeddings.
- Reserve LLM judgement for borderline items only.
- Be **auditable and reversible** — keep filtered rows in the database with reason and score so thresholds can be tuned without re-fetching.
- Be **adapter-agnostic** — every existing and future source picks it up without per-adapter changes.

## What Changes

### Data model (one Alembic migration)
- Add columns to `contents`: `filter_score float NULL`, `filter_decision varchar(20) NULL`, `filter_reason text NULL`, `filter_tier varchar(20) NULL`, `priority_bucket varchar(20) NULL`, `filtered_at timestamptz NULL`.
- Add `FILTERED_OUT` value to `ContentStatus` enum (Postgres `ALTER TYPE ADD VALUE` migration — see Top-10 gotcha #2).
- Add indexes on `(status, filter_score DESC)` and `(filter_decision, ingested_at DESC)`.

### New service: `IngestionFilterService` (`src/services/ingestion_filter.py`)
- Three-tier pipeline:
  - **Tier 1 — Heuristic**: length, language, deny/allow keyword lists, source-type rules, dedup-by-near-hash. No network calls.
  - **Tier 2 — Embedding similarity**: encode item title+lead with the existing `EmbeddingProvider`, compare against precomputed persona interest vectors. Cosine score.
  - **Tier 3 — LLM judgement**: only for items in a configurable "borderline" band (e.g. embedding score between `low` and `high` thresholds). Routed through `llm-provider-routing` using the cheapest configured model (default `claude-haiku-4-5`).
- Each tier produces a structured `FilterDecision { decision: keep|skip|borderline, score: float, reason: str, tier: str }`.
- Final decision: `keep` → unchanged status, `skip` → `status = FILTERED_OUT`, plus `priority_bucket ∈ {high, normal, low}` for kept items based on score.

### Hook into ingestion
- New post-persist callback in `src/ingestion/orchestrator.py` invoked by every adapter after `Content` is committed (status=PENDING/PARSED) but before any summarization job is enqueued.
- Wrapped in `@observe()` so Langfuse captures the filter decision as a span — we get cost-savings telemetry for free.

### Persona interest profile
- Extend `settings/personas/*.yaml` with a `filter_profile:` block:
  - `interest_description: str` (free text seed for the embedding profile)
  - `must_include: [str]` keywords (any-match → forced keep)
  - `must_exclude: [str]` keywords (any-match → forced skip)
  - `min_word_count: int`, `languages: [str]`
  - `borderline_band: { low: float, high: float }` thresholds (default 0.45 / 0.65)
- Profile embeddings stored in a small `persona_filter_profiles` table (persona_id, embedding, embedding_provider, embedding_model, updated_at) so they don't have to be re-encoded per item.

### Configuration & per-source overrides
- New YAML domain `settings/filtering.yaml` (loaded via `ConfigRegistry`) with global defaults: tier weights, thresholds, model id, enabled flag.
- Per-source overrides via existing `sources.d/*.yaml` `defaults:` block (e.g. `filter: { override_tier_3: false }`) so a high-signal source like Scholar can skip the LLM tier entirely.
- DB-override pattern (same as `prompt_overrides`) so an admin can flip thresholds without redeploy.

### CLI & API
- `aca ingest` commands gain `--no-filter` and `--filter-dry-run` flags. Dry-run records the decision but never changes status.
- New `aca filter` group: `aca filter rerun --persona <id> --since <date>` (re-evaluates kept items against new profile), `aca filter stats` (precision/recall report from human review actions), `aca filter explain <content-id>` (shows the per-tier scores and reason).
- `GET /api/v1/contents` gains `filter_decision`, `priority_bucket` query params.

### Review feedback loop (foundation only in v1)
- Existing review actions (approve/reject in digest review UI) emit a `filter.review.feedback` event with the original score so a future change can train calibration. v1 just logs; no learned model yet.

### Out of scope (deferred)
- Learned/adaptive user model from feedback (logged for a follow-up).
- Cross-source dedup beyond exact hash (HuggingFace ↔ arXiv overlap is its own change).
- BM25 lexical scoring (handled by `use-paradedb-railway-langfuse-default` once landed).
- Multi-persona scoring fusion (v1 uses the active persona; multi-persona ranking comes later).

## Approaches Considered

### Approach A — Tiered filter service inside the ingestion orchestrator (Recommended)

**Description.** A new `IngestionFilterService` runs synchronously inside the orchestrator's post-persist hook. Tier 1 (heuristics) always runs. Tier 2 (embedding) runs unless the source override disables it. Tier 3 (LLM) runs only for items whose Tier-2 score lands in the borderline band. All decisions are written back to the same `Content` row.

**Pros.**
- Simplest to reason about — synchronous, single round-trip per item.
- Natural fit for the existing `@observe()` tracing — one span per filter decision.
- All tiers can short-circuit cheaply; Tier 3 fires for an estimated 10–20% of items.
- Keeps the data model minimal: just new columns on `contents`.
- Reuses existing `EmbeddingProvider`, `LLMProviderRouter`, and `ConfigRegistry` — no new infra.

**Cons.**
- Synchronous embedding call slows ingest path slightly (mitigated by batching for bulk ingests).
- Filter logic lives in the request/job path; bugs there can stall ingestion until disabled by config flag.

**Effort.** M (1 migration, 1 new service, 1 new model, persona/config schema extensions, CLI surface, ~30 tests).

### Approach B — Asynchronous filter worker as a new pgqueuer job

**Description.** Ingestion writes `Content` with status=PENDING as today. A new `filter_content` job is enqueued. A worker drains the queue, applies the three tiers, and updates the row. Summarization is only enqueued after the filter job completes with `keep`.

**Pros.**
- Filter latency fully decoupled from ingest latency.
- Easier to scale tier-3 LLM calls horizontally.
- Failures in the filter don't block raw ingestion.

**Cons.**
- Adds a new job type, a new state machine, and another point of failure.
- Two queue hops before summarization (filter → summarize). Operationally heavier.
- More moving parts to test (idempotency on retry, queue backlog monitoring, etc.).
- For most sources, the filter is fast enough that async is over-engineering.

**Effort.** L (everything in A plus a new pgqueuer job, worker registration, idempotency story, queue depth alerts).

### Approach C — Single-pass LLM filter, second-brain-ingest style

**Description.** One LLM call per ingested item that returns `{ keep: bool, score: int, reason: str }`. No heuristic tier, no embedding tier. Persona prompt is part of the system message.

**Pros.**
- Smallest amount of code.
- Mirrors the reference project closely — easy to explain.
- One model swap covers everything.

**Cons.**
- Pays an LLM call for every item — defeats the cost-savings goal at high source volume.
- Reasoning quality is whatever the prompt-tuned model gives; no cheap pre-filter for obvious noise.
- Hard to tune (one knob: the prompt) — no per-tier thresholds to adjust.
- Doesn't exploit the existing embedding infrastructure.

**Effort.** S (one service, one prompt, one column).

### Recommended: Approach A

It directly meets the discovery answers (post-ingest pre-summarize stage, three tiers heuristic→embedding→LLM, persona-extended profile, FILTERED_OUT status) with the smallest amount of new infrastructure. Approach B can be a follow-up *if* synchronous filter latency becomes a problem; the service interface in A is designed so the same `IngestionFilterService.filter(content_id)` call can later be invoked from a worker. Approach C is rejected because it does not solve the cost-at-scale problem that motivates the change.

### Selected Approach

**Approach A — Tiered filter service inside the ingestion orchestrator.**

Selected because:
- It maps directly onto the discovery answers (post-ingest/pre-summarize stage, three tiers, persona-extended profile, `FILTERED_OUT` status).
- It reuses `EmbeddingProvider`, `LLMProviderRouter`, `ConfigRegistry`, and `@observe()` — no new infrastructure to operate.
- The service surface `IngestionFilterService.filter(content_id) -> FilterDecision` is designed so that, if synchronous latency ever becomes a problem, the same call can be moved behind a pgqueuer job (Approach B) without changing callers.

Approach B (async worker) and Approach C (single-pass LLM) are demoted below.

**Demoted alternatives.** Approach B adds a queue hop and state machine that aren't justified at current ingest volumes; revisit if synchronous filter latency exceeds ingest SLO. Approach C pays an LLM call per item and does not solve the cost-at-scale goal.
