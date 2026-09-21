# Tasks: agent-runtime-correctness

Sizes follow the plan-feature Task Sizing Reference. No task is XL; the single L (3.4) is
kept because splitting the conductor resume across two tasks would leave neither compilable.

## 1. Contracts and operation types

- [ ] 1.1 Write contract tests for the two new operation types — enum parity across `src/models/jobs.py`, `src/contracts/workflow_models.py`, and the three copies in `openapi/v1.yaml`; `LEGACY_OPERATION_TYPES["execute_agent_task"]` maps to `agent_task.execute` (S)
  **Spec scenarios**: agentic-operations.1 (submission returns durable handle), agentic-operations.3 (agent task operations project their resource)
  **Contracts**: contracts/openapi/v1.yaml
  **Design decisions**: D1, D2
  **Dependencies**: None
  **Files**: tests/contract/test_canonical_workflow_contracts.py

- [ ] 1.2 Add `AGENT_TASK_EXECUTE` and `APPROVAL_WAIT` to `OperationType`, the canonical contract, and regenerate models with `make workflow-contracts` (S)
  **Dependencies**: 1.1
  **Files**: src/models/jobs.py, openspec/contracts/content-workflows/openapi/v1.yaml, src/contracts/workflow_models.py, web/src/generated/workflow-contracts.ts

- [ ] 1.3 Add `AgentTaskSubmission`, `ApprovalRequestResponse`, and `ApprovalRequestPage` schemas plus the `/api/v1/agent/task` (202 OperationHandle) and `/api/v1/agent/approvals` paths to the canonical contract (S)
  **Dependencies**: 1.2
  **Files**: openspec/contracts/content-workflows/openapi/v1.yaml, src/contracts/workflow_models.py

- [ ] Checkpoint: run `make workflow-contracts-check` and `pytest tests/contract -m contract --no-cov`, review diff, verify scope

## 2. Defer-until-event

- [ ] 2.1 Write queue tests for waiting parents — parent deferred with `wait_on="children_terminal"` is not claimable before its child is terminal; child completion, failure, and cancellation each reset `execute_after` and notify; `claim_generation` unchanged; fallback re-poll after `operation_wait_fallback_seconds`; `wake()` on a non-waiting operation is a no-op (M)
  **Spec scenarios**: agentic-operations.4 (parent waits on children), agentic-operations.5 (child terminal wakes parent), agentic-operations.6 (external event wakes), agentic-operations.7 (lost wake recovered), agentic-operations.8 (cancel cascades)
  **Design decisions**: D3
  **Dependencies**: None
  **Files**: tests/queue/test_operation_wait.py

- [ ] 2.2 Extend `OperationService.defer` with `wait_on` and add `OperationService.wake`; add `operation_wait_fallback_seconds` setting (S)
  **Dependencies**: 2.1
  **Files**: src/services/operation_service.py, src/config/settings.py

- [ ] 2.3 Add `_wake_waiting_parent` to `src/queue/setup.py` and call it inside every child terminal transition (complete, fail, cancel), leaving the `summarization.run` batch reset in place (M)
  **Dependencies**: 2.1
  **Files**: src/queue/setup.py

- [ ] Checkpoint: run `pytest tests/queue -v`, review diff, verify scope

## 3. Agent task and approval operations

- [ ] 3.1 Write workflow tests for `AgentTaskWorkflow` — normalized input, derived idempotency key returns the existing operation, resource projection, legacy entrypoint projection (M)
  **Spec scenarios**: agentic-analysis.9 (user submits research task), agentic-analysis.10 (repeated submission idempotent), agentic-operations.3
  **Contracts**: contracts/openapi/v1.yaml
  **Design decisions**: D1
  **Dependencies**: 1.2
  **Files**: tests/workflows/test_agent_task_workflow.py

- [ ] 3.2 Write workflow tests for `ApprovalWaitWorkflow` — pending parks with `wait_on="external_event"`, approved and denied both complete with a decision result, infrastructure error fails (S)
  **Spec scenarios**: agentic-analysis.7 (blocking creates durable approval), agent-db-integration.5 (approve wakes child)
  **Design decisions**: D2, D3
  **Dependencies**: 2.2
  **Files**: tests/workflows/test_approval_wait_workflow.py

- [ ] 3.3 Write conductor tests for checkpoint resume — block returns deferred result with plan, index, partial results, cost, tokens, approval operation ID; resume at index restores partial results without re-planning; denial re-plans once then fails on repeat block; `delegate.*` risk resolution and persona override lowering (M)
  **Spec scenarios**: agentic-analysis.6 (risk classification), agentic-analysis.12 (task requires human approval), agentic-analysis.13 (cost accumulated)
  **Design decisions**: D4, D5, D9
  **Dependencies**: None
  **Files**: tests/agents/test_conductor.py, tests/agents/approval/test_gates.py

- [ ] 3.4 Implement `AgentTaskWorkflow` and `ApprovalWaitWorkflow` in `src/workflows/agent_task.py`, register both in `build_workflow_handler_registry`, and refactor `Conductor.execute` to accept and return checkpoints (L, kept whole: the workflow and the conductor checkpoint contract are one compilable unit)
  **Dependencies**: 3.1, 3.2, 3.3, 2.2
  **Files**: src/workflows/agent_task.py, src/queue/workflow_handlers.py, src/agents/conductor.py

- [ ] 3.5 Add `delegate.*` keys to `settings/approval.yaml` and build the gate from configuration in the workflow (S)
  **Dependencies**: 3.3
  **Files**: settings/approval.yaml, src/agents/approval/gates.py, src/workflows/agent_task.py

- [ ] 3.6 Delete the legacy `execute_agent_task` handler from the worker (S)
  **Dependencies**: 3.4
  **Files**: src/queue/worker.py

- [ ] Checkpoint: run `pytest tests/workflows tests/agents -v`, review diff, verify scope

## 4. Approvals service and routes

- [ ] 4.1 Write service and route tests — `create_request` inserts pending with `operation_id`; `decide_request` on non-pending raises; `list_requests` keyset paging; `POST /task` returns 202 `OperationHandle` and never enqueues `execute_agent_task`; `GET /approvals`; `POST /approval/{id}` wakes the child and returns 409 on a decided request (M)
  **Spec scenarios**: agent-db-integration.1 through agent-db-integration.7
  **Contracts**: contracts/openapi/v1.yaml, contracts/db/schema.sql
  **Design decisions**: D1, D10
  **Dependencies**: 1.3
  **Files**: tests/agents/test_api_routes.py, tests/agents/test_approval_service.py

- [ ] 4.2 Add `ApprovalService.create_request`, `list_requests`, and `ApprovalAlreadyDecidedError`; add the `operation_id` column migration for `approval_requests` (S)
  **Dependencies**: 4.1
  **Files**: src/services/agent_service.py, src/models/approval_request.py, alembic/versions/<rev>_approval_request_operation_id.py

- [ ] 4.3 Rewrite task submission to call `OperationService.submit`, add `GET /approvals`, and make the decision route wake the child and return 409 on conflict (M)
  **Dependencies**: 4.2, 2.2
  **Files**: src/api/agent_routes.py, src/agents/scheduler/scheduler.py, src/cli/agent_commands.py

- [ ] Checkpoint: run `pytest tests/agents tests/api/test_agent* -v`, review diff, verify scope

## 5. Memory infrastructure

- [ ] 5.1 Write async session tests — factory is a lazy singleton, rewrites the driver to asyncpg, sessions round-trip against the test database; assert no importer outside `src/agents/memory/` (S)
  **Design decisions**: D6
  **Dependencies**: None
  **Files**: tests/test_storage/test_async_session.py

- [ ] 5.2 Implement `src/storage/async_session.py` (S)
  **Dependencies**: 5.1
  **Files**: src/storage/async_session.py

- [ ] 5.3 Write memory factory tests — default weights, missing backend omitted with warning, dimension mismatch disables vector, graph built only when weighted and configured, embedding adapter exposes `embed` and `embed_query` (M)
  **Spec scenarios**: agentic-analysis.2 (strategies built from settings), agentic-analysis.3 (vector validates dimension)
  **Design decisions**: D7
  **Dependencies**: None
  **Files**: tests/agents/memory/test_factory.py

- [ ] 5.4 Implement `build_memory_strategies`, the embedding adapter, `GraphitiMemoryAdapter`, and the `query_embed_fn` option on `VectorStrategy`; add `agent_memory_strategies` and `agent_memory_embedding_dimensions` settings (M)
  **Dependencies**: 5.2, 5.3
  **Files**: src/agents/memory/factory.py, src/agents/memory/strategies/vector.py, src/agents/memory/strategies/graph.py, src/config/settings.py

- [ ] 5.5 Write migration test — column dimension follows `AGENT_MEMORY_EMBEDDING_DIMENSIONS`, HNSW index rebuilt, nulled row count logged, downgrade restores 1536 (S)
  **Design decisions**: D7
  **Dependencies**: None
  **Files**: tests/integration/test_agent_memory_migration.py

- [ ] 5.6 Write the embedding alignment migration (S)
  **Dependencies**: 5.5
  **Files**: alembic/versions/<rev>_align_agent_memory_embedding.py

- [ ] Checkpoint: run `pytest tests/agents/memory tests/test_storage -v`, review diff, verify scope

## 6. Store outcome

- [ ] 6.1 Write provider tests — `stored`, `partial`, `failed`, skipped strategies under an open circuit, same ID across strategies, telemetry status recorded (S)
  **Spec scenarios**: agentic-analysis.4 (partial store reported), agentic-analysis.5 (store fails on every strategy)
  **Design decisions**: D8
  **Dependencies**: None
  **Files**: tests/agents/memory/test_provider.py

- [ ] 6.2 Implement `MemoryStoreOutcome` and update the two internal callers (S)
  **Dependencies**: 6.1
  **Files**: src/agents/memory/provider.py, src/agents/memory/models.py, src/agents/conductor.py, src/telemetry/agent_metrics.py

## 7. Cost accounting

- [ ] 7.1 Write cost tests — each specialist sets `metadata["cost"]`; conductor sums `cost` and `cost_usd`; `LLMRouter._estimate_cost` matches `ModelConfig.calculate_cost` for every registry model and overestimates unknown models (S)
  **Spec scenarios**: agentic-analysis.13
  **Design decisions**: D9
  **Dependencies**: None
  **Files**: tests/agents/test_specialists_cost.py, tests/services/test_llm_router_cost.py

- [ ] 7.2 Populate `cost` in specialist metadata and delegate router estimation to the registry, removing the hardcoded table (S)
  **Dependencies**: 7.1
  **Files**: src/agents/specialists/base.py, src/services/llm_router.py

- [ ] Checkpoint: run `pytest tests/agents tests/services/test_llm_router_cost.py -v`, review diff, verify scope

## 8. Integration and documentation

- [ ] 8.1 Write an end-to-end test — submit a task whose persona forces `delegate.ingestion` to HIGH, observe `blocked` and a pending approval, approve via the route, observe resume and completion with non-zero `cost_total` and a stored memory (M)
  **Spec scenarios**: agentic-analysis.12, agent-db-integration.5, agentic-operations.5
  **Dependencies**: 3.4, 4.3, 5.4, 6.2, 7.2
  **Files**: tests/integration/test_agent_approval_resume.py

- [ ] 8.2 Update `docs/ACA-AGENTS.md` (task lifecycle, approvals, memory configuration) and `docs/GOTCHAS.md` (defer-until-event, embedding dimension) (S)
  **Dependencies**: 8.1
  **Files**: docs/ACA-AGENTS.md, docs/GOTCHAS.md

- [ ] 8.3 Run the full suite and the workflow-contract drift check (S)
  **Dependencies**: 8.2
  **Files**: none
