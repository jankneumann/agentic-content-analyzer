# Design: Agentic Analysis Agent

**Change ID**: `agentic-analysis-agent`
**Approach**: Layered Extension

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                      Agent Layer (NEW)                        │
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Conductor   │  │  Heartbeat   │  │  Approval Gates    │  │
│  │  Agent       │──│  Scheduler   │  │  (risk-tiered)     │  │
│  └──────┬───┬──┘  └──────┬───────┘  └────────┬───────────┘  │
│         │   │            │                     │              │
│  ┌──────▼───▼──────────────────────────────────▼───────────┐ │
│  │              Specialist Agent Registry                    │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │ │
│  │  │ Research  │ │ Analysis │ │Synthesis │ │ Ingestion  │ │ │
│  │  │Specialist│ │Specialist│ │Specialist│ │ Specialist │ │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘ │ │
│  └─────────────────────────┬───────────────────────────────┘ │
│                             │                                 │
│  ┌──────────────────────────▼──────────────────────────────┐ │
│  │                Memory Provider                           │ │
│  │  ┌───────────┐  ┌───────────┐  ┌─────────────────────┐ │ │
│  │  │  Graph    │  │  Vector   │  │  Keyword (BM25)     │ │ │
│  │  │ Strategy  │  │ Strategy  │  │  Strategy           │ │ │
│  │  └───────────┘  └───────────┘  └─────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────┐  ┌─────────────────────────────────┐   │
│  │  Agent Persona  │  │  Agent Task & Insight Models    │   │
│  │  (YAML config)  │  │  (DB persistence)               │   │
│  └─────────────────┘  └─────────────────────────────────┘   │
├──────────────────────────────────────────────────────────────┤
│                   Extended Core Layer                         │
│                                                               │
│  LLMRouter (+reflection, +planning, +memory hooks)           │
│  Pipeline Runner (+partial execution, +agent params)         │
│  Job Queue (+agent_task entrypoint, +dependencies)           │
├──────────────────────────────────────────────────────────────┤
│                 Unchanged Foundation Layer                    │
│                                                               │
│  Ingestion Services │ Parsers │ Search │ Graphiti/Neo4j      │
│  Content Models │ Storage Providers │ Observability          │
└──────────────────────────────────────────────────────────────┘
```

## Design Decisions

### D1: Conductor Agent as Stateful Task Manager

The Conductor Agent is the entry point for all agentic work — both user-initiated tasks and heartbeat-scheduled jobs. It maintains state across the lifecycle of a task.

**State machine:**
```
RECEIVED → PLANNING → DELEGATING → MONITORING → SYNTHESIZING → COMPLETED
                                       ↓
                                   BLOCKED (awaiting approval)
                                       ↓
                                   APPROVED → DELEGATING (resume)
```

**Key design choices:**
- Conductor uses `LLMRouter.generate_with_tools()` for its reasoning loop
- Tools available to conductor: `delegate_to_specialist`, `query_memory`, `store_insight`, `request_approval`, `report_progress`
- Conductor does NOT execute domain tasks directly — it only plans and delegates
- Task state persisted in PostgreSQL (new `agent_tasks` table) for crash recovery
- Each task gets an OTel trace for full observability

**Rejected alternative:** Having the conductor call processors directly (like Pipeline Runner does). This would bypass the specialist abstraction and make it harder to add new specialist types.

### D2: Specialist Agents as Tool-Equipped Wrappers

Each specialist wraps one or more existing processors/services and exposes them through a uniform interface.

```python
class BaseSpecialist(ABC):
    """Base class for all specialist agents."""

    @abstractmethod
    async def execute(self, task: SpecialistTask) -> SpecialistResult:
        """Execute a specialist task."""

    @abstractmethod
    def get_tools(self) -> list[ToolDefinition]:
        """Return tools this specialist can use in its reasoning loop."""

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """Describe what this specialist can do (for conductor's planning)."""
```

**Specialist inventory:**

| Specialist | Wraps | Tools |
|-----------|-------|-------|
| ResearchSpecialist | HybridSearchService, GraphitiClient, web search | `search_content`, `query_knowledge_graph`, `search_web`, `fetch_url` |
| AnalysisSpecialist | ThemeAnalyzer, HistoricalContextAnalyzer | `analyze_themes`, `get_historical_context`, `detect_anomalies`, `compare_periods` |
| SynthesisSpecialist | DigestCreator, PodcastScriptGenerator | `create_report`, `generate_insight`, `draft_digest`, `create_briefing` |
| IngestionSpecialist | Ingestion orchestrator | `ingest_source`, `scan_sources`, `ingest_url` |

**Key design choice:** Specialists have their own mini reasoning loops (via `generate_with_tools()`). The Research Specialist, for example, can decide to query the knowledge graph, then search for more context, then fetch a URL — all within a single delegated task. This is the Nanobot-inspired "tool palette" pattern at the specialist level.

**Rejected alternative:** Making specialists simple function calls without reasoning. This would limit their ability to handle complex, multi-step sub-tasks autonomously.

### D3: Memory Provider with Strategy Pattern

The memory provider abstracts how agents store and recall information. It uses a strategy pattern so different memory backends can be composed.

```python
class MemoryStrategy(ABC):
    """Interface for memory storage/retrieval strategies."""

    @abstractmethod
    async def store(self, memory: MemoryEntry) -> str:
        """Store a memory, return its ID."""

    @abstractmethod
    async def recall(self, query: str, limit: int = 10,
                     filters: MemoryFilter | None = None) -> list[MemoryEntry]:
        """Recall memories relevant to a query."""

    @abstractmethod
    async def forget(self, memory_id: str) -> bool:
        """Remove a memory entry."""


class MemoryProvider:
    """Composes multiple strategies with configurable weighting."""

    def __init__(self, strategies: dict[str, tuple[MemoryStrategy, float]]):
        # e.g., {"graph": (GraphStrategy(), 0.4), "vector": (VectorStrategy(), 0.4), "keyword": (KeywordStrategy(), 0.2)}
        ...

    async def recall(self, query: str, ...) -> list[MemoryEntry]:
        """Query all strategies, merge results using weighted RRF."""
```

**Memory entry model:**
```python
class MemoryEntry:
    id: str
    content: str                    # The actual memory text
    memory_type: MemoryType         # OBSERVATION, INSIGHT, TASK_RESULT, PREFERENCE, META_LEARNING
    source_task_id: str | None      # Which task produced this memory
    tags: list[str]                 # For filtering
    confidence: float               # How reliable this memory is
    created_at: datetime
    last_accessed: datetime         # For recency-weighted recall
    access_count: int               # For frequency-weighted recall
```

**Strategy implementations:**

| Strategy | Backend | Best For | Recall Method |
|----------|---------|----------|--------------|
| GraphStrategy | Graphiti/Neo4j | Entity relationships, temporal evolution | Semantic search + relationship traversal |
| VectorStrategy | PostgreSQL pgvector | Semantic similarity, fuzzy matching | Cosine similarity on embeddings |
| KeywordStrategy | PostgreSQL FTS | Precise term matching, known-item retrieval | BM25 ranking |
| HybridStrategy | All of above | Default — balanced recall | Weighted RRF fusion (configurable) |

**Key design choice:** Memory strategies use the same backends as the existing search system (`src/services/search.py` for vector+keyword, `src/storage/graphiti_client.py` for graph) but through a memory-specific interface. This avoids duplicating infrastructure while allowing memory-specific optimizations (e.g., recency weighting, confidence filtering).

**Rejected alternative:** Building a separate memory store (Redis, SQLite, flat files like OpenClaw's MEMORY.md). This would duplicate existing infrastructure and miss the opportunity to leverage the knowledge graph for relationship-rich recall.

### D4: Heartbeat Scheduler as PGQueuer Extension

The heartbeat scheduler manages proactive tasks. Rather than introducing a new scheduling system (like APScheduler or Celery Beat), it extends the existing PGQueuer job queue.

**Design:**
```python
# settings/heartbeat.yaml
schedules:
  scan_sources:
    cron: "0 */4 * * *"        # Every 4 hours
    task_type: ingestion
    description: "Scan all enabled sources for new content"
    priority: low

  trend_detection:
    cron: "0 9 * * *"          # Daily at 9 AM
    task_type: analysis
    params:
      lookback_days: 1
      focus: emerging_trends
    description: "Detect emerging trends in yesterday's content"
    priority: medium

  weekly_synthesis:
    cron: "0 10 * * MON"       # Monday at 10 AM
    task_type: synthesis
    params:
      lookback_days: 7
      output: weekly_briefing
    description: "Generate weekly trend synthesis and briefing"
    priority: medium

  knowledge_maintenance:
    cron: "0 3 * * *"          # Nightly at 3 AM
    task_type: maintenance
    params:
      actions: [prune_stale, merge_duplicates, refresh_embeddings]
    description: "Knowledge graph maintenance and optimization"
    priority: low

  cross_theme_discovery:
    cron: "0 14 * * WED"       # Wednesday at 2 PM
    task_type: analysis
    params:
      lookback_days: 30
      focus: cross_theme_connections
    description: "Discover connections between themes across 30 days"
    priority: low

  draft_daily_digest:
    cron: "0 17 * * MON-FRI"   # Weekdays at 5 PM
    task_type: synthesis
    params:
      output: daily_digest_draft
    description: "Draft daily digest for review"
    priority: medium
```

**Implementation:** A lightweight scheduler thread checks `heartbeat.yaml` schedules against the current time and enqueues `agent_task` jobs into PGQueuer. The conductor picks these up like any other task.

**Key design choice:** Using PGQueuer rather than a separate scheduler gives us transactional guarantees, deduplication (don't re-enqueue if a previous run is still active), and unified job monitoring.

**Rejected alternative:** Using APScheduler or Celery Beat. These introduce new infrastructure dependencies and separate monitoring concerns. PGQueuer already handles everything we need.

### D5: Tiered Approval Gates

Actions are classified by risk level. The approval gate system intercepts high-risk actions before execution.

```python
class RiskLevel(StrEnum):
    LOW = "low"         # Read, search, analyze — auto-approve
    MEDIUM = "medium"   # Ingest, run pipeline — log + auto-approve
    HIGH = "high"       # Publish, email, modify graph structure — require approval
    CRITICAL = "critical"  # Delete content, modify agent config — require approval + audit

# settings/approval.yaml
risk_levels:
  # Low risk — always auto-approved
  search_content: low
  query_knowledge_graph: low
  analyze_themes: low
  get_historical_context: low

  # Medium risk — logged, auto-approved
  ingest_source: medium
  ingest_url: medium
  run_pipeline: medium
  summarize_content: medium

  # High risk — requires human approval
  create_digest: high
  send_email: high
  publish_digest: high
  store_graph_episode: high

  # Critical — requires approval + full audit trail
  delete_content: critical
  modify_agent_config: critical
  bulk_operations: critical
```

**Approval flow:**
1. Specialist (or conductor) calls `request_approval(action, context, risk_level)`
2. If LOW or MEDIUM: auto-approve, log to audit trail
3. If HIGH or CRITICAL: create `ApprovalRequest` in DB, notify user (API/CLI/notification)
4. Task enters BLOCKED state until user approves/denies
5. On approval: resume task execution
6. On denial: task receives denial reason, conductor can adjust plan

**Key design choice:** Risk levels are configured in YAML, not hard-coded. Users can adjust risk tolerance as they gain confidence in the system. Initial defaults are conservative.

### D6: Agent Persona Configuration

The persona system uses YAML configuration (inspired by OpenClaw's SOUL.md) loaded via `ConfigRegistry`.

```yaml
# settings/persona.yaml
name: "AI Trend Analyst"
role: "Senior technology strategist specializing in AI/ML/Data trends"

domain_focus:
  primary:
    - artificial_intelligence
    - machine_learning
    - data_engineering
  secondary:
    - devops_infrastructure
    - security
    - developer_tools

analysis_preferences:
  depth: thorough           # brief | standard | thorough | exhaustive
  perspective: strategic    # tactical | strategic | both
  time_horizon: 6_months    # 1_month | 3_months | 6_months | 1_year
  novelty_bias: 0.7         # 0.0 (established only) to 1.0 (emerging only)

communication_style:
  tone: professional_concise
  format: structured_markdown
  include_confidence: true
  include_sources: true
  max_insight_length: 500   # words per insight

relevance_weighting:
  strategic_impact: 0.3
  technical_depth: 0.25
  novelty: 0.25
  cross_domain_relevance: 0.2
```

**Key design choice:** Persona is loaded once at conductor initialization and injected into the system prompt. It influences how the conductor plans tasks, how specialists frame their analysis, and how synthesis formats output. The persona is NOT self-modifiable (unlike OpenClaw's SOUL.md) — this prevents drift and maintains predictable behavior.

**Rejected alternative:** Self-modifiable persona (OpenClaw pattern). While appealing for continuous improvement, self-modification creates unpredictable behavior and makes it hard to reproduce results.

### D7: LLMRouter Extensions

The existing `generate_with_tools()` is extended with three new capabilities, all backward-compatible:

**a) Reflection steps:**
```python
async def generate_with_tools(
    self,
    ...,
    enable_reflection: bool = False,    # NEW: Agent reviews its own output
    reflection_prompt: str | None = None,  # NEW: Custom reflection instruction
) -> LLMResponse:
```

When `enable_reflection=True`, after the tool loop completes, the model is asked to review its reasoning and output quality. If the reflection identifies issues, the loop can continue.

**b) Planning phase:**
```python
async def generate_with_planning(
    self,
    goal: str,
    tools: list[ToolDefinition],
    tool_executor: Callable,
    max_iterations: int = 10,
    memory_context: list[MemoryEntry] | None = None,  # NEW
) -> LLMResponse:
```

A higher-level method that first asks the model to create an explicit plan, then executes the plan step-by-step via `generate_with_tools()`.

**c) Memory hooks:**
At each iteration of the tool loop, the router can optionally query the memory provider for relevant context and inject it into the conversation.

### D8: Data Model Extensions

**New tables:**

```sql
-- Agent tasks (conductor-managed)
CREATE TABLE agent_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR NOT NULL,          -- 'research', 'analysis', 'synthesis', 'ingestion'
    source VARCHAR NOT NULL,             -- 'user', 'heartbeat', 'conductor'
    prompt TEXT NOT NULL,                -- Original task description
    plan JSONB,                          -- Conductor's decomposed plan
    status VARCHAR NOT NULL DEFAULT 'received',  -- State machine states
    result JSONB,                        -- Final result
    parent_task_id UUID REFERENCES agent_tasks(id),  -- For sub-tasks
    specialist_type VARCHAR,             -- Which specialist is handling
    persona_config JSONB,                -- Snapshot of persona at task time
    cost_total DECIMAL(10, 6),           -- Total LLM cost
    tokens_total INTEGER,                -- Total tokens used
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent insights (generated findings)
CREATE TABLE agent_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES agent_tasks(id),
    insight_type VARCHAR NOT NULL,       -- 'trend', 'connection', 'anomaly', 'prediction', 'summary'
    title VARCHAR NOT NULL,
    content TEXT NOT NULL,                -- Markdown formatted
    confidence FLOAT NOT NULL,
    tags JSONB DEFAULT '[]',
    related_content_ids JSONB DEFAULT '[]',
    related_theme_ids JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent memory entries
CREATE TABLE agent_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_type VARCHAR NOT NULL,        -- 'observation', 'insight', 'task_result', 'preference', 'meta_learning'
    content TEXT NOT NULL,
    embedding vector(1536),              -- For vector strategy recall
    tags JSONB DEFAULT '[]',
    source_task_id UUID REFERENCES agent_tasks(id),
    confidence FLOAT DEFAULT 1.0,
    access_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Approval requests
CREATE TABLE approval_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES agent_tasks(id),
    action VARCHAR NOT NULL,
    risk_level VARCHAR NOT NULL,
    context JSONB NOT NULL,              -- What the agent wants to do and why
    status VARCHAR NOT NULL DEFAULT 'pending',  -- pending, approved, denied
    decision_reason TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Heartbeat schedule state (tracks last run, next run)
CREATE TABLE heartbeat_schedules (
    id VARCHAR PRIMARY KEY,              -- Matches YAML schedule key
    cron_expression VARCHAR NOT NULL,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    last_status VARCHAR,                 -- 'completed', 'failed', 'skipped'
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**New enums (Python + Postgres):**
```python
class AgentTaskStatus(StrEnum):
    RECEIVED = "received"
    PLANNING = "planning"
    DELEGATING = "delegating"
    MONITORING = "monitoring"
    SYNTHESIZING = "synthesizing"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"

class InsightType(StrEnum):
    TREND = "trend"
    CONNECTION = "connection"
    ANOMALY = "anomaly"
    PREDICTION = "prediction"
    SUMMARY = "summary"

class MemoryType(StrEnum):
    OBSERVATION = "observation"
    INSIGHT = "insight"
    TASK_RESULT = "task_result"
    PREFERENCE = "preference"
    META_LEARNING = "meta_learning"
```

## File Structure

```
src/
├── agents/
│   ├── __init__.py
│   ├── base.py                          # EXISTING — extend with BaseSpecialist
│   ├── conductor.py                     # NEW — Conductor agent
│   ├── registry.py                      # NEW — Specialist registry
│   ├── specialists/
│   │   ├── __init__.py
│   │   ├── base.py                      # NEW — BaseSpecialist ABC
│   │   ├── research.py                  # NEW — ResearchSpecialist
│   │   ├── analysis.py                  # NEW — AnalysisSpecialist
│   │   ├── synthesis.py                 # NEW — SynthesisSpecialist
│   │   └── ingestion.py                 # NEW — IngestionSpecialist
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── provider.py                  # NEW — MemoryProvider (composition)
│   │   ├── strategies/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                  # NEW — MemoryStrategy ABC
│   │   │   ├── graph.py                 # NEW — GraphStrategy (Graphiti)
│   │   │   ├── vector.py                # NEW — VectorStrategy (pgvector)
│   │   │   └── keyword.py              # NEW — KeywordStrategy (BM25)
│   │   └── models.py                    # NEW — MemoryEntry, MemoryFilter
│   ├── heartbeat/
│   │   ├── __init__.py
│   │   ├── scheduler.py                 # NEW — Heartbeat scheduler
│   │   └── tasks.py                     # NEW — Proactive task definitions
│   ├── approval/
│   │   ├── __init__.py
│   │   ├── gates.py                     # NEW — Approval gate system
│   │   └── models.py                    # NEW — ApprovalRequest model
│   └── persona/
│       ├── __init__.py
│       └── loader.py                    # NEW — Persona config loader
├── models/
│   ├── agent_task.py                    # NEW — AgentTask ORM model
│   ├── agent_insight.py                 # NEW — AgentInsight ORM model
│   ├── agent_memory.py                  # NEW — AgentMemory ORM model
│   └── approval_request.py             # NEW — ApprovalRequest ORM model
├── api/
│   └── agent_routes.py                  # NEW — Agent API endpoints
├── cli/
│   └── agent_commands.py                # NEW — Agent CLI commands
├── services/
│   └── llm_router.py                    # MODIFIED — Add reflection, planning, memory hooks
├── queue/
│   └── worker.py                        # MODIFIED — Add agent_task handler
settings/
├── persona.yaml                         # NEW — Default agent persona
├── heartbeat.yaml                       # NEW — Proactive task schedules
└── approval.yaml                        # NEW — Risk level configuration
```

## Integration Points

### With Existing Pipeline
- Heartbeat triggers `run_pipeline()` via IngestionSpecialist
- Conductor can request partial pipeline runs (ingest-only, summarize-only)
- Pipeline results fed back to conductor for synthesis decisions

### With Knowledge Graph
- GraphStrategy queries Graphiti for memory recall
- AnalysisSpecialist uses GraphitiClient for entity/relationship queries
- Insights stored as Graphiti episodes for future recall

### With Search System
- VectorStrategy and KeywordStrategy use existing search infrastructure
- ResearchSpecialist uses HybridSearchService for content discovery

### With Job Queue
- `agent_task` registered as PGQueuer entrypoint
- Sub-tasks tracked as dependent jobs
- Heartbeat enqueues scheduled tasks via PGQueuer

### With Observability
- Each agent task creates an OTel trace
- Specialist invocations are child spans
- Memory operations instrumented
- Cost tracking per task and per agent
