# Architecture Impact: add-gemini-batch-processing

## Summary

This change adds an inert, durable execution substrate for Gemini Batch API
work. It does not alter current ingestion or processing behavior because the
global and per-step switches default off and no production caller opts in.

## Boundaries Added

- **Persistence**: `batch_jobs` and `batch_requests` model provider work,
  per-request lifecycle, content ownership, correlation keys, and bounded
  fallback attempts. Partial unique indexes prevent concurrent active work for
  the same content/step/model target.
- **Provider adapter**: `LLMRouter.submit_batch` and `poll_batch` expose an
  asynchronous Gemini-only boundary. Callers use provider-neutral request and
  result types; metadata keys, rather than positional order, correlate results.
- **Orchestration**: collection, submit, poll/reconcile, and synchronous
  fallback are separate services. Durable claim commits and per-request
  savepoints define crash and handler-failure boundaries.
- **Scheduling**: an advisory-lock-protected maintenance tick runs inside the
  existing worker process. It adds no free-form queue operation or public write
  surface.
- **Operations**: `aca batch status` and `aca evaluate batch-savings` are
  read-only inspection/reporting surfaces.

## Existing Consumers

There are no new production consumers. Existing synchronous LLM calls,
ingestion gating, YouTube processing, queue operation types, HTTP APIs, MCP
tools, and frontend flows remain unchanged.

## Data and Failure Semantics

- Claims are committed before the non-idempotent provider create call.
- Stale interrupted submissions are recovered after a grace period; the
  documented provider-accepted/local-commit orphan window remains observable.
- Poll reconciliation is idempotent and isolates result-handler failures with
  savepoints.
- Fallback attempts are committed before external calls, bounding repeated
  spend even if a worker is interrupted.
- Credential-like keys anywhere in the request payload are rejected before the
  JSON payload is persisted.

## Rollback and Follow-up

Operational rollback is immediate: leave `GEMINI_BATCH_ENABLED=false` or
disable each step. The additive tables and adapter can remain dormant. Removing
the schema uses the Alembic downgrade only when no retained batch history is
needed.

Production adoption requires separate persist-first/resume designs for the
ingestion filter and YouTube/caption workflows. Those follow-ups are explicitly
outside this change.
