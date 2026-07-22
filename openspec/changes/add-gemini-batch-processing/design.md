# Design: Gemini Batch Processing Infrastructure

## Context

The repository uses `google-genai==1.68.0`. Gemini calls currently create a
client inside `LLMRouter` and complete synchronously from the caller's point of
view. Batch execution instead requires durable collection, provider submission,
later polling, correlation, reconciliation, and fallback.

Current-code review changed the scope. The post-persist ingestion filter may
block summarization by setting `FILTERED_OUT`, while caption and YouTube model
calls happen before `Content` persistence. Those call sites require separate
workflow designs. This change ships only the inert reusable core.

Official Batch API details used here:

- inline requests are supported below 20 MB and inline results echo request
  metadata;
- `client.aio.batches.create/get` provide non-blocking SDK calls;
- terminal states include `SUCCEEDED`, `FAILED`, `CANCELLED`, and `EXPIRED`;
- batch creation is not idempotent, so database claiming prevents concurrent
  duplicate submission but cannot eliminate the provider-accepted/DB-crash
  orphan window.

Sources:
- https://ai.google.dev/gemini-api/docs/batch-api
- https://googleapis.github.io/python-genai/genai.html#genai.batches.AsyncBatches

## Decisions

### D1 — Core-only rollout

No production call site branches to batch mode in this change. The collector
and handlers are exercised through unit/integration tests, CLI operations, and
future follow-ups. Safe defaults preserve current behavior exactly.

### D2 — Content targets are typed integers

`contents.id` is an auto-incrementing integer, not UUID. Phase 0 stores a
nullable `content_id BIGINT REFERENCES contents(id) ON DELETE SET NULL` rather
than a generic UUID target. Provider-generic targets can be introduced when a
second target type exists.

### D3 — Explicit lifecycle and deduplication

`batch_jobs.state` uses `submitting|pending|running|succeeded|failed|cancelled|expired`.
`batch_requests.status` uses
`pending|claimed|submitted|succeeded|fallback|failed`. `request_key` is unique,
and a partial unique index prevents more than one active request for the same
`(model_step, content_id)`.

Submission locks eligible rows with `FOR UPDATE SKIP LOCKED`, creates a
`submitting` job, and marks requests `claimed` before the provider call. On
success it records the provider job name and marks requests `submitted`. On a
transport failure it returns requests to `pending` and marks the job failed.
The provider create API is not idempotent: a process crash after provider
acceptance but before the local commit may orphan a provider job. Such jobs are
visible only provider-side; automatic blind resubmission is deliberately not
claimed to be exactly-once.

### D4 — Inline batches first

Phase 0 serializes Gemini `InlinedRequest` objects with
`metadata={"request_key": ...}` and rejects groups at or above an 18 MiB
conservative ceiling before provider submission. Rejected groups remain pending
and surface an actionable error. JSONL input/output file mode is deferred
because it requires provider-file lifecycle and output parsing not needed for
the initial small-request candidates.

### D5 — Async SDK boundary

`LLMRouter.submit_batch` and `poll_batch` use `client.aio.batches.create/get` and
the same `GOOGLE_API_KEY` and provider-model resolution as existing Gemini
generation. Non-Google models are rejected before an SDK call.

`poll_batch` normalizes provider states and returns per-key success/error
records. Missing metadata, duplicate keys, missing results, and per-request
errors are treated as request failures rather than silently paired by position.

### D6 — Idempotent reconciliation and bounded fallback

Result handlers are keyed by `ModelStep` and receive a session, request row,
and result text. A terminal request is never applied twice. Provider job
`FAILED`, `CANCELLED`, or `EXPIRED`, missing results, and errored results move
requests to `fallback`. Fallback execution is delegated to a registered handler
and bounded by `batch.fallback_max_attempts`; exhaustion marks the request
`failed` with an error.

No production handler is registered in this core-only change. Tests register
deterministic handlers, and follow-up changes own their domain handlers.

### D7 — Leader-elected worker maintenance

The embedded worker invokes a periodic batch-maintenance tick that tries a
fixed PostgreSQL advisory lock. The lock winner submits eligible requests and
polls active jobs; other workers skip the tick. The maintenance tick is not a
user-facing workflow and does not create an untyped queue entrypoint that would
break canonical operation projection. `aca batch status` is read-only; this
change intentionally exposes no direct mutation command.

### D8 — Configuration and reporting

```yaml
batch_execution:
  content_filtering: sync
  caption_proofreading: sync
  youtube_rss_processing: sync
  youtube_processing: sync
batch:
  enabled: false
  flush_max_requests: 50
  flush_max_wait_minutes: 60
  fallback_max_attempts: 1
  inline_max_bytes: 18874368
```

`GEMINI_BATCH_ENABLED` overrides `batch.enabled`. Per-step mode is effective only
when both the global switch and that step's mode are enabled.

`aca evaluate batch-savings` reports assumptions instead of presenting
unreproducible measured savings. It uses model pricing, exported per-step token
estimates, database content counts, and a documented 50% batch multiplier. It
is read-only and supports `aca --json evaluate batch-savings`.

## Persistence

`batch_jobs` stores provider, provider job name, logical model/step, state,
request count, timestamps, and error. `provider_job_name` is unique when set.

`batch_requests` stores unique request key, job FK, step/model, nullable content
FK, serialized provider-neutral prompt/config payload, lifecycle status,
result/error, fallback attempt count, and timestamps. JSON payloads contain no
API keys or other credentials.

## Failure Modes

- provider transport error during submit: job `failed`, claims returned pending;
- nonterminal poll: no request mutation;
- failed/cancelled/expired job: incomplete requests enter bounded fallback;
- partial/missing/duplicate/errored output: only affected requests fall back;
- duplicate poll/result: terminal requests are skipped idempotently;
- fallback exception: increment attempt count, retry within bound, then fail;
- oversized inline group: no provider call; requests remain pending and CLI/status
  exposes the reason;
- batching disabled: collector reports disabled and writes nothing.

## Migration / Rollback

The migration adds two tables and indexes only. Runtime behavior remains off.
Rollback is disabling the flag (default) and reverting code; dropping tables is
optional and destructive, so the downgrade migration removes them only when an
operator explicitly runs Alembic downgrade.
