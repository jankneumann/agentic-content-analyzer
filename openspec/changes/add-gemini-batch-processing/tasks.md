# Tasks: Gemini Batch Processing Infrastructure

## 1. Persistence and configuration

- [ ] 1.1 Generate an Alembic revision and add `batch_jobs`/`batch_requests`,
  lifecycle constraints, integer content FK, unique provider/request keys, and
  active-target deduplication; verify a single Alembic head.
- [ ] 1.2 Add SQLAlchemy models/enums in `src/models/batch.py` and export them so
  metadata and Alembic tests discover the tables.
- [ ] 1.3 Add safe-default `batch_execution`/`batch` YAML and
  `GEMINI_BATCH_ENABLED` settings support with `_env_file=None` tests.

## 2. Gemini router boundary

- [ ] 2.1 Add provider-neutral batch request/result/state dataclasses.
- [ ] 2.2 Add async Gemini-only `LLMRouter.submit_batch` using metadata-correlated
  inline requests and the 18 MiB guard.
- [ ] 2.3 Add `LLMRouter.poll_batch` state normalization and strict per-key result
  extraction for success, partial, missing, duplicate, and error responses.
- [ ] 2.4 Unit-test the installed SDK surface via mocked source clients, including
  non-Google rejection, cancelled/expired states, and no positional correlation.

## 3. Batch orchestration

- [ ] 3.1 Add configuration loading and `is_batch_enabled(step)`.
- [ ] 3.2 Add `BatchCollector.enqueue` with request-key generation, disabled
  no-op behavior, and active-target deduplication.
- [ ] 3.3 Add result/fallback handler protocols and registry.
- [ ] 3.4 Implement concurrency-safe submit grouping and thresholds with
  `FOR UPDATE SKIP LOCKED`, claim/job state transitions, and transport recovery.
- [ ] 3.5 Implement polling, idempotent reconciliation, terminal-job handling,
  partial-result fallback, bounded fallback attempts, and exhaustion failure.
- [ ] 3.6 Add an advisory-lock-protected worker maintenance tick and observability.
- [ ] 3.7 Test collection, thresholds, concurrent claiming SQL, job transitions,
  idempotent duplicate polls, partial results, cancellation, and fallback bounds.

## 4. CLI and cost reporting

- [ ] 4.1 Add read-only `aca batch status` with canonical output and root `--json`.
- [ ] 4.2 Export token assumptions and implement read-only
  `aca evaluate batch-savings` with model pricing, content counts, explicit
  assumptions, and JSON/human output tests.

## 5. Documentation and validation

- [ ] 5.1 Document configuration, latency, inline-size limitation, operations,
  fallback, scheduling, and rollback in `docs/MODEL_CONFIGURATION.md` and
  `CLAUDE.md`.
- [ ] 5.2 Run scoped tests, model/config/CLI regressions, migration tests, Ruff,
  mypy on changed modules, strict OpenSpec validation, and full relevant tests.
- [ ] 5.3 Update traceability/evidence artifacts and mark completed tasks.

## Deferred to follow-up changes

- `batch-ingestion-filter`: blocking-safe post-persist filter rollout.
- `batch-youtube-processing`: persist-first captions/native video and backlog
  resumption.
- Gemini JSONL input/output file-mode batches and provider-file cleanup.
