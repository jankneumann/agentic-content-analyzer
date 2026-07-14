# Design: Ingestion Filtering and Prioritization

## Context

Every ingestion adapter in `src/ingestion/*.py` routes through `src/ingestion/orchestrator.py` and persists a `Content` row before any summarization job is enqueued. Summary.relevance_scores is populated only *after* expensive summarization runs. This design inserts a new synchronous stage between persist and enqueue.

## Design Decisions

### D1 — Synchronous post-persist hook (not a new queue stage)

The filter runs inline in the orchestrator's post-persist callback. Alternatives considered: a dedicated pgqueuer job (Approach B, rejected in proposal) and a pre-persist gate (rejected in discovery). Synchronous is chosen because:

- Tier 1 costs ~microseconds and Tier 2 costs ~10–50ms with batched embedding — well inside our ingest SLO.
- Tier 3 only fires on borderline items; per-item average LLM cost is low once tiers 1–2 short-circuit.
- A single DB transaction covers ingest + filter, avoiding two-phase idempotency problems.

### D2 — One filter service, three tiers, one decision object

`IngestionFilterService.filter(content_id: int) -> FilterDecision` is the only public entry point. Each tier is a private method returning either a terminal `FilterDecision` or `None` ("pass to next tier"). The service composes them in a strict order and produces a single output. This keeps the state machine trivial and each tier independently testable.

```python
class FilterTier(StrEnum):
    HEURISTIC = "heuristic"
    EMBEDDING = "embedding"
    LLM = "llm"

@dataclass
class FilterDecision:
    decision: Literal["keep", "skip"]
    score: float               # [0.0, 1.0]
    tier: FilterTier
    reason: str                # short machine-parseable token, e.g. "embedding.similarity:0.72"
    priority_bucket: Literal["high", "normal", "low"] | None
```

### D3 — Persona profile embeddings are cached in Postgres

Re-encoding the persona interest description on every filter call would dominate latency. We cache profile vectors in a new `persona_filter_profiles` table keyed by `(persona_id, embedding_provider, embedding_model)`. Invalidation is based on the hash of the interest description at load time; a hash change triggers a re-encode. This mirrors the pattern used for `document_chunks.embedding_provider/embedding_model`.

### D4 — New enum value requires `ALTER TYPE ADD VALUE` migration

Per CLAUDE.md gotcha #2, adding `FILTERED_OUT` to `ContentStatus` (a Postgres enum backed by a Python StrEnum) requires an explicit migration using `ALTER TYPE content_status ADD VALUE 'FILTERED_OUT'`. The migration must be committed standalone — `ALTER TYPE ADD VALUE` cannot run inside a transaction block with other DDL. A separate Alembic revision adds the columns in a second, transactional migration.

### D5 — Filter config has three override layers

From lowest to highest precedence:

1. `settings/filtering.yaml` — shipped defaults (thresholds, tier weights, enabled flag, default LLM model id).
2. `sources.d/*.yaml` `defaults.filter` — per-source overrides (e.g. Scholar skips Tier 3).
3. DB override row (same pattern as `prompt_overrides`) — runtime tuning by an admin via the prompt-management API.

`ConfigRegistry` already supports this precedence for prompts and model selection; we add a new registry domain `filtering`.

### D6 — LLM tier routes through existing `LLMProviderRouter`

Tier 3 does NOT talk to Anthropic directly. It constructs a prompt from `settings/prompts.yaml` (new key `pipeline.filter.system`/`user_template`), routes through `LLMProviderRouter`, and consumes the routed model's response. Token/cost metrics flow through the same Langfuse path as summarization. A dedicated model env var `MODEL_CONTENT_FILTER` (default `claude-haiku-4-5`) picks the cheapest quality-adequate model.

### D7 — Orchestrator hook is adapter-agnostic

The hook is a single call inserted in the orchestrator wrapper functions (`ingest_rss`, `ingest_gmail`, `ingest_youtube`, `ingest_url`, etc.) rather than inside each adapter's fetch/parse code. Each adapter still returns its list of persisted `Content` ids; the orchestrator loops over them and calls `IngestionFilterService.filter(id)`. New adapters automatically inherit the behavior as long as they register through the orchestrator.

### D8 — Feedback event is fire-and-forget in v1

Review UI emits `filter.review.feedback` via the existing notification/event bus used by `notification-events` spec. v1 only logs the event and writes to an append-only `filter_feedback_events` table. No calibration or learning happens yet; that's the foundation for a future "learned filter" change.

### D9 — No physical deletion of filtered items

All filtered items stay in `Content` with `status=FILTERED_OUT`. Rationale:

- Threshold tuning is reversible — `aca filter rerun` can flip items back to `PARSED`.
- Audit: operators can inspect why items were skipped.
- Dedup signals persist — a later re-fetch sees the same `content_hash` and skips re-ingest.

A separate retention job (out of scope here) can physically prune `FILTERED_OUT` rows older than N days.

## Data Model

### New columns on `contents`

| Column | Type | Default | Notes |
|---|---|---|---|
| `filter_score` | `float` | `NULL` | Tier final score, `[0.0, 1.0]` |
| `filter_decision` | `varchar(20)` | `NULL` | `keep` / `skip` |
| `filter_tier` | `varchar(20)` | `NULL` | `heuristic` / `embedding` / `llm` |
| `filter_reason` | `text` | `NULL` | machine-parseable short token |
| `priority_bucket` | `varchar(20)` | `NULL` | `high` / `normal` / `low` |
| `filtered_at` | `timestamptz` | `NULL` | when the decision was recorded |

### New indexes on `contents`

- `ix_contents_status_filter_score (status, filter_score DESC)` — feeds priority-ordered summarization queue lookup.
- `ix_contents_filter_decision_ingested (filter_decision, ingested_at DESC)` — admin views and stats queries.

### New table `persona_filter_profiles`

```
persona_id             text        PRIMARY KEY part
embedding_provider     text        PRIMARY KEY part
embedding_model        text        PRIMARY KEY part
interest_hash          text        not null   -- sha256 of the interest_description string
embedding              vector      not null   -- pgvector, dim matches provider
updated_at             timestamptz not null default now()
```

### New table `filter_feedback_events`

```
id                 bigserial primary key
content_id         bigint references contents(id)
persona_id         text not null
original_score     float not null
original_decision  text not null
reviewer_decision  text not null    -- approve / reject / promote / demote
reviewed_at        timestamptz not null default now()
metadata           jsonb
```

### New `ContentStatus` enum value

`FILTERED_OUT` — added via `ALTER TYPE content_status ADD VALUE 'FILTERED_OUT'` in a standalone migration.

## Configuration

### `settings/filtering.yaml` (new)

```yaml
enabled: true
default_model: claude-haiku-4-5
tiers:
  heuristic:
    min_word_count: 40
    allowed_languages: [en]
  embedding:
    provider: null              # null => use global embedding provider
    model: null
  llm:
    enabled: true
borderline_band:
  low: 0.45
  high: 0.65
priority_buckets:
  high_threshold: 0.65
  low_threshold: 0.45
```

### `settings/personas/*.yaml` (extension)

```yaml
filter_profile:
  interest_description: |
    Engineering leadership, AI agents, production ML, and applied AI strategy.
  must_include: []
  must_exclude: ["press release", "sponsored", "advertorial"]
  min_word_count: 60
  languages: [en]
  borderline_band:
    low: 0.45
    high: 0.65
```

### `sources.d/<name>.yaml` (extension)

```yaml
defaults:
  filter:
    enabled: true
    override_tier_3: true     # false to skip LLM for this source
```

## Observability

- `IngestionFilterService.filter` is decorated with `@observe(name="ingestion.filter")`.
- Span attributes: `source_type`, `content_id`, `persona_id`, `decision`, `tier`, `score`, `reason`, `duration_ms`, `llm_tokens` (when Tier 3 ran).
- A new Langfuse dashboard view aggregates `decision` counts per source per day (documentation only — no code change).

## Failure Modes

- **Embedding provider down**: Tier 2 raises; service records `FilterDecision{decision=keep, tier=heuristic, reason="embedding.error:<class>", score=0.0, priority_bucket=normal}`. Fail-open so ingestion continues; the error is traced.
- **LLM provider down on borderline item**: Same fail-open policy — kept with `priority_bucket=low`, `reason="llm.error:<class>"`.
- **Filter service itself throws**: orchestrator logs, records exception span, and proceeds as if filter were disabled (kept, `filter_decision=NULL`). Config flag `filtering.strict=true` overrides this to fail ingest instead; default is lenient.
- **Profile not yet encoded on first call**: synchronous encode-and-cache on first use.

## Rollout

1. Ship the migration with `filtering.enabled=false` in YAML defaults.
2. Enable on one low-volume source (e.g. `scholar`) via `sources.d/scholar.yaml`.
3. Compare filter metrics in Langfuse against a week of baseline ingest.
4. Flip `filtering.enabled=true` globally; override per noisy source as needed.
5. After two weeks of stable operation, enable for all sources by default.

## Open Questions

- [ ] Should we expose filter decisions on the digest review UI in v1 or wait for the learned-calibration follow-up? (Design assumes "not in v1" — purely backend.)
- [ ] Does ParadeDB arrival change the embedding tier design? (Not blocking — BM25 would be an additional signal in a future tier.)
