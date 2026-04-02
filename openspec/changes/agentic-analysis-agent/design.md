# Design: Agentic Analysis Agent

**Change ID**: `agentic-analysis-agent`
**Approach**: Layered Extension

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                      Agent Layer (NEW)                        │
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Conductor   │  │  Proactive   │  │  Approval Gates    │  │
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

The Conductor Agent is the entry point for all agentic work — both user-initiated tasks and schedule-triggered proactive jobs. It maintains state across the lifecycle of a task.

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
- **Persona-parameterized**: Every task execution receives a persona name (defaults to `"default"`). The conductor loads that persona's full configuration — model overrides, approval overrides, tool restrictions, output preferences — and enforces them throughout the task lifecycle. The same conductor code handles all personas.

```python
class Conductor:
    async def execute_task(
        self,
        task: AgentTask,
        persona: str = "default",
    ) -> AgentTaskResult:
        """Execute a task under a specific persona's policy."""
        persona_config = PersonaLoader.load(persona)

        # Persona controls model selection for each specialist step
        model = persona_config.resolve_model(task.task_type)

        # Persona filters available tools for specialists
        available_tools = persona_config.filter_tools(
            self.registry.get_all_tools()
        )

        # Persona overrides approval risk levels
        approval_gate = ApprovalGate(
            base_config=self.approval_config,
            overrides=persona_config.approval_overrides,
        )

        # Persona shapes output format
        output_config = persona_config.output
        ...
```

**Rejected alternative:** Having the conductor call processors directly (like Pipeline Runner does). This would bypass the specialist abstraction and make it harder to add new specialist types.

**Rejected alternative:** Separate conductor classes per persona. This duplicates orchestration logic and makes the conductor harder to maintain. Persona-as-configuration is cleaner.

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

### D4: Schedule-Driven Proactive Tasks (PGQueuer Extension)

The scheduler manages proactive tasks. Rather than introducing a new scheduling system (like APScheduler or Celery Beat), it extends the existing PGQueuer job queue. Schedules are defined in `settings/schedule.yaml` — separate from persona definitions, because the same persona can be used across different schedules with different parameters, sources, and output formats.

**Design:**
```python
# settings/schedule.yaml
schedules:
  # ─── Infrastructure (no persona) ────────────────────────────
  scan_sources:
    cron: "0 */4 * * *"
    task_type: ingestion
    description: "Scan all enabled sources for new content"
    priority: low

  knowledge_maintenance:
    cron: "0 3 * * *"
    task_type: maintenance
    params:
      actions: [prune_stale, merge_duplicates, refresh_embeddings]
    description: "Knowledge graph maintenance and optimization"
    priority: low

  # ─── Analysis ──────────────────────────────────────────────
  # Same persona, different source scopes:
  trend_detection_tech:
    cron: "0 9 * * *"
    task_type: analysis
    persona: ai-ml-technology
    output: technical_report
    params:
      lookback_days: 1
      focus: emerging_trends
    description: "Detect emerging AI/ML trends in yesterday's content"
    priority: medium

  trend_detection_tech_arxiv_only:
    cron: "0 11 * * *"
    task_type: analysis
    persona: ai-ml-technology          # Same persona, different sources
    output: technical_report
    sources: [arxiv, scholar]           # Only academic sources
    params:
      lookback_days: 7
      focus: research_breakthroughs
    description: "Weekly research paper trend analysis"
    priority: low

  trend_detection_leadership:
    cron: "0 9,30 * * *"
    task_type: analysis
    persona: leadership
    output: executive_briefing          # Output controlled at schedule level
    params:
      lookback_days: 1
      focus: strategic_shifts
    description: "Detect strategic leadership trends"
    priority: medium

  # ─── Synthesis ─────────────────────────────────────────────
  weekly_synthesis_tech:
    cron: "0 10 * * MON"
    task_type: synthesis
    persona: ai-ml-technology
    output: technical_report
    params:
      lookback_days: 7
    description: "Weekly AI/ML trend synthesis"
    priority: medium

  weekly_synthesis_leadership:
    cron: "0 10,30 * * MON"
    task_type: synthesis
    persona: leadership
    output: executive_briefing
    params:
      lookback_days: 7
    description: "Weekly leadership briefing"
    priority: medium

  cross_theme_discovery:
    cron: "0 14 * * WED"
    task_type: analysis
    persona: ai-ml-technology
    output: raw_insights
    params:
      lookback_days: 30
      focus: cross_theme_connections
    description: "Discover connections between themes across 30 days"
    priority: low

  # ─── Daily Digests ─────────────────────────────────────────
  # Same persona can produce different output formats:
  draft_daily_digest_tech:
    cron: "0 17 * * MON-FRI"
    task_type: synthesis
    persona: ai-ml-technology
    output: digest
    description: "Draft daily AI/ML digest"
    priority: medium

  draft_daily_digest_leadership:
    cron: "0 17,15 * * MON-FRI"
    task_type: synthesis
    persona: leadership
    output: digest                      # Leadership digest — concise by persona style
    description: "Draft daily leadership digest"
    priority: medium
```

**Implementation:** A lightweight scheduler thread checks `schedule.yaml` schedules against the current time and enqueues `agent_task` jobs into PGQueuer with the schedule's `persona`, `output`, and `sources` fields as task parameters. The conductor picks these up like any other task — loading the specified persona and applying the output format.

**Schedule-level fields** (all optional, compose freely):
- `persona` — which persona to use (defaults to `default`)
- `output` — output format override (`technical_report`, `executive_briefing`, `digest`, `raw_insights`)
- `sources` — restrict analysis to specific source types (e.g., `[arxiv, scholar]`)
- `params` — additional task-specific parameters

This separation means: a persona defines *how* to analyze; a schedule defines *when*, *what sources*, and *what output*. The same persona can appear in multiple schedules with different source scopes and output formats.

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
2. The gate resolves the **effective risk level**: persona override > base `approval.yaml` > default (MEDIUM)
3. If LOW or MEDIUM: auto-approve, log to audit trail
4. If HIGH or CRITICAL: create `ApprovalRequest` in DB, notify user (API/CLI/notification)
5. Task enters BLOCKED state until user approves/denies
6. On approval: resume task execution
7. On denial: task receives denial reason, conductor can adjust plan

**Per-persona override resolution:**
```python
class ApprovalGate:
    def __init__(
        self,
        base_config: dict[str, RiskLevel],     # From settings/approval.yaml
        overrides: dict[str, RiskLevel] | None, # From persona's approval_overrides
    ):
        self.base_config = base_config
        self.overrides = overrides or {}

    def get_risk_level(self, action: str) -> RiskLevel:
        """Persona override > base config > default MEDIUM."""
        if action in self.overrides:
            return self.overrides[action]
        return self.base_config.get(action, RiskLevel.MEDIUM)
```

Example: The base config says `create_digest: high` (requires approval). A leadership persona sets `approval_overrides: {create_digest: medium}` — now the leadership persona can auto-create digests, while the tech persona still needs approval. This allows trusted, well-tested personas to operate with less friction.

**Key design choice:** Risk levels are configured in YAML, not hard-coded. Users can adjust risk tolerance both globally (`approval.yaml`) and per-persona. A persona can only **lower** its own risk levels — it cannot escalate another persona's constraints. Initial defaults are conservative.

### D6: Multi-Persona Configuration

The persona system uses a **directory of YAML files** — each file is a self-contained agent profile that controls not just the LLM's tone and focus, but also model selection, tool access, approval thresholds, and output format. Personas are **policy bundles**, not just prompt decorations.

```
settings/
└── personas/
    ├── default.yaml              # Fallback — used when no persona specified
    ├── ai-ml-technology.yaml     # Deep technical AI/ML focus
    ├── leadership.yaml           # CTO/VP strategic lens
    ├── data-engineering.yaml     # Data infra & platform focus
    └── security-ai.yaml          # AI safety & security angle
```

**Full persona schema** (all sections optional — missing sections inherit from `default.yaml`):

```yaml
# settings/personas/ai-ml-technology.yaml
name: "AI/ML Technology Analyst"
role: "Senior ML engineer tracking cutting-edge AI research and tooling"

# --- Domain & Analysis Lens ---
domain_focus:
  primary:
    - machine_learning
    - deep_learning
    - natural_language_processing
    - computer_vision
  secondary:
    - mlops
    - data_engineering
    - research_papers

analysis_preferences:
  depth: exhaustive          # brief | standard | thorough | exhaustive
  perspective: tactical      # tactical | strategic | both
  time_horizon: 3_months     # 1_month | 3_months | 6_months | 1_year
  novelty_bias: 0.8          # 0.0 (established only) to 1.0 (emerging only)

relevance_weighting:
  strategic_impact: 0.15
  technical_depth: 0.40      # Heavy weight on technical detail
  novelty: 0.30
  cross_domain_relevance: 0.15

# --- Model Overrides (per specialist task type) ---
# Override the global MODEL_* settings for specific pipeline steps.
# Only the steps listed here are overridden; unlisted steps use global defaults.
model_overrides:
  theme_analysis: claude-sonnet-4-5       # More capable model for deep analysis
  digest_creation: claude-sonnet-4-5      # High quality technical digests
  summarization: claude-haiku-4-5         # Fast model is fine for summarization
  # research, historical_context, etc. → use global defaults

# --- Approval Overrides ---
# Override base settings/approval.yaml risk levels for this persona.
# Can only LOWER risk (e.g., high → medium), never escalate.
approval_overrides:
  store_graph_episode: medium             # Auto-approve graph writes for tech persona
  # create_digest remains HIGH from base config

# --- Tool Restrictions ---
# Restrict which specialist tools this persona can use.
# If omitted, all tools are available. If present, only unlisted tools are blocked.
restricted_tools: []                      # Tech persona has full tool access

# --- Output Defaults ---
# These defaults apply when no output format is specified at schedule/task level.
# Schedules can override default_format; style settings always come from persona.
output_defaults:
  default_format: technical_report        # technical_report | executive_briefing | digest | raw_insights
  include_code_examples: true
  include_architecture_diagrams: true
  include_confidence: true
  include_sources: true
  max_insight_length: 800                 # words per insight (longer for technical depth)

# --- Communication Style ---
# How this persona writes — applies regardless of output format.
communication_style:
  tone: technical_detailed
  format: structured_markdown
  audience: engineers_and_architects
```

```yaml
# settings/personas/leadership.yaml
name: "Leadership Strategist"
role: "VP/CTO-level advisor focused on AI adoption, team impact, and competitive landscape"

domain_focus:
  primary:
    - business_strategy
    - ai_adoption
    - team_management
    - competitive_landscape
  secondary:
    - artificial_intelligence
    - data_strategy
    - security

analysis_preferences:
  depth: brief               # Leaders want signal, not noise
  perspective: strategic
  time_horizon: 6_months
  novelty_bias: 0.3          # Focus on proven, actionable trends

relevance_weighting:
  strategic_impact: 0.50     # Dominant weight on business relevance
  technical_depth: 0.10
  novelty: 0.15
  cross_domain_relevance: 0.25

model_overrides:
  digest_creation: claude-haiku-4-5       # Fast model — briefings are concise
  theme_analysis: claude-sonnet-4-5       # Good analysis still needed
  # summarization → global default

approval_overrides:
  create_digest: medium                   # Leadership digests auto-approved
  send_email: medium                      # Can auto-send briefings

restricted_tools:
  - fetch_url                             # No external URL fetching
  - search_web                            # No web searches — only internal knowledge

output_defaults:
  default_format: executive_briefing
  include_code_examples: false
  include_architecture_diagrams: false
  include_confidence: true
  include_sources: true
  max_insight_length: 300                 # Concise — busy leaders

communication_style:
  tone: executive_concise
  format: structured_markdown
  audience: cto_and_vp_level
```

```yaml
# settings/personas/default.yaml
name: "AI Trend Analyst"
role: "Balanced technology strategist spanning CTO-level strategy to practitioner best practices"

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
  depth: thorough
  perspective: both
  time_horizon: 6_months
  novelty_bias: 0.5

relevance_weighting:
  strategic_impact: 0.3
  technical_depth: 0.25
  novelty: 0.25
  cross_domain_relevance: 0.2

model_overrides: {}          # Use global MODEL_* settings
approval_overrides: {}       # Use base approval.yaml
restricted_tools: []         # All tools available

output_defaults:
  default_format: digest
  include_code_examples: false
  include_architecture_diagrams: false
  include_confidence: true
  include_sources: true
  max_insight_length: 500

communication_style:
  tone: professional_concise
  format: structured_markdown
  audience: technical_leaders
```

**Persona loader with inheritance:**

```python
class PersonaConfig(BaseModel):
    """Validated persona configuration with inheritance from default."""
    name: str
    role: str
    domain_focus: DomainFocus
    analysis_preferences: AnalysisPreferences
    relevance_weighting: RelevanceWeighting
    model_overrides: dict[str, str] = {}
    approval_overrides: dict[str, RiskLevel] = {}
    restricted_tools: list[str] = []
    output_defaults: OutputDefaults       # Persona's defaults (schedule can override format)
    communication_style: CommunicationStyle

    def resolve_model(self, step: str) -> str | None:
        """Return model override for a step, or None to use global default."""
        return self.model_overrides.get(step)

    def filter_tools(self, tools: list[ToolDefinition]) -> list[ToolDefinition]:
        """Remove tools that this persona is restricted from using."""
        if not self.restricted_tools:
            return tools
        return [t for t in tools if t.name not in self.restricted_tools]

    def resolve_output(self, schedule_output: str | None = None) -> OutputDefaults:
        """Merge schedule-level output format with persona's output defaults.

        Schedule specifies *what format* (e.g., "executive_briefing").
        Persona specifies *how to write it* (e.g., max_insight_length, include_sources).
        """
        if schedule_output:
            return self.output_defaults.model_copy(
                update={"default_format": schedule_output}
            )
        return self.output_defaults


class PersonaLoader:
    """Loads persona YAML files from settings/personas/ with default inheritance."""

    PERSONAS_DIR = "settings/personas"

    @classmethod
    def load(cls, name: str = "default") -> PersonaConfig:
        """Load a persona by name. Missing fields inherit from default.yaml."""
        default_data = cls._read_yaml("default")
        if name == "default":
            return PersonaConfig(**default_data)

        persona_data = cls._read_yaml(name)
        # Deep merge: persona values override default values
        merged = deep_merge(default_data, persona_data)
        return PersonaConfig(**merged)

    @classmethod
    def list_personas(cls) -> list[str]:
        """List all available persona names."""
        ...
```

**Key design choices:**
- **Personas are policy bundles** — they control model selection, tool access, approval thresholds, and communication style, not just the LLM system prompt. This is inspired by NemoClaw's policy enforcement but configured via YAML rather than kernel-level guardrails.
- **Separation of persona and schedule** — A persona defines *how* to think and write. A schedule defines *when* to run, *which sources* to analyze, and *what output format* to produce. The same persona can appear in multiple schedules with different source scopes and output types (e.g., `ai-ml-technology` persona can produce both a `technical_report` from arXiv papers and a `digest` from all sources). Output format defaults live in the persona (`output_defaults.default_format`) but can be overridden per schedule.
- **Inheritance from default** — each persona only needs to specify what differs from the default. A new persona can be as simple as 5 lines overriding `domain_focus` and `analysis_preferences`.
- **Per-step model overrides** — different personas can use different models for different tasks. The leadership persona uses a fast model for digest creation (concise output), while the tech persona uses a more capable model (detailed analysis). This maps to the existing `ModelStep` system.
- **Approval overrides can only lower risk** — a persona can set `create_digest: medium` (auto-approve) where the base is `high`, but cannot set `delete_content: low` if the base is `critical`. This prevents misconfigured personas from bypassing safety.
- **Tool restrictions are deny-lists** — by default all tools are available. The leadership persona blocks `fetch_url` and `search_web` because it should rely on internal knowledge only.
- Persona is NOT self-modifiable (unlike OpenClaw's SOUL.md) — this prevents drift and maintains predictable behavior.

**Rejected alternative:** Self-modifiable persona (OpenClaw pattern). While appealing for continuous improvement, self-modification creates unpredictable behavior and makes it hard to reproduce results.

**Rejected alternative:** Separate conductor classes per persona. The conductor is generic orchestration; the persona is the parameterization. Duplicating conductor code per persona would be a maintenance burden.

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
    source VARCHAR NOT NULL,             -- 'user', 'schedule', 'conductor'
    prompt TEXT NOT NULL,                -- Original task description
    plan JSONB,                          -- Conductor's decomposed plan
    status VARCHAR NOT NULL DEFAULT 'received',  -- State machine states
    result JSONB,                        -- Final result
    parent_task_id UUID REFERENCES agent_tasks(id),  -- For sub-tasks
    specialist_type VARCHAR,             -- Which specialist is handling
    persona_name VARCHAR NOT NULL DEFAULT 'default',  -- Which persona was used
    persona_config JSONB,                -- Full snapshot of persona at task time (for reproducibility)
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

-- Schedule state (tracks last run, next run)
CREATE TABLE agent_schedules (
    id VARCHAR PRIMARY KEY,              -- Matches YAML schedule key
    cron_expression VARCHAR NOT NULL,
    persona_name VARCHAR,                -- Which persona to run with (NULL = no persona)
    output_type VARCHAR,                 -- Output format override for this schedule
    source_filter JSONB,                 -- Optional source filtering for this run
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
│   ├── scheduler/
│   │   ├── __init__.py
│   │   ├── scheduler.py                 # NEW — Schedule runner (cron → PGQueuer)
│   │   └── tasks.py                     # NEW — Proactive task definitions
│   ├── approval/
│   │   ├── __init__.py
│   │   ├── gates.py                     # NEW — Approval gate system
│   │   └── models.py                    # NEW — ApprovalRequest model
│   └── persona/
│       ├── __init__.py
│       ├── loader.py                    # NEW — PersonaLoader with inheritance
│       └── models.py                    # NEW — PersonaConfig, DomainFocus, OutputConfig
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
├── personas/                            # NEW — Multi-persona directory
│   ├── default.yaml                     # NEW — Default balanced persona (fallback)
│   ├── ai-ml-technology.yaml            # NEW — Deep technical AI/ML focus
│   ├── leadership.yaml                  # NEW — CTO/VP strategic lens
│   ├── data-engineering.yaml            # NEW — Data infra & platform focus
│   └── security-ai.yaml                # NEW — AI safety & security angle
├── schedule.yaml                        # NEW — Proactive task schedules (with persona + output + source refs)
└── approval.yaml                        # NEW — Base risk level configuration
```

## Integration Points

### With Existing Pipeline
- Scheduler triggers `run_pipeline()` via IngestionSpecialist
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
- Scheduler enqueues scheduled tasks via PGQueuer

### With Observability
- Each agent task creates an OTel trace
- Specialist invocations are child spans
- Memory operations instrumented
- Cost tracking per task and per agent

## Mock Boundaries for Testing

Tests for each component mock at well-defined boundaries to enable isolated, fast testing:

| Component | Mocks | Real |
|-----------|-------|------|
| Conductor | All specialists (mock execute), MemoryProvider, ApprovalGate, PersonaLoader | State machine logic, planning |
| Specialists | LLMRouter.generate_with_tools(), wrapped services (SearchService, GraphitiClient, etc.) | Tool registration, capability declaration |
| MemoryProvider | Individual strategies (GraphStrategy, VectorStrategy, KeywordStrategy) | RRF fusion, weight calculation, dedup |
| Individual Strategies | DB sessions (AsyncSession), GraphitiClient, embedding calls | Strategy-specific query building |
| Scheduler | PGQueuer.enqueue(), PersonaLoader, datetime.now() | Cron matching, deduplication, schedule state |
| ApprovalGate | DB session, notification channels | Risk resolution, persona override merging |
| PersonaLoader | Filesystem (YAML reads) | Deep merge, validation, inheritance |
| LLMRouter extensions | LLM API calls (provider clients) | Reflection loop, planning step execution, cost tracking |
| API routes | Conductor, DB session | Request validation, response serialization, SSE streaming |

**Principle**: Each layer mocks the layer directly below it. Integration tests use real instances of 2+ layers with only external services mocked (LLM APIs, Neo4j, filesystem).

## Numeric Thresholds & Defaults

Configurable values referenced across the spec and their defaults:

| Parameter | Default | Configurable Via | Spec Reference |
|-----------|---------|-----------------|----------------|
| `max_iterations` (specialist) | 10 | Task params | agentic-analysis.21 |
| `max_plan_steps` (conductor) | 5 | Task params | agentic-analysis.21 |
| `cost_limit` (per task) | $1.00 | Task params, schedule | agentic-analysis.21 |
| `task_timeout` | 10 min | Schedule, task submission | agentic-analysis.23, .28 |
| `sub_task_timeout` | 3 min | Task params | agentic-analysis.23 |
| `max_retries` (specialist) | 2 | approval.yaml | agentic-analysis.23 |
| `retry_backoff_base` | 2s | Not configurable | agentic-analysis.23 |
| `approval_timeout` | 24 hours | approval.yaml | agentic-analysis.27 |
| `rrf_k_constant` | 60 | Not configurable | agentic-analysis.22 |
| `rrf_min_score` | 0.01 | Not configurable | agentic-analysis.22 |
| `memory_max_results` | 20 | Task params | agentic-analysis.22 |
| `circuit_breaker_cooldown` | 60s | Not configurable | agentic-analysis.26 |
| `confidence_high` | >= 0.8 | Not configurable | agentic-analysis.20 |
| `confidence_moderate` | 0.5–0.79 | Not configurable | agentic-analysis.20 |
| `confidence_speculative` | < 0.3 | Not configurable | agentic-analysis.20 |
| `graph_weight` | 0.4 | MemoryProvider config | agentic-analysis.22 |
| `vector_weight` | 0.4 | MemoryProvider config | agentic-analysis.22 |
| `keyword_weight` | 0.2 | MemoryProvider config | agentic-analysis.22 |
