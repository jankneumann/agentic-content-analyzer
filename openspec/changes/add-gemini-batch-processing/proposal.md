# Add Gemini Batch API Execution for Non-Latency-Sensitive Steps

## Why

Several pipeline steps call Gemini synchronously, one item at a time, from the
background queue worker — they are **not** in any user-facing request path:
`content_filtering`, `caption_proofreading`, `youtube_rss_processing`, and
`youtube_processing`. Google's [Batch API](https://ai.google.dev/gemini-api/docs/batch-mode)
charges a **flat 50% discount** on input *and* output tokens with a target
turnaround of 24h (48h hard cap). Because these steps already run
asynchronously and tolerate hours of latency, they are natural batch
candidates.

### Honest ROI (from the `aca evaluate batch-savings` dry-run, see design.md)

Measured against the current corpus (4,846 content items, 2,026 YouTube) at the
new Gemini 3.x pricing:

| Step | Model | $/1k std | $/1k batch | Batchable? |
|------|-------|---------:|-----------:|------------|
| `content_filtering` | gemini-3.1-flash-lite | 0.53 | 0.26 | ✅ text |
| `youtube_rss_processing` (transcript path) | gemini-3.1-flash-lite | 4.25 | 2.12 | ✅ text |
| `caption_proofreading` | gemini-3.1-flash-lite | 7.50 | 3.75 | ✅ text |
| `youtube_processing` (YouTube-URL video) | gemini-3.1-flash-lite | 6.00 | 3.00 | ✅ video (public only) |

All four batch-eligible steps run on **`gemini-3.1-flash-lite`** and are **all
batchable**: the Batch API supports "the same modalities as the interactive API,"
and YouTube-URL `fileData` parts are an interactive-API modality
([video-understanding#youtube](https://ai.google.dev/gemini-api/docs/video-understanding#youtube)).
Batch therefore becomes a **uniform, low-risk** transformation rather than a
risky special case. Measured against the existing corpus, the whole batchable
backfill is **$22.30 → $11.15 (~$11 one-time)**; steady-state savings remain
small at personal scale, so the durable value is **cost + rate-limit avoidance +
headroom for volume growth**, proven incrementally.

**Two caveats baked into the design:**

1. **Public-video-only applies at the *video* level, not the playlist.**
   Gemini's YouTube-URL understanding accepts *public videos*. An **unlisted
   playlist of public videos** (e.g. "Jan's AI Playlist") is fully fine — the
   Data API returns its public video IDs and each is processed by `watch?v=` URL
   normally; playlist visibility is irrelevant to the per-video call. Only a
   genuinely *private/unlisted video* falls back to the (also-batchable)
   transcript path. So the video-URL sub-path is the common case; the transcript
   sub-path is the rare exception.
2. **YouTube-URL is itself in preview.** No doc *names* batch + YouTube-URL
   explicitly, so Phase 3 keeps a one-shot smoke test (submit a single
   YouTube-URL request as a batch) as cheap insurance — not a blocking gate.

The core batch infrastructure is built once and proven on the safest step
(`content_filtering`), then extended pipeline-by-pipeline.

## What Changes

### Core infrastructure (Phase 0 — build once)
- **Persistence**: two new tables — `batch_jobs` (provider job handle + state)
  and `batch_requests` (per-item request keyed to a target row, with result and
  fallback state). One Alembic migration.
- **Router**: add `LLMRouter.submit_batch(model, requests)` and
  `poll_batch(job_name)` wrapping `google-genai` `client.batches.create/get`
  (SDK 1.68.0 ships `Batches`/`AsyncBatches`). Build JSONL with stable per-item
  keys; support inline (<20MB) and input-file (JSONL) modes.
- **Collector**: a `BatchCollector.enqueue(step, target, request)` that persists
  a `batch_requests` row instead of calling Gemini inline. Call sites consult
  `is_batch_enabled(step)` and branch.
- **Submitter + Poller**: new queue-worker entrypoints `batch_submit` and
  `batch_poll` (driven by an interval / pg_cron), flushing pending requests into
  a job and reconciling completed jobs back to their target rows.
- **Reconciler + fallback**: match each result by key → target row → per-step
  result handler; on `JOB_STATE_FAILED`/`JOB_STATE_EXPIRED` or per-request
  errors, fall back to the existing synchronous path.
- **Config**: a `batch_execution:` map in `settings/models.yaml` (per-step
  `sync|batch`) plus `GEMINI_BATCH_ENABLED` global flag and flush thresholds
  (max requests / max wait). Default **OFF** — opt-in, reversible.
- **CLI**: `aca evaluate batch-savings` (the cost-report dry-run; read-only) and
  `aca batch status|flush|poll` ops commands.
- **Observability**: reuse the existing `NotificationEventType.BATCH_SUMMARY`
  event and wrap submit/poll/reconcile in `@observe()` spans.

### Pipeline enablement (later phases, incremental)
- **Phase 1 — `content_filtering`** (pilot): post-persist, advisory, safe to
  defer (an item simply stays unfiltered until the batch lands). No pipeline
  blocking. Smallest blast radius — proves the plumbing end-to-end.
- **Phase 2 — `caption_proofreading` + `youtube_rss_processing`** (text/transcript
  path): both already text once captions/transcripts are fetched.
- **Phase 3 — `youtube_processing`**: batch both the YouTube-URL video sub-path
  (public videos) and the transcript sub-path (the unlisted/private fallback).
  Introduces `PENDING_BATCH` Content status so the digest pipeline excludes
  not-yet-ready items. A one-shot smoke test confirms YouTube-URL batch
  acceptance before rollout (insurance, not a blocking gate).

### Pipeline decoupling
- Add `ContentStatus.PENDING_BATCH` (Postgres `ALTER TYPE ADD VALUE` migration —
  Top-10 gotcha #2) for steps whose output gates downstream work. Digest/
  summarization stages SHALL exclude `PENDING_BATCH` rows.

## Approaches Considered

### Approach A — Dedicated `batch_jobs` + `batch_requests` tables + poller worker (Recommended)
A durable request table (generic `target_table`/`target_id`) collects deferred
requests; a flush worker groups them into a Gemini batch job; a poll worker
reconciles results back via per-step handlers.
- **Pros**: durable across restarts/24h windows; provider- and step-generic;
  clean separation from the per-item queue; reuses `SELECT FOR UPDATE SKIP LOCKED`.
- **Cons**: new schema (2 tables) + a poller surface to operate.
- **Effort**: L (split into M-sized tasks per phase).

### Approach B — Reuse `pgqueuer_jobs` + status fields on `Content`
Encode each deferred request as a queue job and track batch state via Content
status; no new request table.
- **Pros**: less new schema; leans on existing worker infra.
- **Cons**: conflates two async models (per-item queue vs. batch grouping);
  grouping N requests into one Gemini job is awkward on a per-job queue; couples
  to `Content` only (no generic reuse); harder to reconcile partial results.
- **Effort**: M.

### Approach C — In-memory collector, flush-at-end-of-run, no persistence
Buffer requests in memory during an ingestion run, submit one batch, poll inline.
- **Pros**: smallest; fastest pilot.
- **Cons**: not durable (crash/restart loses in-flight requests); can't span the
  24–48h batch window or multiple runs; doesn't generalize beyond the pilot.
- **Effort**: S.

**Recommended: A.** The batch model is inherently deferred across hours and
process restarts, so durability (Approach A's request table) is a requirement,
not a nicety — C cannot survive the 24h window and B cannot cleanly group
requests into a single job or reconcile partial failures. A's generic
target/handler design is also what makes the phased rollout (filtering → captions
→ youtube) additive rather than a rewrite per step.

### Selected Approach (Gate 1)

**Approach A — dedicated `batch_jobs` + `batch_requests` tables + poller worker.**
Chosen because batch execution is inherently deferred across hours and process
restarts, so a durable request store is a requirement; the generic
target/handler design makes the phased rollout additive. No modifications
requested at Gate 1.

## Impact

- **Affected specs**: new capability `gemini-batch-execution`; touches
  `cli-interface` (new commands) and `model-configuration` (batch toggles).
- **Affected code**: `src/services/llm_router.py`, `src/services/content_filter.py`,
  `src/ingestion/youtube.py`, `src/queue/worker.py`, `src/config/models.py`,
  `settings/models.yaml`, new `src/services/batch/` package, new Alembic
  migrations, new `src/cli/` surface.
- **Backward compatibility**: fully gated behind `GEMINI_BATCH_ENABLED=false`
  default. With the flag off, every call path is byte-for-byte the current
  synchronous behavior.
- **Non-goals**: Anthropic Message Batches / OpenAI Batch (the schema is
  provider-generic, but only Gemini is wired here); batching latency-sensitive
  steps (`cloud_stt`, `podcast_script`) stays synchronous.
