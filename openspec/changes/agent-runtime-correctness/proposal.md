# Change: agent-runtime-correctness

## Why

The durable agent-task path (`execute_agent_task` in `src/queue/worker.py`) cannot complete a
single task today, and the two subsystems that make agent runs durable across sessions are
inert. A design review of the agent-facing surfaces against the enterprise memory-platform
specification (see the session log) surfaced the following, each verified against the code on
2026-09-05:

1. **Every durable agent task fails before reaching the conductor.** `worker.py:1438` calls
   `ApprovalGate()` with no arguments, but `base_config` is a required positional. The
   `TypeError` is caught by the generic handler and the task is marked `failed` with
   "Failed due to an internal error".
2. **Agent memory is permanently inert.** The same block constructs `MemoryProvider(strategies={})`,
   so `Conductor._query_memory` always returns `[]` and `_store_insights` writes nowhere. The
   `VectorStrategy` and `KeywordStrategy` classes require an async SQLAlchemy session factory
   that does not exist anywhere in `src/`, `GraphStrategy` calls an `add_episode` method the
   `GraphitiClient` does not expose, and the `agent_memories.embedding` column is `vector(1536)`
   while the default embedding model produces 384 dimensions.
3. **`MemoryProvider.store` reports success on partial writes.** It returns the first ID
   produced and continues when other strategies fail, so a caller cannot tell that only one of
   three backends holds the record.
4. **Approvals have no producer and a lossy resume.** The conductor returns `BLOCKED` but
   nothing ever inserts an `ApprovalRequest` row (`grep "ApprovalRequest("` finds only the class
   definition), so the `POST /approval/{id}` route decides requests that never exist. The action
   names the conductor synthesizes (`delegate.<specialist>`) never appear in
   `settings/approval.yaml`, so risk resolution always falls through to `MEDIUM` and the block
   path is unreachable. When a request is approved, the re-enqueue payload carries only
   `task_id`, so a resumed task runs as an empty-prompt, default-persona `research` task.
5. **`agent_tasks.cost_total` is always zero.** Specialists emit `tokens_used` but never `cost`;
   the summarizer emits `cost_usd`, which the conductor does not read; and
   `LLMRouter._estimate_cost` carries a hardcoded pricing table that diverges from
   `settings/models.yaml` (for example Haiku 4.5 at 0.25/1.25 instead of 1.00/5.00).

These are correctness defects, not design gaps, and they gate the retrieval-surface work in the
companion change `agent-ergonomic-retrieval-surface` (insight maturity needs memory to run, and
pipeline cost estimation needs a single pricing source).

## What Changes

- **Worker conductor construction**: build `ApprovalGate` from `settings/approval.yaml` plus
  persona overrides, and build `MemoryProvider` from a new settings-driven factory.
- **Async database session infrastructure**: add `create_async_engine` and `async_sessionmaker`
  wiring in `src/storage/` (asyncpg is already a dependency), exposed as
  `get_async_session_factory()`.
- **Memory strategy factory**: `build_memory_strategies(settings) -> dict[str, tuple[MemoryStrategy, float]]`
  reading new `agent_memory_strategies` weights (default keyword 0.6, vector 0.4, graph 0.0),
  adapting the existing `EmbeddingProvider` to the `embed_fn` shape, and skipping strategies whose
  backends are not configured. A `GraphitiClient` adapter provides `add_episode`.
- **Embedding dimension alignment**: a migration that rebuilds `agent_memories.embedding` at the
  dimension of the configured embedding model, with the dimension recorded in a new
  `embedding_dimensions` column-comment and validated at factory time.
- **Partial-write reporting**: `MemoryProvider.store` returns a `MemoryStoreOutcome` with the
  memory ID, per-strategy outcomes, and a `status` of `stored`, `partial`, or `failed`. Callers
  that only want the ID use `.memory_id`. **BREAKING** for the two internal callers of `store`.
- **Approvals end to end**:
  - `ApprovalService.create_request(task_id, action, risk_level, context)`;
  - the conductor persists an `ApprovalRequest` on block and stores a resume checkpoint
    (plan, completed sub-task index, partial results) in `agent_tasks.result`;
  - `settings/approval.yaml` gains `delegate.research|analysis|synthesis|ingestion` keys, and
    the conductor resolves risk from the specialist's declared tool set rather than an
    unmatched synthetic name;
  - approval re-enqueue carries the full original payload and the conductor resumes from the
    checkpoint instead of replanning;
  - `GET /api/v1/agent/approvals?status=pending` lists pending requests; deciding a non-pending
    request returns 409 instead of a 200 that looks like success.
- **Cost accounting**: specialists populate `metadata["cost"]` via `BaseAgent.calculate_cost`;
  the conductor accepts `cost` and `cost_usd`; `LLMRouter._estimate_cost` delegates to
  `ModelConfig.calculate_cost` and the hardcoded table is removed.

## Approaches Considered

### Approach 1: Fix in place, additive infrastructure

Description: Keep the existing `MemoryProvider`, strategy classes, `ApprovalGate`, and
`ApprovalService` shapes. Add the missing async engine, factory, `create_request`, checkpoint,
and cost plumbing around them.

Pros:
- Smallest diff that makes every listed defect observable in a test and then green.
- Preserves the `agentic-analysis` and `agent-db-integration` spec contracts; deltas are
  MODIFIED, not REMOVED.
- Async engine is reusable by the companion change's cursor search.

Cons:
- Two session stacks (sync `get_db`, async factory) coexist; discipline needed to keep the
  async stack confined to memory strategies until a later consolidation.
- Conductor resume is checkpoint-in-JSONB, not a durable child operation.

Effort: M

### Approach 2: Rewrite memory strategies on the sync session stack

Description: Convert `VectorStrategy` and `KeywordStrategy` to the existing `with get_db()`
pattern wrapped in `run_in_executor`, avoiding any new engine.

Pros:
- No new infrastructure; one session stack.

Cons:
- Blocks the worker event loop under load and contradicts the strategies' documented design.
- Rejected explicitly in discovery (user chose the async engine).

Effort: M

### Approach 3: Model approvals as durable child operations

Description: Introduce an `approval.wait` operation type; the conductor submits it via
`OperationService.submit_child` and the task workflow defers on a checkpoint the way
`pipeline.run` defers on ingestion children. Approval resumes the parent through the queue.

Pros:
- Aligns approvals with the canonical durable-operation model; cancellation, retry, and events
  come for free.
- Removes the ad-hoc re-enqueue in `agent_routes.py`.

Cons:
- `execute_agent_task` is a legacy handler outside the v2 workflow registry; moving it is a
  larger refactor than this change should carry.
- Adds an operation type to the closed `OperationHandle.operation_type` enum in the canonical
  contract, which touches five active changes' shared file.

Effort: L

### Recommended

Approach 1. It closes every verified defect with MODIFIED spec deltas only, reuses the
components that already exist, and creates the async session infrastructure the companion
change needs for cursor-based search. Approach 3 is the right long-term home for approvals but
it drags a legacy handler into the v2 registry and the shared contract file; that should be its
own change once `execute_agent_task` is migrated.

### Selected Approach

Approach 3 selected at Gate 1 on 2026-09-05, with one addition requested after the detail
review: a **defer-until-event** queue mechanism. `OperationService.defer` today re-queues a
deferred parent with `execute_after = NOW() + 1 second`, so a parent waiting on a human approval
would re-poll once per second for the whole wait. The selected approach therefore:

1. registers `execute_agent_task` as `OperationType.AGENT_TASK_EXECUTE` in the v2 workflow
   registry, so agent tasks gain idempotency, cancellation, the operations list, and SSE events;
2. models an approval as an `approval.wait` child operation submitted with
   `OperationService.submit_child`; the parent defers on a checkpoint the way `pipeline.run`
   defers on ingestion children;
3. adds `defer(..., until="child_terminal")`, which parks the parent with a far `execute_after`
   and a `wait_on_children` marker, and a child-terminal hook that resets the parent's
   `execute_after` to `NOW()` and issues `pg_notify`, so the parent wakes once when a child
   reaches a terminal state rather than polling;
4. keeps everything from Approach 1 that is independent of approvals: the async engine, memory
   factory, embedding alignment, partial-write reporting, and cost accounting.

The `POST /api/v1/agent/approval/{id}` route becomes a decision on the `approval.wait` child
(completing or failing it), and the ad-hoc re-enqueue in `agent_routes.py` is removed.
Approach 1 remains recorded above as the fallback if the defer-until-event hook proves
unworkable in the queue's fencing model; Approach 2 was rejected in discovery.

## Impact

Affected specs (MODIFIED):
- `agentic-analysis`: Memory Provider, Approval Gates, Conductor Agent
- `agent-db-integration`: ApprovalService, API Routes

Affected code:
- `src/queue/worker.py` (conductor construction, re-enqueue payload)
- `src/storage/database.py` (async engine), new `src/storage/async_session.py`
- `src/agents/memory/provider.py`, `src/agents/memory/factory.py` (new), `src/agents/memory/strategies/*`
- `src/agents/conductor.py`, `src/agents/approval/gates.py`, `src/agents/specialists/base.py`
- `src/services/agent_service.py`, `src/api/agent_routes.py`
- `src/services/llm_router.py`, `src/config/settings.py`, `settings/approval.yaml`
- `alembic/versions/<new>_align_agent_memory_embedding.py`
- `docs/ACA-AGENTS.md`

Not affected: the canonical `openspec/contracts/content-workflows/openapi/v1.yaml`. The agent
routes are FastAPI-only today and remain so in this change.
