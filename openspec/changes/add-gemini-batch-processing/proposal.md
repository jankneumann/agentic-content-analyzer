# Add Gemini Batch Processing Infrastructure

## Why

Several background-only pipeline steps use Gemini and could eventually use the
Gemini Batch API's lower-cost asynchronous execution. The repository does not
currently have durable provider-job tracking, request/result correlation,
reconciliation, bounded fallback, or operational controls for batch work.

The current code does **not** support the original assumption that each call
site can simply enqueue and return:

- post-persist ingestion filtering runs before summarization and can transition
  content to `FILTERED_OUT`;
- caption proofreading and both YouTube Gemini paths consume model output before
  a `Content` row exists;
- the pipeline summarizes explicit ingestion receipt IDs, so a result that
  reconciles tomorrow is not automatically picked up by tomorrow's pipeline.

This change therefore builds and validates the reusable, opt-in core while
leaving all execution modes `sync`. Call-site enablement is split into focused
follow-ups that can define the required gating and resume semantics honestly.

## What Changes

- Add durable `batch_jobs` and `batch_requests` persistence with integer content
  targets, unique request keys, active-target deduplication, lifecycle states,
  bounded fallback attempts, and timestamps/errors for recovery and operations.
- Add Gemini-only `LLMRouter.submit_batch()` and `poll_batch()` methods using the
  installed `google-genai==1.68.0` asynchronous batch client. Phase 0 supports
  metadata-correlated inline requests below a conservative size limit; file-mode
  jobs are explicitly deferred.
- Add a provider-neutral `src/services/batch/` core: configuration, collector,
  result-handler registry, submit, poll, reconcile, cancellation handling, and
  synchronous fallback hooks.
- Add a leader-elected batch-maintenance tick to the embedded worker. A
  PostgreSQL advisory lock ensures only one worker submits and polls each tick;
  no free-form queue entrypoint bypasses canonical operation projection.
- Add `batch_execution` and `batch` settings with safe defaults (`sync`, disabled)
  and a `GEMINI_BATCH_ENABLED` kill switch.
- Add read-only `aca batch status` and `aca evaluate batch-savings`, including
  canonical root `--json` output.
- Add observability, tests, and operator documentation. With batching disabled,
  no existing Gemini call site changes behavior or writes batch rows.

## Deferred Follow-ups

- **`batch-ingestion-filter`**: choose blocking-safe semantics for the borderline
  LLM tier, including content status gating and pipeline receipt behavior.
- **`batch-youtube-processing`**: persist transient transcript/video context,
  batch caption/native-video work, and add a durable ready-for-summarization
  backlog/resume workflow.
- **Gemini input-file batches**: JSONL upload/output download, per-line parsing,
  provider-file cleanup, and payloads above the inline size ceiling.

## Impact

- **Affected specs**: new `gemini-batch-execution`; deltas for `cli-interface`,
  `llm-provider-routing`, and `settings-management`.
- **Affected code**: `src/services/llm_router.py`, new `src/services/batch/`,
  `src/models/batch.py`, `src/queue/worker.py`, `src/config/settings.py`,
  `settings/models.yaml`, new Alembic migration, and CLI/docs/tests.
- **Backward compatibility**: all modes remain synchronous and the global switch
  defaults false. Existing provider and pipeline paths are unchanged.
- **Non-goals**: call-site rollout, YouTube/caption persistence redesign,
  file-mode Gemini batches, other providers, or latency-sensitive steps.
