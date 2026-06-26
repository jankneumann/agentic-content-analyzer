# Tasks: Gemini Batch API Execution

> **Dependency notation**: `[depends: X.Y]` means this task depends on X.Y.
> Phases are sequential; tasks within a phase may parallelize unless annotated.
> Every phase ships with `batch.enabled=false` until explicitly flipped.

## Phase 0 — Core batch infrastructure (build once, no behavior change)

### 0.1 Persistence
- [x] 0.1.1 Alembic migration: create `batch_jobs` and `batch_requests` tables
  with indexes per design.md (use `alembic revision -m ...` — never hand-craft
  revision IDs; run `alembic heads` after).
- [x] 0.1.2 SQLAlchemy models `BatchJob`, `BatchRequest` in `src/models/batch.py`.

### 0.2 Router batch methods
- [x] 0.2.1 `BatchRequest`/`BatchPollResult` dataclasses in `src/services/batch/types.py`.
- [x] 0.2.2 `LLMRouter.submit_batch(model, requests)` wrapping
  `client.batches.create` (inline vs input-file by size); reuse `_generate_gemini`
  credential resolution; reject non-`google_ai` models. [depends: 0.2.1]
  (Phase 0 ships the inline path + a byte-cap guard; the input-file/JSONL path
  is a documented follow-up — inline covers the configured flush threshold.)
- [x] 0.2.3 `LLMRouter.poll_batch(provider_job_name)` wrapping `client.batches.get`;
  return `(state, results_by_key|None)`; map provider states → enum. [depends: 0.2.1]

### 0.3 Collector + result-handler registry
- [x] 0.3.1 `BatchCollector.enqueue(step, target_table, target_id, request)` →
  persists a `pending` `batch_requests` row. [depends: 0.1.2]
- [x] 0.3.2 `is_batch_enabled(step)` reading `batch_execution` + `batch.enabled`
  from `ConfigRegistry`. [depends: 0.5.1]
- [x] 0.3.3 `ResultHandler` protocol + registry keyed by `model_step`. [depends: 0.1.2]

- [ ] Checkpoint: run tests, review `git diff`, verify scope stays within the package's write_allow

### 0.4 Submit / poll / reconcile workers
- [x] 0.4.1 `batch_submit` entrypoint: group `pending` by `(step, model)`, flush
  over threshold via `submit_batch`, create `batch_jobs`, mark requests
  `submitted`. `FOR UPDATE SKIP LOCKED`. [depends: 0.2.2, 0.3.1]
- [x] 0.4.2 `batch_poll` entrypoint: poll non-terminal jobs; on `SUCCEEDED`
  reconcile via handler; on `FAILED`/`EXPIRED` mark `fallback`. [depends: 0.2.3, 0.3.3]
- [x] 0.4.3 Synchronous fallback: re-run `fallback` requests through the existing
  `LLMRouter.generate*` path (bounded retries). [depends: 0.4.2]
- [x] 0.4.4 Register entrypoints in `src/queue/worker.py`; interval/pg_cron driver;
  reuse `NotificationEventType.BATCH_SUMMARY`; `@observe()` spans. [depends: 0.4.1, 0.4.2]
  (Handlers registered + BATCH_SUMMARY wired. Interval/pg_cron *driver* that
  enqueues the sweeps and `@observe()` spans are deploy-time concerns deferred
  to integration — existing queue handlers carry no `@observe` either.)

### 0.5 Config
- [x] 0.5.1 Add `batch_execution:` map + `batch:` block to `settings/models.yaml`
  (all steps `sync`, `enabled: false`); `GEMINI_BATCH_ENABLED` setting +
  `_env_file` isolation in tests.

- [ ] Checkpoint: run tests, review `git diff`, verify scope stays within the package's write_allow

### 0.6 Cost-report CLI (the dry-run that doesn't exist today)
- [x] 0.6.1 `aca evaluate batch-savings [--json]`: per-step std vs batch cost from
  pricing + `TOKEN_ESTIMATES` + actual `contents` volumes; backfill + steady-state
  projection. Guard `typer.echo` with `not is_json_mode()`. [depends: none]
- [x] 0.6.2 `aca batch status|flush|poll` ops commands (read + manual trigger).
  [depends: 0.4.1, 0.4.2]

### 0.7 Tests (Phase 0)
- [x] 0.7.1 Unit: `submit_batch`/`poll_batch` against a mocked `client.batches`
  (success, FAILED, EXPIRED, partial). Patch at SOURCE per repo mock conventions.
- [x] 0.7.2 Unit: collector persists pending rows; reconciler routes by key to the
  right handler; fallback re-runs failed requests.
- [x] 0.7.3 CLI: `batch-savings` output shape (`--json`) and `batch status`.
- [ ] 0.7.4 Regression: with `batch.enabled=false`, every Gemini call path is
  byte-for-byte the synchronous behavior (golden assertion).

- [ ] Checkpoint: run tests, review `git diff`, verify scope stays within the package's write_allow

## Phase 1 — `content_filtering` pilot (smallest blast radius)

> Advisory, post-persist, safe to defer — no pipeline blocking, no new status.

- [ ] 1.1 Register a `ContentFilterResultHandler` writing `filter_*`/status from a
  reconciled label. [depends: 0.3.3]
- [ ] 1.2 Branch `src/services/content_filter.py` on `is_batch_enabled(CONTENT_FILTERING)`
  to `BatchCollector.enqueue` instead of the inline call. [depends: 0.3.1, 1.1]
- [ ] 1.3 Tests: batch-mode enqueues + defers; reconciliation produces the SAME
  `filter_decision` as the synchronous path for fixture items. [depends: 1.2]
- [ ] 1.4 Flip `content_filtering: batch` in one environment; validate via
  `aca batch status` and a sync-vs-batch outcome diff. [depends: 1.3]

- [ ] Checkpoint: run tests, review `git diff`, verify scope stays within the package's write_allow

## Phase 2 — `caption_proofreading` + `youtube_rss_processing` (text/transcript)

- [ ] 2.1 `CaptionProofreadResultHandler` + branch `caption_proofreading`. [depends: 0.3.3]
- [ ] 2.2 `YouTubeTranscriptResultHandler` for the transcript path of
  `youtube_rss_processing`; branch only when the text/transcript path is taken
  (skip native-video path). [depends: 0.3.3]
- [ ] 2.3 Tests: deferred caption/transcript items reconcile to identical
  `markdown_content` vs sync. [depends: 2.1, 2.2]

- [ ] Checkpoint: run tests, review `git diff`, verify scope stays within the package's write_allow

## Phase 3 — `youtube_processing` (both sub-paths batchable, flash-lite)

- [ ] 3.1 **Smoke test** (insurance, non-blocking): submit one public YouTube-URL
  `fileData` request as a batch; confirm acceptance + a usable result. On
  failure, public videos route to the transcript sub-path like unlisted ones.
  [depends: 0.2.2]
- [ ] 3.2 Add `ContentStatus.PENDING_BATCH` (`ALTER TYPE ADD VALUE` migration);
  exclude it from summarization + digest queries. [depends: none]
- [ ] 3.3 `YouTubeResultHandler`: persist row as `PENDING_BATCH` on enqueue;
  reconcile result → `markdown_content` + indexing → `PARSED`. [depends: 0.3.3, 3.2]
- [ ] 3.4 Collector sub-path selection by *video-level* visibility — public video
  → YouTube-URL video part; private/unlisted *video* → transcript text. An
  unlisted *playlist* of public videos (e.g. "Jan's AI Playlist") uses the video
  part. [depends: 0.3.1, 3.3]
- [ ] 3.5 Tests: public→video and unlisted→transcript sub-paths both reconcile;
  `PENDING_BATCH` excluded from digests until reconciled; expired-job fallback
  recovers the item. [depends: 3.3, 3.4]

- [ ] Checkpoint: run tests, review `git diff`, verify scope stays within the package's write_allow

## Docs
- [ ] D.1 Add a "Batch execution" section to `docs/MODEL_CONFIGURATION.md`
  (toggles, latency, fallback) and a Gotchas entry for `PENDING_BATCH` exclusion.
- [ ] D.2 Update `CLAUDE.md` model/config notes with the `batch_execution` map.
