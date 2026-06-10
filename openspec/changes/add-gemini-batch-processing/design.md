# Design: Gemini Batch API Execution

## Context

Today every Gemini step is a synchronous request/response inside the background
queue worker. `LLMRouter.generate*` build a `google.genai.Client`, call
`generate_content`, and return immediately. `_process_video` (and the content
filter) ingest → call Gemini → write the row, inline and blocking.

The Batch API inverts this into a **deferred-completion** model: collect N
requests → submit one job → wait minutes-to-hours → reconcile results back to
the right rows later. This is the central architectural shift; everything below
exists to make that shift safe, reversible, and incrementally adoptable.

### Verified facts (June 2026)

- **SDK**: `google-genai==1.68.0` ships `Batches`/`AsyncBatches`.
- **Modalities**: batch supports "the same modalities as the interactive API"
  (text, image, audio, PDF, File-API uploads, and YouTube-URL `fileData` parts —
  an interactive-API modality). YouTube-URL understanding accepts **public videos
  only** (not unlisted/private) and is itself in preview, so Phase 3 keeps a
  one-shot smoke test rather than assuming silently.
- **Submission**: inline `GenerateContentRequest[]` (<20MB total) or an input
  JSONL file (<2GB). Each line carries a caller-defined `key`.
- **States**: `JOB_STATE_PENDING | RUNNING | SUCCEEDED | FAILED | CANCELLED |
  EXPIRED`. SLA: 24h target, 48h hard cap (→ `EXPIRED`).
- **Pricing**: exactly 50% of the standard tier on input and output.

## Goals / Non-Goals

**Goals**: cut cost on non-latency-sensitive Gemini steps; build provider-generic
batch plumbing once; make adoption per-step, opt-in, and reversible; never block
or regress the synchronous path when disabled.

**Non-Goals**: batching Claude/OpenAI (schema-ready, not wired); batching
`cloud_stt`/`podcast_script`; changing summarization/theme/digest models.

## Architecture

```
ingest/ filter ──▶ is_batch_enabled(step)?
                      │ no → existing synchronous LLMRouter.generate*  (unchanged)
                      │ yes → BatchCollector.enqueue(step, target, request)
                      ▼
              batch_requests (status=pending)
                      │  batch_submit entrypoint (interval / pg_cron)
                      ▼
   LLMRouter.submit_batch ──▶ client.batches.create ──▶ batch_jobs(status=running)
                      │  batch_poll entrypoint (interval / pg_cron)
                      ▼
   poll_batch ──▶ SUCCEEDED ──▶ reconcile by key ──▶ per-step result handler
                  FAILED/EXPIRED ──▶ synchronous fallback for affected requests
```

### Persistence (Phase 0)

```sql
CREATE TABLE batch_jobs (
    id              uuid PRIMARY KEY,
    provider        varchar(20) NOT NULL,         -- 'google_ai'
    provider_job_name text,                       -- batches/123...; NULL until submitted
    model_id        varchar(64) NOT NULL,         -- logical id, e.g. gemini-3.1-flash-lite
    model_step      varchar(40) NOT NULL,
    state           varchar(24) NOT NULL,          -- pending|running|succeeded|failed|expired
    request_count   integer NOT NULL DEFAULT 0,
    submitted_at    timestamptz,
    completed_at    timestamptz,
    error           text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE batch_requests (
    id              uuid PRIMARY KEY,
    request_key     varchar(64) NOT NULL,          -- stable key echoed in JSONL
    batch_job_id    uuid REFERENCES batch_jobs(id),-- NULL until flushed into a job
    model_step      varchar(40) NOT NULL,
    model_id        varchar(64) NOT NULL,
    target_table    varchar(40) NOT NULL,          -- 'contents'
    target_id       uuid NOT NULL,                 -- row to reconcile back to
    request_payload jsonb NOT NULL,                -- serialized GenerateContentRequest
    status          varchar(20) NOT NULL,          -- pending|submitted|succeeded|failed|fallback
    result_text     text,
    error           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    completed_at    timestamptz
);
CREATE INDEX ix_batch_requests_pending ON batch_requests (model_step, status)
    WHERE status = 'pending';
CREATE INDEX ix_batch_requests_job ON batch_requests (batch_job_id);
```

A **generic target_table/target_id** (rather than a hard FK to `contents`) keeps
the schema reusable for future non-Content steps. `request_key` is the join key
between the JSONL we send and the results we receive.

### Router methods (Phase 0)

```python
async def submit_batch(self, model: str, requests: list[BatchRequest]) -> str:
    """Create a Gemini batch job; return provider_job_name. Chooses inline vs
    input-file by payload size. Each BatchRequest carries (key, contents, config)."""

async def poll_batch(self, provider_job_name: str) -> BatchPollResult:
    """Return (state, results_by_key | None). results_by_key maps request_key ->
    text. Raises only on transport errors; FAILED/EXPIRED are returned states."""
```

These wrap `client.batches.create(model=..., src=...)` and
`client.batches.get(name=...)`. Reuse the existing API-key/credential resolution
from `_generate_gemini`. Keep them provider-internal: `submit_batch` rejects
non-`google_ai` models in Phase 0.

### Collector + per-step result handlers

`BatchCollector.enqueue(step, target_table, target_id, request)` serializes the
request and writes a `batch_requests` row (`status=pending`). The **only** call-
site change per step is:

```python
if batch.is_batch_enabled(ModelStep.CONTENT_FILTERING):
    batch.enqueue(step, "contents", content.id, request); return  # defer
# else: existing synchronous path (unchanged)
```

A registry maps `model_step -> ResultHandler`. Each handler knows how to apply a
reconciled result to its target row (e.g. content_filtering writes
`filter_*`/status; youtube writes `markdown_content` + indexing + status).

### Submit / poll / reconcile

- `batch_submit`: group `pending` requests by `(model_step, model_id)`; for each
  group over a flush threshold (count ≥ N or oldest ≥ T minutes), call
  `submit_batch`, create a `batch_jobs` row, set requests `submitted` with the
  job id. Thresholds in config; default N=50, T=60min.
- `batch_poll`: for each non-terminal `batch_jobs`, `poll_batch`. On `SUCCEEDED`,
  reconcile each result via its handler, mark requests `succeeded`, job
  `succeeded`. On `FAILED`/`EXPIRED`, mark requests `fallback` and re-run them
  synchronously (bounded), so no item is permanently stuck.
- Scheduling: register both as queue entrypoints invoked by a lightweight
  interval loop in the worker (or pg_cron in Railway). Idempotent and
  `SELECT ... FOR UPDATE SKIP LOCKED` safe for concurrent workers.

### Pipeline decoupling (Phase 3 only)

`content_filtering` is advisory (post-persist) — no blocking needed. But
`youtube_processing` output gates summarization/digest, so batching it requires a
new `ContentStatus.PENDING_BATCH`: the row persists immediately as
`PENDING_BATCH`, summarization/digest stages exclude it, and the reconciler flips
it to `PARSED` when the result lands. The daily pipeline already runs ingest →
summarize → digest sequentially, so digests naturally pick up
yesterday-submitted items the next morning.

### `youtube_processing` batching (Phase 3 — two sub-paths)

`youtube_processing` runs at `gemini-3.1-flash-lite` (~$6→$3 per 1k batched) and
has two sub-paths, **both batchable**:

1. **YouTube-URL video** (public videos): submit the `fileData` YouTube-URL part
   directly in the batch request — native-video understanding, no download.
   Supported by modality parity; a one-shot smoke test verifies acceptance
   (YouTube-URL is in preview) before rollout.
2. **Transcript text** (unlisted/private videos, or smoke-test failure): the
   existing `_process_video` transcript fallback, batched as plain text.

Per item, the collector selects the sub-path from **video-level** visibility
(public video → video part; private/unlisted *video* → transcript), mirroring
today's synchronous fallback. Note the granularity: an **unlisted playlist of
public videos** (e.g. "Jan's AI Playlist") still uses the **video** sub-path —
the Data API returns its public video IDs and each public video processes by URL.
Playlist visibility never reaches the per-video Gemini call.

### Config

```yaml
# settings/models.yaml
batch_execution:          # per-step execution mode; absent ⇒ sync
  content_filtering: sync # flipped to 'batch' in Phase 1
  caption_proofreading: sync
  youtube_rss_processing: sync
  youtube_processing: sync
batch:
  enabled: false          # GEMINI_BATCH_ENABLED global kill-switch
  flush_max_requests: 50
  flush_max_wait_minutes: 60
  fallback_on_expire: true
```

### CLI: `aca evaluate batch-savings` (the cost-report dry-run)

Read-only. Loads model pricing + `TOKEN_ESTIMATES` + actual `contents` volumes,
prints per-step standard vs batch cost (the table in proposal.md) and a backfill
+ steady-state projection. `--json` for machine consumption. This is the command
that does not exist today; it lands in Phase 0 so adoption decisions are
data-driven.

## Risks / Trade-offs

- **ROI is modest at current volume** (~$11 one-time backfill; small monthly).
  Mitigation: build core once, prove on the cheap pilot; value batch as
  cost + rate-limit + scale insurance, not a large cash saving.
- **YouTube-URL is preview + public-only** → Phase 3 keeps a one-shot smoke test
  and routes unlisted/private items to the (batchable) transcript sub-path.
- **24–48h latency** → `PENDING_BATCH` status + digest exclusion; advisory steps
  need neither.
- **Partial/expired failures** → mandatory synchronous fallback path; no item
  permanently stuck.
- **Operational surface** (a poller, a new table) → justified by reuse across
  steps and future providers; fully inert when disabled.

## Migration / Rollout

1. Ship Phase 0 with all `batch_execution` steps = `sync` (no behavior change).
2. Flip `content_filtering` → `batch` in a single environment; watch
   `aca batch status` and reconciliation; compare filter outcomes vs sync.
3. Extend to Phase 2 text steps; then decide Phase 3 from the verification task.
4. Roll back any step instantly by flipping it back to `sync` (in-flight jobs
   still reconcile; no data loss).
