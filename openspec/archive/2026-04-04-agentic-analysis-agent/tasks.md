# Tasks: Agentic Analysis Agent

**Change ID**: `agentic-analysis-agent`
**Approach**: Layered Extension
**Last updated**: 2026-04-04 (retroactive update from implementation audit)

## Phase 1: Foundation — Data Models & Memory Provider ✅

*Priority: Must complete first — all other phases depend on these models and the memory abstraction.*
*Implemented in: `63627c0` feat(agents): Phase 1 — data models, enums, memory provider with RRF fusion*
*Tests: `tests/agents/test_agent_models.py` (31 tests), `tests/agents/memory/test_memory_models.py` (9), `tests/agents/memory/test_strategies.py` (14), `tests/agents/memory/test_provider.py` (12)*
*Note: Used VARCHAR columns instead of native PG enums — avoids the ALTER TYPE migration gotcha entirely.*

- [x] 1.0 Design and document PG enum migration strategy — define all new StrEnums (AgentTaskStatus, InsightType, MemoryType, RiskLevel) and corresponding `CREATE TYPE` + `ALTER TYPE ... ADD VALUE` migrations; document enum extension pattern in migration file comments
  **Spec scenarios**: agentic-analysis.20 (confidence scoring uses enums for classification)
  **Design decisions**: D8 (data model extensions)
  **Dependencies**: None
  **Gotcha**: PG enum + Python StrEnum mismatch — adding to StrEnum requires `ALTER TYPE ... ADD VALUE` migration (see CLAUDE.md gotchas)

- [x] 1.1 Write tests for agent data models — AgentTask, AgentInsight, AgentMemory, ApprovalRequest ORM models and enums
  **Spec scenarios**: agentic-analysis.1 (task lifecycle), agentic-analysis.9 (memory storage), agentic-analysis.13 (approval model)
  **Design decisions**: D8 (data model extensions)
  **Dependencies**: 1.0

- [x] 1.2 Create Alembic migration for agent tables — `agent_tasks`, `agent_insights`, `agent_memories`, `approval_requests`, `agent_schedules` with all enums
  **Dependencies**: 1.1

- [x] 1.3 Implement AgentTask, AgentInsight, AgentMemory, ApprovalRequest ORM models in `src/models/`
  **Dependencies**: 1.1, 1.2

- [x] 1.4 Write tests for MemoryStrategy ABC and MemoryProvider composition — store, recall, forget, weighted RRF merging, graceful degradation
  **Spec scenarios**: agentic-analysis.9 (hybrid recall), agentic-analysis.10 (strategy configuration)
  **Design decisions**: D3 (memory provider with strategy pattern)
  **Dependencies**: 1.3

- [x] 1.5 Implement MemoryStrategy ABC and MemoryEntry/MemoryFilter models in `src/agents/memory/`
  **Dependencies**: 1.4

- [x] 1.6 Write tests for VectorStrategy — storage with embedding, cosine similarity recall, recency weighting
  **Spec scenarios**: agentic-analysis.9 (vector recall)
  **Design decisions**: D3 (vector strategy uses pgvector)
  **Dependencies**: 1.5

- [x] 1.7 Implement VectorStrategy wrapping existing pgvector/embedding infrastructure
  **Dependencies**: 1.6

- [x] 1.8 Write tests for KeywordStrategy — BM25 storage/recall, precise term matching
  **Spec scenarios**: agentic-analysis.9 (keyword recall)
  **Design decisions**: D3 (keyword strategy uses PostgreSQL FTS)
  **Dependencies**: 1.5

- [x] 1.9 Implement KeywordStrategy wrapping existing PostgreSQL FTS infrastructure
  **Dependencies**: 1.8

- [x] 1.10 Write tests for GraphStrategy — entity-aware storage, relationship traversal recall
  **Spec scenarios**: agentic-analysis.9 (graph recall)
  **Design decisions**: D3 (graph strategy uses Graphiti)
  **Dependencies**: 1.5

- [x] 1.11 Implement GraphStrategy wrapping GraphitiClient
  **Dependencies**: 1.10

- [x] 1.12 Write tests for MemoryProvider composition — multi-strategy RRF fusion, configurable weights, graceful degradation
  **Spec scenarios**: agentic-analysis.9 (hybrid recall), agentic-analysis.10 (configuration)
  **Design decisions**: D3 (weighted RRF composition)
  **Dependencies**: 1.7, 1.9, 1.11

- [x] 1.13 Implement MemoryProvider with configurable strategy composition
  **Dependencies**: 1.12

## Phase 2: LLMRouter Extensions ✅

*Priority: Extends the core reasoning engine. Specialists depend on these capabilities.*
*Implemented in: `51716a0` feat(agents): Phase 2 — LLMRouter extensions for reflection, planning, memory, cost*
*Tests: `tests/agents/test_llm_router_extensions.py` (13 tests)*

- [x] 2.1 Write tests for LLMRouter reflection — enable_reflection flag, reflection prompt, loop continuation on issues
  **Spec scenarios**: agentic-analysis.18 (enhanced tool calling)
  **Design decisions**: D7 (LLMRouter extensions)
  **Dependencies**: 1.3 (needs AgentTask model for context)

- [x] 2.2 Implement reflection support in `generate_with_tools()` — backward-compatible optional parameters
  **Dependencies**: 2.1

- [x] 2.3 Write tests for LLMRouter planning — goal decomposition, step-by-step execution, plan revision, cost tracking
  **Spec scenarios**: agentic-analysis.19 (planning method)
  **Design decisions**: D7 (planning phase)
  **Dependencies**: 2.2

- [x] 2.4 Implement `generate_with_planning()` method on LLMRouter
  **Dependencies**: 2.3

- [x] 2.5 Write tests for memory context injection in tool loop — memory_context parameter, cost_limit abort
  **Spec scenarios**: agentic-analysis.18 (memory context, cost limit)
  **Design decisions**: D7 (memory hooks)
  **Dependencies**: 1.13 (needs MemoryProvider), 2.2

- [x] 2.6 Implement memory context injection and cost_limit in `generate_with_tools()`
  **Dependencies**: 2.5

## Phase 3: Specialist Agents ✅

*Priority: The domain-specific agents that perform actual work. Depend on memory provider and LLMRouter extensions.*
*Implemented in: `effbf6e` feat(agents): Phases 3+4 — specialist agents, approval gates, persona system*
*Tests: `tests/agents/specialists/test_base.py` (13 tests), `tests/agents/specialists/test_registry.py` (12 tests)*

- [x] 3.1 Write tests for BaseSpecialist ABC — execute interface, tool registration, capability declaration
  **Spec scenarios**: agentic-analysis.5-8 (all specialist scenarios)
  **Design decisions**: D2 (specialist agents as tool-equipped wrappers)
  **Dependencies**: 1.13, 2.4

- [x] 3.2 Implement BaseSpecialist ABC in `src/agents/specialists/base.py`
  **Dependencies**: 3.1

- [x] 3.3 Write tests for ResearchSpecialist — multi-step research, search + graph + web, structured findings, memory storage
  **Spec scenarios**: agentic-analysis.5 (deep investigation)
  **Design decisions**: D2 (research specialist tools)
  **Dependencies**: 3.2

- [x] 3.4 Implement ResearchSpecialist wrapping HybridSearchService, GraphitiClient, and web search
  **Dependencies**: 3.3

- [x] 3.5 Write tests for AnalysisSpecialist — theme detection, historical context, anomaly identification, trend classification
  **Spec scenarios**: agentic-analysis.6 (trend detection)
  **Design decisions**: D2 (analysis specialist tools)
  **Dependencies**: 3.2

- [x] 3.6 Implement AnalysisSpecialist wrapping ThemeAnalyzer and HistoricalContextAnalyzer
  **Dependencies**: 3.5

- [x] 3.7 Write tests for SynthesisSpecialist — insight generation, cross-theme connections, persona-aware formatting
  **Spec scenarios**: agentic-analysis.7 (insight generation)
  **Design decisions**: D2 (synthesis specialist tools)
  **Dependencies**: 3.2

- [x] 3.8 Implement SynthesisSpecialist wrapping DigestCreator and insight generation
  **Dependencies**: 3.7

- [x] 3.9 Write tests for IngestionSpecialist — source ingestion, approval integration, new content reporting
  **Spec scenarios**: agentic-analysis.8 (content acquisition)
  **Design decisions**: D2 (ingestion specialist tools)
  **Dependencies**: 3.2

- [x] 3.10 Implement IngestionSpecialist wrapping ingestion orchestrator
  **Dependencies**: 3.9

- [x] 3.11 Write tests for SpecialistRegistry — registration, lookup by capability, tool aggregation
  **Design decisions**: D2 (specialist registry)
  **Dependencies**: 3.4, 3.6, 3.8, 3.10

- [x] 3.12 Implement SpecialistRegistry in `src/agents/registry.py`
  **Dependencies**: 3.11

## Phase 4: Approval Gates & Persona ✅

*Priority: Cross-cutting concerns needed by conductor. Can be built in parallel with Phase 3.*
*Implemented in: `effbf6e` feat(agents): Phases 3+4 — specialist agents, approval gates, persona system*
*Tests: `tests/agents/approval/test_gates.py` (14 tests), `tests/agents/persona/test_models.py` (11), `tests/agents/persona/test_loader.py` (14)*

- [x] 4.1 Write tests for approval gate system — risk classification, auto-approve, block-and-request, approval/denial flow, per-persona overrides (lower only)
  **Spec scenarios**: agentic-analysis.3 (task requires approval), agentic-analysis.13 (risk classification with persona overrides)
  **Design decisions**: D5 (tiered approval gates)
  **Dependencies**: 1.3 (needs ApprovalRequest model)

- [x] 4.2 Implement approval gate system in `src/agents/approval/gates.py` — with persona override resolution
  **Dependencies**: 4.1

- [x] 4.3 Create `settings/approval.yaml` with default risk level configuration
  **Dependencies**: 4.2

- [x] 4.4 Write tests for PersonaConfig model — domain_focus, model_overrides, approval_overrides, restricted_tools, output_defaults, communication_style
  **Spec scenarios**: agentic-analysis.14 (multi-persona loading)
  **Design decisions**: D6 (multi-persona configuration)
  **Dependencies**: None

- [x] 4.5 Implement PersonaConfig, OutputDefaults, and related Pydantic models in `src/agents/persona/models.py`
  **Dependencies**: 4.4

- [x] 4.6 Write tests for PersonaLoader — YAML loading, default inheritance (deep merge), persona listing, resolve_model, filter_tools, resolve_output
  **Spec scenarios**: agentic-analysis.14 (multi-persona loading), agentic-analysis.14a (persona listing)
  **Design decisions**: D6 (inheritance from default, separation from schedule)
  **Dependencies**: 4.5

- [x] 4.7 Implement PersonaLoader in `src/agents/persona/loader.py` — with default.yaml inheritance
  **Dependencies**: 4.6

- [x] 4.8 Create `settings/personas/` directory with default.yaml, ai-ml-technology.yaml, and leadership.yaml personas
  **Dependencies**: 4.7

## Phase 5: Conductor Agent ✅

*Priority: The orchestrating intelligence. Depends on specialists, memory, approval, and persona.*
*Implemented in: `70b971c` feat(agents): implement conductor, scheduler, API routes, and CLI*
*Tests: `tests/agents/test_conductor.py` (30 tests — all mocked unit tests)*

- [x] 5.1 Write tests for Conductor task lifecycle — received → planning → delegating → monitoring → synthesizing → completed
  **Spec scenarios**: agentic-analysis.1 (user task), agentic-analysis.2 (scheduled task), agentic-analysis.4 (failure recovery)
  **Design decisions**: D1 (conductor as stateful task manager)
  **Dependencies**: 3.12 (specialist registry), 4.2 (approval gates), 4.5 (persona), 1.13 (memory)

- [x] 5.2 Implement Conductor agent core in `src/agents/conductor.py` — task state machine (received→planning→delegating→monitoring→completed/failed), persona loading, and basic task execution scaffold
  **Dependencies**: 5.1

- [x] 5.2a Implement Conductor delegation logic — specialist selection based on task type, tool filtering via persona, sub-task creation and monitoring
  **Dependencies**: 5.2

- [x] 5.3 Write tests for Conductor goal decomposition — complex task broken into specialist sub-tasks with dependencies
  **Spec scenarios**: agentic-analysis.1 (task decomposition)
  **Design decisions**: D1 (conductor plans and delegates)
  **Dependencies**: 5.2a

- [x] 5.4 Implement goal decomposition and sub-task management in Conductor
  **Dependencies**: 5.3

- [x] 5.5 Write tests for Conductor synthesis — merging specialist results, generating insights, storing to DB
  **Spec scenarios**: agentic-analysis.1 (synthesize results), agentic-analysis.7 (insight generation)
  **Design decisions**: D1 (conductor synthesizes)
  **Dependencies**: 5.2

- [x] 5.6 Implement result synthesis and insight storage in Conductor
  **Dependencies**: 5.5

- [x] 5.7 Write integration test for end-to-end task flow — user submits task → conductor plans → specialists execute → results synthesized
  **Spec scenarios**: agentic-analysis.1 (full flow)
  **Design decisions**: D1 (full lifecycle)
  **Dependencies**: 5.6
  **Done**: `tests/integration/test_agent_integration.py::TestEndToEndTaskFlow` (8 tests with real object composition)

## Phase 6: Scheduler ✅

*Priority: Enables proactive behavior. Depends on conductor for task execution.*
*Implemented in: `70b971c` feat(agents): implement conductor, scheduler, API routes, and CLI*
*Tests: `tests/agents/scheduler/test_scheduler.py` (28 tests)*

- [x] 6.1 Write tests for scheduler — cron parsing, schedule matching, deduplication, PGQueuer integration, persona/output/sources passed through to task
  **Spec scenarios**: agentic-analysis.11 (schedule execution), agentic-analysis.12 (schedule management), agentic-analysis.12a (source filtering)
  **Design decisions**: D4 (schedule-driven proactive tasks)
  **Dependencies**: 5.2 (conductor handles enqueued tasks), 4.7 (PersonaLoader)

- [x] 6.2 Implement scheduler in `src/agents/scheduler/scheduler.py` — reads schedule.yaml, enqueues with persona + output + sources
  **Dependencies**: 6.1

- [x] 6.3 Create `settings/schedule.yaml` with default proactive task schedules (infrastructure + persona-driven analysis + synthesis)
  **Dependencies**: 6.2

- [x] 6.4 Write tests for proactive task definitions — scan_sources, trend_detection (per-persona), weekly_synthesis (per-persona), knowledge_maintenance, cross_theme_discovery, source-filtered runs
  **Spec scenarios**: agentic-analysis.2 (scheduled triggers), agentic-analysis.11 (schedule execution), agentic-analysis.12a (source filtering)
  **Design decisions**: D4 (proactive tasks, persona separation)
  **Dependencies**: 6.2

- [x] 6.5 Implement proactive task definitions in `src/agents/scheduler/tasks.py`
  **Dependencies**: 6.4

- [x] 6.6 Integrate scheduler with FastAPI lifespan (start/stop) and PGQueuer worker
  **Dependencies**: 6.5

## Phase 7: API & CLI ✅

*Priority: User-facing interfaces. Depend on conductor and all supporting infrastructure.*
*Implemented in: `70b971c` (routes + CLI), `254a0fb` (wiring into main app)*
*Tests: `tests/agents/test_api_routes.py` (21 tests), `tests/agents/test_cli_commands.py` (18 tests)*
*Additional: `tests/security/test_agent_error_leakage.py` (1 test — from Sentinel PR #364)*

- [x] 7.1 Write tests for agent API endpoints — task CRUD, insight CRUD, approval handling, schedule listing, persona listing (all REST endpoints from agentic-analysis.15)
  **Spec scenarios**: agentic-analysis.15 (API endpoints)
  **Design decisions**: D8 (data models)
  **Dependencies**: 5.6, 6.5

- [x] 7.2 Implement agent API routes in `src/api/agent_routes.py`
  **Dependencies**: 7.1

- [x] 7.3 Write tests for SSE progress streaming — task status changes, specialist events, intermediate findings
  **Spec scenarios**: agentic-analysis.16 (SSE streaming)
  **Dependencies**: 7.2

- [x] 7.4 Implement SSE progress streaming for agent tasks
  **Dependencies**: 7.3

- [x] 7.5 Write tests for agent CLI commands — task submission, status, insights, schedule management, approval
  **Spec scenarios**: agentic-analysis.17 (CLI interface)
  **Dependencies**: 7.2

- [x] 7.6 Implement agent CLI commands in `src/cli/agent_commands.py`
  **Dependencies**: 7.5

- [x] 7.7 Register `agent_task` handler with PGQueuer worker
  **Dependencies**: 5.2, 7.2

## Phase 8: Integration & Polish ✅

*Priority: End-to-end validation, documentation, and observability.*
*Completed: 2026-04-04 — integration tests, OTel instrumentation, regression tests all added.*
*Tests: `tests/integration/test_agent_integration.py` (23 tests), `tests/test_telemetry/test_agent_metrics.py` (15 tests), `tests/regression/test_agent_regression.py` (11 tests)*

- [x] 8.1 Write end-to-end integration test — full flow from CLI task submission through conductor, specialists, memory, and back to CLI results
  **Spec scenarios**: All scenarios (end-to-end validation)
  **Dependencies**: 7.6
  **Done**: `tests/integration/test_agent_integration.py::TestEndToEndTaskFlow` — 8 tests with real Conductor→Registry→Specialists→MemoryProvider→ApprovalGate wiring (only LLM is faked)

- [x] 8.1a Write integration test for persona-parameterized task flow — same task prompt run with two different personas produces differently structured outputs (e.g., technical_report vs executive_briefing)
  **Spec scenarios**: agentic-analysis.14 (persona loading), agentic-analysis.20 (confidence scoring)
  **Dependencies**: 8.1
  **Done**: `TestPersonaParameterizedFlow` — 3 tests: different persona configs, approval overrides, model overrides

- [x] 8.1b Write integration test for error recovery flow — specialist failure → retry → partial result → parent task completes with `partial = true`
  **Spec scenarios**: agentic-analysis.4 (failure recovery), agentic-analysis.24 (specialist failure), agentic-analysis.23 (retry policy)
  **Dependencies**: 8.1
  **Done**: `TestErrorRecoveryFlow` — 3 tests: retry-then-succeed, all-retries-exhausted, exception-caught-and-retried

- [x] 8.1c Write integration test for approval gate flow — task hits HIGH action → blocks → user approves → task resumes and completes
  **Spec scenarios**: agentic-analysis.3 (approval flow), agentic-analysis.13 (risk classification)
  **Dependencies**: 8.1
  **Done**: `TestApprovalGateFlow` — 4 tests: HIGH blocks, LOW passes, escalation-ignored, CRITICAL blocks

- [x] 8.2 Write integration test for proactive scheduler flow — scheduler triggers task → conductor executes → insights generated
  **Spec scenarios**: agentic-analysis.2, agentic-analysis.11
  **Dependencies**: 6.6, 7.2
  **Done**: `TestProactiveSchedulerFlow` — 5 tests: tick-enqueues, disabled-skipped, dedup, persona-passthrough, full-scheduler-to-conductor

- [x] 8.3 Add OTel instrumentation — traces for agent tasks, spans for specialist invocations, metrics for task throughput and cost
  **Dependencies**: 5.2, 3.12
  **Done**: `src/telemetry/agent_metrics.py` — 8 metrics (task counter/duration, tokens, cost, specialist invocations/duration, memory ops, approval checks) + 4 trace context managers. Wired into `src/agents/conductor.py` at task completion, specialist delegation, memory ops, and approval checks. Tests: `tests/test_telemetry/test_agent_metrics.py` (15 tests)

- [x] 8.4 Add agent section to ARCHITECTURE.md documentation
  **Dependencies**: 8.1
  **Done**: `docs/ACA-AGENTS.md` created as standalone guide (commit `33be1a4`). Covers personas, schedules, approval gates, CLI, and best practices.

- [x] 8.5 Add agent commands to CLI help and CLAUDE.md
  **Dependencies**: 7.6
  **Done**: CLAUDE.md already includes `aca agent task`, `aca agent status`, `aca agent insights`, `aca agent personas`, `aca agent schedule` commands.

- [x] 8.6 Write regression test — daily pipeline still works unchanged with agent layer present
  **Dependencies**: 8.1
  **Done**: `tests/regression/test_agent_regression.py` — 11 tests: import safety, model coexistence, enum isolation, CLI/route registration, worker handler, persona/schedule/approval YAML parsing

## Summary

| Phase | Tasks | Status | Tests |
|-------|-------|--------|-------|
| 1. Foundation | 1.0–1.13 (14) | ✅ Complete | 66 unit tests across 4 files |
| 2. LLMRouter | 2.1–2.6 (6) | ✅ Complete | 13 unit tests |
| 3. Specialists | 3.1–3.12 (12) | ✅ Complete | 25 unit tests across 2 files |
| 4. Approval & Persona | 4.1–4.8 (8) | ✅ Complete | 39 unit tests across 3 files |
| 5. Conductor | 5.1–5.7 (8) | ✅ Complete | 30 unit + 8 integration tests |
| 6. Scheduler | 6.1–6.6 (6) | ✅ Complete | 28 unit + 5 integration tests |
| 7. API & CLI | 7.1–7.7 (7) | ✅ Complete | 39 unit + 1 security test |
| 8. Integration | 8.1–8.6 (9) | ✅ Complete | 23 integration + 15 OTel + 11 regression |

**Total**: 57 tasks — **57 complete** ✅
**Test total**: 240 unit + 49 integration/OTel/regression = **289 tests**
**Validation**: Smoke 17/17, spec compliance 22/22 (see validation-report.md)
