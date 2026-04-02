# Tasks: Agentic Analysis Agent

**Change ID**: `agentic-analysis-agent`
**Approach**: Layered Extension

## Phase 1: Foundation — Data Models & Memory Provider

*Priority: Must complete first — all other phases depend on these models and the memory abstraction.*

- [ ] 1.1 Write tests for agent data models — AgentTask, AgentInsight, AgentMemory, ApprovalRequest ORM models and enums
  **Spec scenarios**: agentic-analysis.1 (task lifecycle), agentic-analysis.9 (memory storage), agentic-analysis.13 (approval model)
  **Design decisions**: D8 (data model extensions)
  **Dependencies**: None

- [ ] 1.2 Create Alembic migration for agent tables — `agent_tasks`, `agent_insights`, `agent_memories`, `approval_requests`, `heartbeat_schedules` with all enums
  **Dependencies**: 1.1

- [ ] 1.3 Implement AgentTask, AgentInsight, AgentMemory, ApprovalRequest ORM models in `src/models/`
  **Dependencies**: 1.1, 1.2

- [ ] 1.4 Write tests for MemoryStrategy ABC and MemoryProvider composition — store, recall, forget, weighted RRF merging, graceful degradation
  **Spec scenarios**: agentic-analysis.9 (hybrid recall), agentic-analysis.10 (strategy configuration)
  **Design decisions**: D3 (memory provider with strategy pattern)
  **Dependencies**: 1.3

- [ ] 1.5 Implement MemoryStrategy ABC and MemoryEntry/MemoryFilter models in `src/agents/memory/`
  **Dependencies**: 1.4

- [ ] 1.6 Write tests for VectorStrategy — storage with embedding, cosine similarity recall, recency weighting
  **Spec scenarios**: agentic-analysis.9 (vector recall)
  **Design decisions**: D3 (vector strategy uses pgvector)
  **Dependencies**: 1.5

- [ ] 1.7 Implement VectorStrategy wrapping existing pgvector/embedding infrastructure
  **Dependencies**: 1.6

- [ ] 1.8 Write tests for KeywordStrategy — BM25 storage/recall, precise term matching
  **Spec scenarios**: agentic-analysis.9 (keyword recall)
  **Design decisions**: D3 (keyword strategy uses PostgreSQL FTS)
  **Dependencies**: 1.5

- [ ] 1.9 Implement KeywordStrategy wrapping existing PostgreSQL FTS infrastructure
  **Dependencies**: 1.8

- [ ] 1.10 Write tests for GraphStrategy — entity-aware storage, relationship traversal recall
  **Spec scenarios**: agentic-analysis.9 (graph recall)
  **Design decisions**: D3 (graph strategy uses Graphiti)
  **Dependencies**: 1.5

- [ ] 1.11 Implement GraphStrategy wrapping GraphitiClient
  **Dependencies**: 1.10

- [ ] 1.12 Write tests for MemoryProvider composition — multi-strategy RRF fusion, configurable weights, graceful degradation
  **Spec scenarios**: agentic-analysis.9 (hybrid recall), agentic-analysis.10 (configuration)
  **Design decisions**: D3 (weighted RRF composition)
  **Dependencies**: 1.7, 1.9, 1.11

- [ ] 1.13 Implement MemoryProvider with configurable strategy composition
  **Dependencies**: 1.12

## Phase 2: LLMRouter Extensions

*Priority: Extends the core reasoning engine. Specialists depend on these capabilities.*

- [ ] 2.1 Write tests for LLMRouter reflection — enable_reflection flag, reflection prompt, loop continuation on issues
  **Spec scenarios**: agentic-analysis.18 (enhanced tool calling)
  **Design decisions**: D7 (LLMRouter extensions)
  **Dependencies**: 1.3 (needs AgentTask model for context)

- [ ] 2.2 Implement reflection support in `generate_with_tools()` — backward-compatible optional parameters
  **Dependencies**: 2.1

- [ ] 2.3 Write tests for LLMRouter planning — goal decomposition, step-by-step execution, plan revision, cost tracking
  **Spec scenarios**: agentic-analysis.19 (planning method)
  **Design decisions**: D7 (planning phase)
  **Dependencies**: 2.2

- [ ] 2.4 Implement `generate_with_planning()` method on LLMRouter
  **Dependencies**: 2.3

- [ ] 2.5 Write tests for memory context injection in tool loop — memory_context parameter, cost_limit abort
  **Spec scenarios**: agentic-analysis.18 (memory context, cost limit)
  **Design decisions**: D7 (memory hooks)
  **Dependencies**: 1.13 (needs MemoryProvider), 2.2

- [ ] 2.6 Implement memory context injection and cost_limit in `generate_with_tools()`
  **Dependencies**: 2.5

## Phase 3: Specialist Agents

*Priority: The domain-specific agents that perform actual work. Depend on memory provider and LLMRouter extensions.*

- [ ] 3.1 Write tests for BaseSpecialist ABC — execute interface, tool registration, capability declaration
  **Spec scenarios**: agentic-analysis.5-8 (all specialist scenarios)
  **Design decisions**: D2 (specialist agents as tool-equipped wrappers)
  **Dependencies**: 1.13, 2.4

- [ ] 3.2 Implement BaseSpecialist ABC in `src/agents/specialists/base.py`
  **Dependencies**: 3.1

- [ ] 3.3 Write tests for ResearchSpecialist — multi-step research, search + graph + web, structured findings, memory storage
  **Spec scenarios**: agentic-analysis.5 (deep investigation)
  **Design decisions**: D2 (research specialist tools)
  **Dependencies**: 3.2

- [ ] 3.4 Implement ResearchSpecialist wrapping HybridSearchService, GraphitiClient, and web search
  **Dependencies**: 3.3

- [ ] 3.5 Write tests for AnalysisSpecialist — theme detection, historical context, anomaly identification, trend classification
  **Spec scenarios**: agentic-analysis.6 (trend detection)
  **Design decisions**: D2 (analysis specialist tools)
  **Dependencies**: 3.2

- [ ] 3.6 Implement AnalysisSpecialist wrapping ThemeAnalyzer and HistoricalContextAnalyzer
  **Dependencies**: 3.5

- [ ] 3.7 Write tests for SynthesisSpecialist — insight generation, cross-theme connections, persona-aware formatting
  **Spec scenarios**: agentic-analysis.7 (insight generation)
  **Design decisions**: D2 (synthesis specialist tools)
  **Dependencies**: 3.2

- [ ] 3.8 Implement SynthesisSpecialist wrapping DigestCreator and insight generation
  **Dependencies**: 3.7

- [ ] 3.9 Write tests for IngestionSpecialist — source ingestion, approval integration, new content reporting
  **Spec scenarios**: agentic-analysis.8 (content acquisition)
  **Design decisions**: D2 (ingestion specialist tools)
  **Dependencies**: 3.2

- [ ] 3.10 Implement IngestionSpecialist wrapping ingestion orchestrator
  **Dependencies**: 3.9

- [ ] 3.11 Write tests for SpecialistRegistry — registration, lookup by capability, tool aggregation
  **Design decisions**: D2 (specialist registry)
  **Dependencies**: 3.4, 3.6, 3.8, 3.10

- [ ] 3.12 Implement SpecialistRegistry in `src/agents/registry.py`
  **Dependencies**: 3.11

## Phase 4: Approval Gates & Persona

*Priority: Cross-cutting concerns needed by conductor. Can be built in parallel with Phase 3.*

- [ ] 4.1 Write tests for approval gate system — risk classification, auto-approve, block-and-request, approval/denial flow
  **Spec scenarios**: agentic-analysis.3 (task requires approval), agentic-analysis.13 (risk classification)
  **Design decisions**: D5 (tiered approval gates)
  **Dependencies**: 1.3 (needs ApprovalRequest model)

- [ ] 4.2 Implement approval gate system in `src/agents/approval/gates.py`
  **Dependencies**: 4.1

- [ ] 4.3 Create `settings/approval.yaml` with default risk level configuration
  **Dependencies**: 4.2

- [ ] 4.4 Write tests for persona loader — YAML loading, ConfigRegistry integration, system prompt generation
  **Spec scenarios**: agentic-analysis.14 (persona loading and application)
  **Design decisions**: D6 (agent persona configuration)
  **Dependencies**: None

- [ ] 4.5 Implement persona loader in `src/agents/persona/loader.py`
  **Dependencies**: 4.4

- [ ] 4.6 Create `settings/persona.yaml` with default AI trend analyst persona
  **Dependencies**: 4.5

## Phase 5: Conductor Agent

*Priority: The orchestrating intelligence. Depends on specialists, memory, approval, and persona.*

- [ ] 5.1 Write tests for Conductor task lifecycle — received → planning → delegating → monitoring → synthesizing → completed
  **Spec scenarios**: agentic-analysis.1 (user task), agentic-analysis.2 (heartbeat task), agentic-analysis.4 (failure recovery)
  **Design decisions**: D1 (conductor as stateful task manager)
  **Dependencies**: 3.12 (specialist registry), 4.2 (approval gates), 4.5 (persona), 1.13 (memory)

- [ ] 5.2 Implement Conductor agent in `src/agents/conductor.py` — task state machine, planning, delegation, synthesis
  **Dependencies**: 5.1

- [ ] 5.3 Write tests for Conductor goal decomposition — complex task broken into specialist sub-tasks with dependencies
  **Spec scenarios**: agentic-analysis.1 (task decomposition)
  **Design decisions**: D1 (conductor plans and delegates)
  **Dependencies**: 5.2

- [ ] 5.4 Implement goal decomposition and sub-task management in Conductor
  **Dependencies**: 5.3

- [ ] 5.5 Write tests for Conductor synthesis — merging specialist results, generating insights, storing to DB
  **Spec scenarios**: agentic-analysis.1 (synthesize results), agentic-analysis.7 (insight generation)
  **Design decisions**: D1 (conductor synthesizes)
  **Dependencies**: 5.2

- [ ] 5.6 Implement result synthesis and insight storage in Conductor
  **Dependencies**: 5.5

- [ ] 5.7 Write integration test for end-to-end task flow — user submits task → conductor plans → specialists execute → results synthesized
  **Spec scenarios**: agentic-analysis.1 (full flow)
  **Design decisions**: D1 (full lifecycle)
  **Dependencies**: 5.6

## Phase 6: Heartbeat Scheduler

*Priority: Enables proactive behavior. Depends on conductor for task execution.*

- [ ] 6.1 Write tests for heartbeat scheduler — cron parsing, schedule matching, deduplication, PGQueuer integration
  **Spec scenarios**: agentic-analysis.11 (schedule execution), agentic-analysis.12 (schedule management)
  **Design decisions**: D4 (PGQueuer extension)
  **Dependencies**: 5.2 (conductor handles enqueued tasks)

- [ ] 6.2 Implement heartbeat scheduler in `src/agents/heartbeat/scheduler.py`
  **Dependencies**: 6.1

- [ ] 6.3 Create `settings/heartbeat.yaml` with default proactive task schedules
  **Dependencies**: 6.2

- [ ] 6.4 Write tests for proactive task definitions — scan_sources, trend_detection, weekly_synthesis, knowledge_maintenance, cross_theme_discovery
  **Spec scenarios**: agentic-analysis.2 (heartbeat triggers), agentic-analysis.11 (schedule execution)
  **Design decisions**: D4 (proactive tasks)
  **Dependencies**: 6.2

- [ ] 6.5 Implement proactive task definitions in `src/agents/heartbeat/tasks.py`
  **Dependencies**: 6.4

- [ ] 6.6 Integrate heartbeat with FastAPI lifespan (start/stop scheduler) and PGQueuer worker
  **Dependencies**: 6.5

## Phase 7: API & CLI

*Priority: User-facing interfaces. Depend on conductor and all supporting infrastructure.*

- [ ] 7.1 Write tests for agent API endpoints — task CRUD, insight listing, approval handling, schedule management
  **Spec scenarios**: agentic-analysis.15 (API endpoints), agentic-analysis.16 (SSE streaming)
  **Design decisions**: D8 (data models)
  **Dependencies**: 5.6, 6.5

- [ ] 7.2 Implement agent API routes in `src/api/agent_routes.py`
  **Dependencies**: 7.1

- [ ] 7.3 Write tests for SSE progress streaming — task status changes, specialist events, intermediate findings
  **Spec scenarios**: agentic-analysis.16 (SSE streaming)
  **Dependencies**: 7.2

- [ ] 7.4 Implement SSE progress streaming for agent tasks
  **Dependencies**: 7.3

- [ ] 7.5 Write tests for agent CLI commands — task submission, status, insights, schedule management, approval
  **Spec scenarios**: agentic-analysis.17 (CLI interface)
  **Dependencies**: 7.2

- [ ] 7.6 Implement agent CLI commands in `src/cli/agent_commands.py`
  **Dependencies**: 7.5

- [ ] 7.7 Register `agent_task` handler with PGQueuer worker
  **Dependencies**: 5.2, 7.2

## Phase 8: Integration & Polish

*Priority: End-to-end validation, documentation, and observability.*

- [ ] 8.1 Write end-to-end integration test — full flow from CLI task submission through conductor, specialists, memory, and back to CLI results
  **Spec scenarios**: All scenarios (end-to-end validation)
  **Dependencies**: 7.6

- [ ] 8.2 Write integration test for proactive heartbeat flow — scheduler triggers task → conductor executes → insights generated
  **Spec scenarios**: agentic-analysis.2, agentic-analysis.11
  **Dependencies**: 6.6, 7.2

- [ ] 8.3 Add OTel instrumentation — traces for agent tasks, spans for specialist invocations, metrics for task throughput and cost
  **Dependencies**: 5.2, 3.12

- [ ] 8.4 Add agent section to ARCHITECTURE.md documentation
  **Dependencies**: 8.1

- [ ] 8.5 Add agent commands to CLI help and CLAUDE.md
  **Dependencies**: 7.6

- [ ] 8.6 Write regression test — daily pipeline still works unchanged with agent layer present
  **Dependencies**: 8.1

## Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 1. Foundation | 1.1–1.13 | Data models + Memory provider |
| 2. LLMRouter | 2.1–2.6 | Reflection, planning, memory hooks |
| 3. Specialists | 3.1–3.12 | Four specialist agents + registry |
| 4. Approval & Persona | 4.1–4.6 | Cross-cutting concerns |
| 5. Conductor | 5.1–5.7 | Orchestrating intelligence |
| 6. Heartbeat | 6.1–6.6 | Proactive scheduling |
| 7. API & CLI | 7.1–7.7 | User-facing interfaces |
| 8. Integration | 8.1–8.6 | E2E tests, docs, observability |

**Total**: 50 tasks across 8 phases
**Estimated new files**: ~30
**Modified files**: ~5 (LLMRouter, worker, FastAPI app, ARCHITECTURE.md, CLAUDE.md)
