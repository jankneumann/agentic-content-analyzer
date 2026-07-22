# Change Context: add-gemini-batch-processing

## Requirement Traceability Matrix

| Req ID | Spec Source | Description | Contract Ref | Design Decision | Files Changed | Test(s) | Evidence |
|--------|-------------|-------------|--------------|-----------------|---------------|---------|----------|
| cli-interface.1 | `specs/cli-interface/spec.md` | Read-only batch operator commands | --- | D7, D8 | `src/cli/batch_commands.py`, `src/cli/evaluate_commands.py` | `tests/cli/test_batch_commands.py` | Pending final validation |
| gemini-batch-execution.1 | `specs/gemini-batch-execution/spec.md` | Safe-default batch configuration | --- | D1, D8 | `src/config/settings.py`, `src/config/models.py`, `settings/models.yaml` | `tests/config/test_batch_config.py` | Pending final validation |
| gemini-batch-execution.2 | `specs/gemini-batch-execution/spec.md` | Durable request collection | Database migration | D2, D3 | `src/models/batch.py`, `src/services/batch/collector.py`, `alembic/versions/1e6a460b6722_add_batch_execution_tables.py` | `tests/test_models/test_batch.py`, `tests/test_services/test_batch_collector.py`, `tests/migrations/test_batch_execution.py` | Pending final validation |
| gemini-batch-execution.3 | `specs/gemini-batch-execution/spec.md` | Concurrency-safe submission | Database migration | D3, D4 | `src/services/batch/workers.py` | `tests/test_services/test_batch_workers.py` | Pending final validation |
| gemini-batch-execution.4 | `specs/gemini-batch-execution/spec.md` | Metadata-keyed Gemini adapter | Official Gemini Batch API | D4, D5 | `src/services/llm_router.py`, `src/services/batch/types.py` | `tests/test_services/test_llm_router_batch.py` | Pending final validation |
| gemini-batch-execution.5 | `specs/gemini-batch-execution/spec.md` | Idempotent reconciliation and bounded fallback | --- | D6 | `src/services/batch/handlers.py`, `src/services/batch/workers.py` | `tests/test_services/test_batch_workers.py` | Pending final validation |
| gemini-batch-execution.6 | `specs/gemini-batch-execution/spec.md` | Observable batch operations | --- | D7 | `src/services/batch/workers.py`, `src/queue/worker.py`, `src/cli/batch_commands.py` | `tests/test_services/test_batch_workers.py`, `tests/cli/test_batch_commands.py` | Pending final validation |
| gemini-batch-execution.7 | `specs/gemini-batch-execution/spec.md` | Reproducible read-only savings report | --- | D8 | `src/services/batch/savings.py`, `src/cli/evaluate_commands.py` | `tests/test_services/test_batch_savings.py`, `tests/cli/test_batch_commands.py` | Pending final validation |
| llm-provider-routing.1 | `specs/llm-provider-routing/spec.md` | Gemini-only batch adapter | Official google-genai async API | D5 | `src/services/llm_router.py` | `tests/test_services/test_llm_router_batch.py` | Pending final validation |
| settings-management.1 | `specs/settings-management/spec.md` | Safe batch settings precedence | --- | D8 | `src/config/settings.py`, `src/config/models.py`, `settings/models.yaml` | `tests/config/test_batch_config.py` | Pending final validation |

## Design Decision Trace

| Decision | Rationale | Implementation | Why This Approach |
|----------|-----------|----------------|-------------------|
| D1 | Keep rollout inert | Global and per-step switches default off | Existing synchronous behavior remains unchanged. |
| D2 | Match persisted identity | Nullable integer `content_id` FK | `Content.id` is an integer and no second target type exists. |
| D3 | Make lifecycle explicit | Job/request states, keys, claims, partial unique index | Multiple workers can coordinate without duplicating active targets. |
| D4 | Start with inline requests | 18 MiB preflight limit | Avoids an incomplete provider-file lifecycle. |
| D5 | Preserve an async boundary | `client.aio.batches.create/get` | Queue maintenance does not block the event loop on SDK network calls. |
| D6 | Reconcile once and bound recovery | Terminal guards and fallback attempt limits | Retries remain safe and permanently failing requests become visible. |
| D7 | Elect one maintainer | PostgreSQL advisory lock in the worker tick | Maintenance stays internal and does not expand canonical operation types. |
| D8 | Expose read-only operations | Status and assumptions-based savings commands | Operators can inspect and estimate without triggering remote work. |

## Scope Corrections from Current-Code Review

- Production ingestion-filter and YouTube/caption call sites are deferred because they need workflow-specific persistence and resume designs.
- The batch core uses an integer content FK rather than the proposal's original generic UUID target.
- Batch maintenance is an internal advisory-lock-protected tick, not free-form queue entrypoints.
- Phase 0 is inline-only and uses the installed SDK's asynchronous batch client.

## Coverage Summary

- **Requirements traced**: 10/10
- **Tests mapped**: 10/10
- **Evidence collected**: pending final validation
- **Deferred items**: post-persist ingestion filter rollout, persist-first YouTube/caption rollout, provider file-mode lifecycle
