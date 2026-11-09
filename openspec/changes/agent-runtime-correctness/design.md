# Design: agent-runtime-correctness

## Context

The agent runtime has three layers that were built to the `agentic-analysis` and
`agent-db-integration` specs but never wired together in the durable worker path:

- `execute_agent_task` (`src/queue/worker.py:1411`) is a legacy string-registered handler,
  outside the v2 `WorkflowHandlerRegistry`. Agent tasks therefore have no `OperationHandle`,
  no idempotency key, no cancellation through the operations API, and no SSE events.
- The handler constructs `ApprovalGate()` without its required `base_config` and
  `MemoryProvider(strategies={})`, so every task fails before the conductor runs, and memory
  would be inert even if it did not.
- The conductor's `BLOCKED` return is a bare return: no `ApprovalRequest` row is written, the
  synthesized `delegate.<specialist>` action never matches `settings/approval.yaml`, and the
  approve route re-enqueues with only `task_id`, dropping prompt, type, and persona.

The queue already has the primitives this design needs. `OperationService.defer` checkpoints
a parent and releases it with `execute_after = NOW() + 1 second`; `submit_child` recovers
terminal children by idempotency key; and `_reconcile_batch_parent_status` in
`src/queue/setup.py` already resets a parent's `execute_after` to `NOW()` when its children go
terminal, but only for `summarization.run` batch parents. This design generalizes that reset.

Memory strategies require an async SQLAlchemy session factory, and `sqlalchemy.ext.asyncio` is
imported nowhere else in `src/`. `asyncpg` is already a dependency (the queue uses it directly).

## Goals / Non-Goals

Goals:
- Every durable agent task runs through the v2 registry as `agent_task.execute` and returns an
  `OperationHandle`.
- An approval is an `approval.wait` child operation; the parent waits without polling and
  resumes from a checkpoint with prior sub-task results intact.
- Memory strategies are built from settings and actually persist and recall.
- Partial memory writes are reported, not hidden.
- `agent_tasks.cost_total` reflects real spend, computed from one pricing source.

Non-Goals:
- Approval expiry sweeps (`ApprovalStatus.EXPIRED` stays defined but unused).
- Notification delivery on approval requests (the `notification-events` capability owns that).
- Migrating the sync `get_db` session stack; the async factory is confined to memory strategies.
- Changing recall ranking (recency and frequency weighting stays per the current spec; the
  companion change adds a maturity filter only).
- Any retrieval-surface change; see `agent-ergonomic-retrieval-surface`.

## Decisions

### D1: `agent_task.execute` is a canonical operation type

`OperationType.AGENT_TASK_EXECUTE = "agent_task.execute"` is added to `src/models/jobs.py`,
the three enum copies in `openspec/contracts/content-workflows/openapi/v1.yaml`, and the
generated models. `LEGACY_OPERATION_TYPES["execute_agent_task"]` maps the old entrypoint so
in-flight jobs on deploy are still projected. A new `src/workflows/agent_task.py` holds
`AgentTaskWorkflow`, registered in `build_workflow_handler_registry` with
`resource_type="agent_task"`. The normalized input is
`{task_id, prompt, task_type, persona, params}`; the derived idempotency key therefore makes a
repeated submission of the same prompt under the same persona return the existing operation.
`POST /api/v1/agent/task` returns `202 OperationHandle` whose `resource` is
`{type: "agent_task", id: <uuid>, url: /api/v1/agent/task/<uuid>}`. The legacy
`@register_handler("execute_agent_task")` block is deleted.

### D2: `approval.wait` is a child operation with a decision, not a failure

`OperationType.APPROVAL_WAIT = "approval.wait"`, input
`{task_id, approval_request_id, action, risk_level, context}`. Its handler reads the
`ApprovalRequest` row: `pending` parks the child with D3's external-event wait; `approved`
completes it with `result={"decision": "approved"}`; `denied` completes it with
`result={"decision": "denied", "reason": ...}`. Denial is a valid outcome, so the child never
fails on a human "no"; only an infrastructure error fails it. The child's `resource` is
`{type: "approval_request", id: <uuid>, url: /api/v1/agent/approvals/<uuid>}`.

### D3: Defer-until-event generalizes the existing batch reset

`OperationService.defer` gains `wait_on: Literal["children_terminal", "external_event"] | None`.
When set, the parent is released with `payload.wait_on = <value>` and
`execute_after = NOW() + settings.operation_wait_fallback_seconds` (default 3600) as a
lost-wake safety net. Two wake paths:

- `_wake_waiting_parent(conn, child_job_id)` runs inside the same transaction as any child
  terminal transition (complete, fail, cancel) in `src/queue/setup.py`. If the parent's
  `payload->>'wait_on' = 'children_terminal'`, it sets `execute_after = NOW()`, clears
  `wait_on`, and issues `pg_notify('pgqueuer', <entrypoint>)`. The existing
  `summarization.run` special case in `_reconcile_batch_parent_status` is left in place and
  covered by the same test module so the two paths cannot diverge.
- `OperationService.wake(operation_id)` does the same for `wait_on = 'external_event'`; the
  approval decision route calls it on the `approval.wait` child after updating the row.

Fencing is preserved: a wake only touches rows with `status = 'queued'` and never changes
`claim_generation`, so a stale worker cannot resume a parent that another claim has taken.

### D4: The conductor checkpoints into the operation, not into `agent_tasks.result`

`Conductor.execute` accepts an optional `checkpoint` and returns `ConductorResult` with a new
`deferred: bool` and `checkpoint: dict`. On block it returns
`{stage: "awaiting_approval", plan, next_index, partial_results, cost_total, tokens_total,
approval_operation_id}`. `AgentTaskWorkflow` submits the `approval.wait` child with idempotency
key `agent_task:<op>:approval:<index>:<action>`, sets `agent_tasks.status = blocked`, and
defers with `wait_on="children_terminal"`. On resume it reads the child result: approved
continues at `next_index` with `partial_results` restored; denied re-plans once with the
reason appended to the prompt context, then fails the task if the new plan blocks again on the
same action. `agent_tasks.result` keeps only the final result.

### D5: Approval actions are named after what the specialist will do

`settings/approval.yaml` gains explicit `delegate.research`, `delegate.analysis`,
`delegate.synthesis`, and `delegate.ingestion` keys (low, low, medium, high). The conductor
keeps the `delegate.<specialist>` name, so persona `approval_overrides` continue to work, and
`ApprovalGate.get_risk_level` is unchanged. The worker builds the gate from
`load_approval_config()` plus the persona's overrides instead of `ApprovalGate()`.

### D6: One async engine, confined to memory strategies

`src/storage/async_session.py` exposes `get_async_session_factory()`: a lazy singleton
`async_sessionmaker` over `create_async_engine` built from `settings.database_url` with the
driver rewritten to `postgresql+asyncpg`, `pool_size=2`, `expire_on_commit=False`. It is used
only by `KeywordStrategy` and `VectorStrategy`. Tests use the same factory against the test
database.

### D7: Memory strategies are built from settings and validated at startup

`settings.agent_memory_strategies: dict[str, float]` (default `{"keyword": 0.6, "vector": 0.4}`)
and `settings.agent_memory_embedding_dimensions: int` (default 384, matching the default
`all-MiniLM-L6-v2` model). `build_memory_strategies(settings)` in
`src/agents/memory/factory.py`:
- always builds `KeywordStrategy` when weighted;
- builds `VectorStrategy` with an adapter over `get_embedding_provider()` that exposes
  `embed(text)` and `embed_query(text)`; `VectorStrategy` gains an optional `query_embed_fn`;
- queries `atttypmod` on `agent_memories.embedding` and disables the vector strategy with a
  warning if the column dimension differs from the provider's;
- builds `GraphStrategy` only when weighted above zero and a graph provider is configured,
  through a `GraphitiMemoryAdapter` that maps `add_episode` onto
  `GraphitiClient.add_content_summary` with a `memory:` episode prefix.
The migration `ALTER COLUMN embedding TYPE vector(<N>)` interpolates `N` from
`AGENT_MEMORY_EMBEDDING_DIMENSIONS` at migration time, the pattern documented for pg_cron in
`docs/GOTCHAS.md`, and rebuilds the HNSW index. Existing rows are nulled because 1536-dim
vectors cannot be cast.

### D8: `store` returns an outcome

```python
@dataclass(frozen=True)
class MemoryStoreOutcome:
    memory_id: str
    status: Literal["stored", "partial", "failed"]
    strategies: dict[str, Literal["stored", "failed", "skipped"]]
```
`stored` requires every non-skipped strategy to succeed; `failed` means none did. The
conductor logs `partial` at warning with the strategy map and records it in telemetry via
`record_memory_operation(operation="store", success=..., status=...)`.

### D9: One pricing source

Specialists set `metadata["cost"] = self.calculate_cost()` after each generation. The
conductor sums `metadata.get("cost", metadata.get("cost_usd", 0.0))`.
`LLMRouter._estimate_cost` becomes an instance method that calls
`self.model_config.calculate_cost(model, input_tokens, output_tokens)` and falls back to the
registry's most expensive configured tier when the model is unknown, keeping the
"overestimate to protect the limit" intent without a second table.

### D10: Approvals API

`GET /api/v1/agent/approvals?status=pending|approved|denied&limit&cursor` returns
`{data, next_cursor}`. `POST /api/v1/agent/approval/{id}` on a non-pending request returns
`409` as an RFC 7807 problem instead of the current 200 echo. `ApprovalRequest` gains an
`operation_id` column referencing the `approval.wait` job so the row and the child can be
joined in both directions.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Keep re-enqueue on approval (Approach 1) | Owner chose the operation model; re-enqueue leaves agent tasks outside idempotency, cancel, list, and events. |
| Approval as a parent-side sleep loop with 1-second `defer` | Burns a claim per second for the whole human wait; D3 costs one wake hook and reuses an existing reset. |
| `LISTEN` on a dedicated `approval` channel in the worker | Adds a second notification channel; the queue already listens on `pgqueuer`, and a targeted `execute_after` reset plus notify is enough. |
| Strategies on the sync session via `run_in_executor` | Blocks the worker loop; rejected in discovery. |
| Fixed `vector(1536)` and force an OpenAI embedding model for memory | Couples memory to a paid provider; the default local model is 384-dim and the column should follow configuration. |
| Store the checkpoint in `agent_tasks.result` | Two sources of truth for resume; the operation checkpoint is what `pipeline.run` already uses and what `retry` restores. |

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| A wake is lost (notify dropped, worker down) | `operation_wait_fallback_seconds` re-poll; a test asserts the parent still resumes without notify. |
| Parent cancelled while child waits | Cancel cascade marks the `approval.wait` child `cancelled`; a decision on a cancelled request returns 409. |
| Contract enum change touches a file five active changes edit | `wp-contracts` runs first and holds the file lock; regeneration is via `make workflow-contracts`, never by hand. |
| Vector dimension migration nulls existing embeddings | Memory has been inert in the durable path, so no production rows exist; the migration logs the row count it nulls. |
| Two session stacks | The async factory is imported only under `src/agents/memory/`; a test asserts no other importer. |
| Denial re-plan loops | One re-plan per task; a second block on the same action fails the task with the denial reason. |

## Migration Plan

1. Land `wp-contracts` (enum + generated models) with `make workflow-contracts-check` green.
2. Deploy queue changes; `LEGACY_OPERATION_TYPES` keeps in-flight `execute_agent_task` jobs
   projectable, and the legacy handler is removed only after the registry handler is
   registered in the same release.
3. Run the alembic migration with `AGENT_MEMORY_EMBEDDING_DIMENSIONS` set to the deployed
   embedding model's size.
4. Rollback: the migration's `downgrade` restores `vector(1536)`; the enum addition is
   additive; reverting the worker restores the legacy handler.
