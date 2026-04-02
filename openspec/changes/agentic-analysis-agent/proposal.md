# Proposal: Agentic Analysis Agent

**Change ID**: `agentic-analysis-agent`
**Status**: Proposed
**Created**: 2026-04-02

## Why

The newsletter aggregator currently operates as a **pipeline-driven system** — content flows linearly through ingest → summarize → analyze → digest. Users must manually trigger each step or run the full pipeline on a schedule. There is no autonomous reasoning about *what* to investigate, *when* to dig deeper, or *how* to connect insights across the knowledge base.

Technical leaders need more than a daily digest. They need:
- **Proactive trend detection** — spotting emerging patterns before they become obvious
- **Deep research on demand** — "What's happening with AI agents in enterprise?" answered with structured analysis drawing on the full knowledge base
- **Cross-domain insight generation** — discovering connections between themes that span content sources and time periods
- **Continuous knowledge evolution** — the system should learn and refine its understanding over time

The agentic AI landscape (OpenClaw, Nanobot, NanoClaw, NemoClaw) demonstrates that effective autonomous systems share five primitives: a **reasoning loop**, **persistent memory**, **tool repertoire**, **proactive scheduling**, and **safety guardrails**. Our system already implements most of the underlying capabilities — what's missing is the orchestrating intelligence that ties them together.

## What Changes

### New Components

1. **Conductor Agent** — A meta-cognitive planning agent (inspired by OpenClaw 2.0's Conductor) that:
   - Receives tasks from users or the proactive scheduler
   - Decomposes complex research goals into sub-tasks
   - Delegates to specialist agents
   - Synthesizes results into coherent insights
   - Maintains a configurable persona (YAML-based, inspired by OpenClaw's SOUL.md)

2. **Specialist Agents** — Domain-focused agents wrapping existing processors:
   - **Research Specialist** — Deep-dive investigations using search + knowledge graph + web sources
   - **Analysis Specialist** — Theme detection, trend analysis, historical context (wraps ThemeAnalyzer, HistoricalContextAnalyzer)
   - **Synthesis Specialist** — Generates insights, connections, reports, digests (wraps DigestCreator, podcast generators)
   - **Ingestion Specialist** — Acquires new content from configured sources (wraps ingestion orchestrator)

3. **Memory Provider** — Abstracted memory layer with pluggable strategies:
   - **Graph strategy** — Uses Graphiti/Neo4j for entity-rich, relationship-aware recall
   - **Vector strategy** — Uses PostgreSQL pgvector for semantic similarity search
   - **Keyword strategy** — Uses PostgreSQL BM25 for precise term matching
   - **Hybrid strategy** — Configurable blend of graph + vector + keyword (default)
   - Strategy selection configurable per agent or per task

4. **Proactive Scheduler** — Schedule-driven task engine (inspired by Nanobot's cron + OpenClaw's Heartbeat pattern):
   - Scheduled source scanning, trend detection, anomaly alerts
   - Automatic digest drafting and weekly synthesis
   - Knowledge graph maintenance and cross-theme connection discovery
   - Schedules defined in `settings/schedule.yaml` (separate from personas)
   - Each schedule specifies: persona, output format, and optional source filtering
   - Extends existing PGQueuer job queue for transactional guarantees
   - Same persona can appear in multiple schedules with different source scopes

5. **Approval Gate System** — Risk-tiered action control (inspired by NemoClaw):
   - Low risk (read, search, analyze) → auto-approve
   - Medium risk (ingest, run pipeline) → log + auto-approve
   - High risk (publish, email, modify graph structure) → require human approval
   - Configurable risk levels per action type

6. **Agent Identity (Persona)** — YAML-based agent configuration:
   - Domain focus areas and analysis depth preferences
   - Communication style and output format preferences
   - Strategic priorities and relevance weighting
   - Loadable per task or as persistent default

### Modified Components

7. **LLMRouter Enhancement** — Extend `generate_with_tools()` to support:
   - Reflection steps (agent reviews its own reasoning)
   - Planning phases (explicit goal decomposition before acting)
   - Memory integration (automatic context retrieval at each loop iteration)
   - Iteration budgets and cost limits per task

8. **Pipeline Runner Extension** — Add agent-triggered pipeline stages:
   - Support partial pipeline execution (e.g., "just ingest from this source")
   - Accept agent-generated parameters (date ranges, source filters, focus topics)
   - Report results back to the agent loop

9. **Job Queue Enhancement** — Support agentic task types:
   - `agent_task` entrypoint for conductor-dispatched work
   - Task dependency tracking (sub-tasks must complete before synthesis)
   - Priority-aware scheduling (user tasks > proactive tasks)

### New API & CLI

10. **Agent API endpoints**:
    - `POST /api/v1/agent/task` — Submit a research/analysis task
    - `GET /api/v1/agent/task/{id}` — Get task status and results
    - `GET /api/v1/agent/insights` — List generated insights
    - `POST /api/v1/agent/chat` — Interactive research conversation

11. **CLI commands**:
    - `aca agent task "research question"` — Submit a task
    - `aca agent status` — View active/recent tasks
    - `aca agent insights` — Browse generated insights
    - `aca agent schedule` — Manage proactive schedules

## Approaches Considered

### Approach A: Layered Extension (Recommended)

Build the agentic system as a new layer on top of existing components, extending them minimally.

**Architecture:**
```
┌─────────────────────────────────────────┐
│           NEW: Agent Layer              │
│  Conductor → Specialists → Memory      │
│  Scheduler → Approval Gates → Persona  │
├─────────────────────────────────────────┤
│        EXTENDED: Core Layer             │
│  LLMRouter (+ reflection/planning)     │
│  Pipeline (+ partial execution)        │
│  Job Queue (+ agent task types)        │
├─────────────────────────────────────────┤
│       UNCHANGED: Foundation Layer       │
│  Ingestion │ Parsers │ Search │ Graph  │
│  Models │ Storage │ Observability      │
└─────────────────────────────────────────┘
```

- New code lives in `src/agents/` (conductor, specialists, memory)
- New config in `settings/personas/` (persona directory), `settings/schedule.yaml`, `settings/approval.yaml`
- Existing processors wrapped as specialist tools, not modified
- LLMRouter extended with backward-compatible new parameters

**Pros:**
- Minimal disruption to existing, working system
- Each component can be developed and tested independently
- Existing tests continue to pass unchanged
- Clear separation of agentic logic from domain logic
- Memory provider abstraction is future-proof

**Cons:**
- Some indirection overhead (specialists wrap existing processors)
- Conductor ↔ Specialist communication adds latency
- Two layers of LLM calls for complex tasks (conductor reasons, then specialist executes)

**Effort:** L (Large — new agent framework layer, memory abstraction, scheduler, approval system)

---

### Approach B: Deep Integration

Merge agentic capabilities directly into existing processors and pipeline, making the system "natively agentic."

**Architecture:**
```
┌─────────────────────────────────────────┐
│        MODIFIED: Agentic Pipeline       │
│  ThemeAnalyzer (+ autonomous research)  │
│  DigestCreator (+ insight generation)   │
│  Pipeline (+ agent loop + scheduling)   │
│  LLMRouter (+ full ReAct + memory)     │
│  Job Queue (+ conductor logic)          │
└─────────────────────────────────────────┘
```

- Agentic behavior embedded in existing classes
- ThemeAnalyzer gains autonomous research capabilities
- Pipeline runner becomes the conductor
- No separate specialist agents — processors *are* the agents

**Pros:**
- No wrapper overhead — direct execution
- Fewer new files and abstractions
- Simpler mental model (one layer, not three)

**Cons:**
- High risk of breaking existing functionality
- Existing processors become more complex (mixed concerns)
- Harder to test agentic behavior independently
- Memory provider still needed as a cross-cutting concern
- Difficult to add new specialist types without touching core code

**Effort:** L (Large — extensive modification of existing code, high regression risk)

---

### Approach C: MCP-Native Agent

Build the agent as an external process that interacts with the system entirely through the existing MCP server, treating the aggregator as a tool server.

**Architecture:**
```
┌─────────────────────────────────────┐
│  EXTERNAL: Agent Process            │
│  Conductor + Memory + Scheduler     │
│  Uses Claude Agent SDK or custom    │
├─────────────────┬───────────────────┤
│     MCP Tools   │   Direct DB       │
│  (via MCP srv)  │  (read-only)      │
├─────────────────┴───────────────────┤
│  UNCHANGED: Aggregator System       │
│  Full existing codebase             │
└─────────────────────────────────────┘
```

- Agent is a separate Python process with its own event loop
- Communicates with aggregator via MCP tool calls
- Can also directly query PostgreSQL/Neo4j for reads
- Zero modification to existing codebase

**Pros:**
- Zero risk to existing system
- Clean separation of concerns
- Could run on different hardware
- Easy to swap agent implementations

**Cons:**
- MCP overhead for every operation (serialization, network)
- MCP server doesn't expose all capabilities yet (would need expansion)
- Harder to integrate memory provider deeply
- Separate deployment and monitoring
- Loses access to internal abstractions (LLMRouter's multi-provider routing, etc.)

**Effort:** M (Medium — smaller scope since no existing code changes, but needs MCP expansion)

## Decision Criteria

| Criterion | Weight | Approach A | Approach B | Approach C |
|-----------|--------|-----------|-----------|-----------|
| Existing system stability | High | Best | Risky | Best |
| Development velocity | High | Good | Slow | Fast (initially) |
| Architectural cleanliness | Medium | Best | Poor | Good |
| Performance (latency) | Medium | Good | Best | Worst |
| Future extensibility | High | Best | Poor | Good |
| Testing isolation | High | Best | Poor | Good |
| Memory provider integration | High | Best | Good | Poor |

## Selected Approach

**Approach A: Layered Extension** was selected because it:
1. Preserves the stability of a system that already works well
2. Creates clean architectural boundaries between agentic logic and domain logic
3. Allows the memory provider abstraction to be a first-class citizen
4. Enables independent development and testing of each component
5. Maps naturally to the Conductor + Specialist pattern chosen in discovery
6. Follows the Nanobot philosophy of building on existing capabilities rather than replacing them

Approaches B (Deep Integration) and C (MCP-Native Agent) were rejected:
- **B** was too risky — modifying working processors to embed agentic logic creates regression risk and mixed concerns
- **C** was too limited — MCP overhead and loss of internal abstractions (LLMRouter, memory provider) would constrain the system's capabilities

## Impact on Existing Components

This change modifies the following existing components. All modifications are backward-compatible — existing behavior is preserved when the new optional parameters are not used.

| Component | File(s) | Change | Risk |
|-----------|---------|--------|------|
| **LLMRouter** | `src/services/llm_router.py` | Add `enable_reflection`, `reflection_prompt`, `memory_context`, `cost_limit` optional params to `generate_with_tools()`; add new `generate_with_planning()` method | Low — all new params have defaults; existing callers unchanged |
| **PGQueuer Worker** | `src/queue/worker.py` | Register `agent_task` job handler alongside existing handlers | Low — additive; existing job types unmodified |
| **FastAPI App** | `src/api/app.py` | Mount `agent_routes` router under `/api/v1/agent/` | Low — new prefix; no overlap with existing routes |
| **Alembic Migrations** | `alembic/versions/` | New migration for 5 tables and 3+ PG enums | Low — additive schema; no existing table modifications |
| **ARCHITECTURE.md** | `docs/ARCHITECTURE.md` | Document agent layer in architecture docs | None — documentation only |
| **CLAUDE.md** | `CLAUDE.md` | Add agent CLI commands to quick reference | None — documentation only |

**No existing tests are modified.** A regression test (task 8.6) validates the daily pipeline still works unchanged with the agent layer present.
