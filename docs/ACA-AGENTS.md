# Agentic Analysis System

The agentic analysis system provides autonomous, persona-driven analysis of ingested content. A **Conductor** orchestrates tasks by decomposing them into sub-tasks, delegating to specialist agents, and synthesizing results into actionable insights.

## Quick Start

```bash
# Submit an analysis task
aca agent task "What are the emerging trends in AI agents?" --persona ai-ml-technology

# Check status
aca agent status <task-id>

# Browse generated insights
aca agent insights --type trend

# List available personas
aca agent personas
```

## Architecture Overview

```
User / Schedule
      |
  [API / CLI]
      |
  [Queue Worker]  ── execute_agent_task entrypoint
      |
  [Conductor]  ← PersonaLoader, MemoryProvider, ApprovalGate
      |
  [Plan]  ← LLMRouter.generate_with_planning()
      |
  [Specialist Registry]
      |
  ┌───┴───┬──────────┬──────────┐
  │       │          │          │
Analysis Research Synthesis Ingestion
  │       │          │          │
  └───┬───┴──────────┴──────────┘
      |
  [Synthesize Results]
      |
  [Store Insights + Memory]
      |
  ConductorResult → DB
```

**Key components:**

| Component | Location | Purpose |
|-----------|----------|---------|
| Conductor | `src/agents/conductor.py` | Task lifecycle orchestration (7-state machine) |
| Specialists | `src/agents/specialists/` | Domain-specific tool-using agents (4 built-in) |
| Memory Provider | `src/agents/memory/` | Hybrid recall with vector, keyword, and graph strategies |
| Persona System | `src/agents/persona/` | YAML-configured analysis perspectives |
| Approval Gates | `src/agents/approval/gates.py` | Risk-tiered action control |
| Scheduler | `src/agents/scheduler/` | Cron-driven proactive task execution |
| Service Layer | `src/services/agent_service.py` | DB CRUD for tasks, insights, approvals |
| API Routes | `src/api/agent_routes.py` | 11 REST endpoints under `/api/v1/agent/` |
| CLI Commands | `src/cli/agent_commands.py` | 7 commands under `aca agent` |
| Queue Handler | `src/queue/worker.py` | `execute_agent_task` bridges queue to Conductor |

## Setup

### Prerequisites

The agent system builds on the existing stack. Ensure you have:

```bash
source .venv/bin/activate
docker compose up -d        # PostgreSQL + Neo4j
alembic upgrade head        # Creates agent_tasks, agent_insights, agent_memories,
                            # approval_requests, agent_schedules tables
```

### Required Environment Variables

The agent system uses the same LLM providers as the rest of the pipeline. At minimum:

```bash
ANTHROPIC_API_KEY=sk-ant-...    # For Claude models (conductor planning, specialists)
```

Optional but recommended:

```bash
GOOGLE_AI_API_KEY=...           # For Gemini models (large context analysis)
OPENAI_API_KEY=...              # For GPT models and embeddings
TAVILY_API_KEY=...              # For web search tool (search_web)
NEO4J_URL=bolt://localhost:7687 # For graph memory strategy
```

### Worker Configuration

Agent tasks execute asynchronously via the queue worker. The worker starts automatically with the API server when `WORKER_ENABLED=true` (default):

```bash
# Embedded worker (default — runs inside the API process)
WORKER_ENABLED=true             # Enable/disable (default: true)
WORKER_CONCURRENCY=5            # Max concurrent jobs (default: 5)

# Standalone worker (alternative)
aca worker start
```

## Configuration

### Personas

Personas define the analysis perspective — what to focus on, how deep to go, and which models/tools to use. Stored in `settings/personas/`.

**Built-in personas:**

| Persona | Focus | Depth | Perspective |
|---------|-------|-------|-------------|
| `default` | AI, ML, data engineering | thorough | both tactical + strategic |
| `ai-ml-technology` | ML, deep learning, NLP, CV | exhaustive | tactical |
| `leadership` | Business strategy, AI adoption | brief | strategic |

**Creating a custom persona:**

Create `settings/personas/<name>.yaml`:

```yaml
name: "Security Analyst"
role: "Cybersecurity threat intelligence analyst focused on AI security"

domain_focus:
  primary: [AI security, adversarial ML, LLM vulnerabilities]
  secondary: [supply chain security, zero-trust architecture]

analysis_preferences:
  depth: thorough          # brief | thorough | exhaustive
  perspective: tactical    # tactical | strategic | both
  time_horizon: 3_months   # How far back to look for trends
  novelty_bias: 0.7        # 0.0 = conservative, 1.0 = novelty-seeking

relevance_weighting:       # Must sum to 1.0
  strategic_impact: 0.2
  technical_depth: 0.4
  novelty: 0.3
  cross_domain_relevance: 0.1

output_defaults:
  default_format: technical_report   # technical_report | executive_briefing | ...
  include_code_examples: true
  include_sources: true
  max_insight_length: 2000

communication_style:
  tone: precise
  format: structured
  audience: security engineers

# Optional: override which LLM models are used
model_overrides:
  theme_analysis: claude-sonnet-4-5
  summarization: claude-haiku-4-5

# Optional: override approval risk levels (can only LOWER, never escalate)
approval_overrides:
  store_graph_episode: medium    # Default is high

# Optional: restrict which tools specialists can use
restricted_tools:
  - fetch_url              # Disable URL fetching for this persona
```

Personas inherit from `default.yaml` — you only need to specify overrides.

### Schedules

Proactive scheduled tasks in `settings/schedule.yaml`:

```yaml
schedules:
  # Run trend detection every morning at 9 AM UTC
  trend_detection_tech:
    cron: "0 9 * * *"            # Standard 5-field cron
    task_type: analysis
    persona: ai-ml-technology
    output: technical_report
    priority: medium
    enabled: true

  # Weekly synthesis every Monday at 10 AM UTC
  weekly_synthesis_leadership:
    cron: "0 10 * * MON"
    task_type: synthesis
    persona: leadership
    output: executive_briefing
    priority: medium

  # Scan for new content every 4 hours
  scan_sources:
    cron: "0 */4 * * *"
    task_type: ingestion
    priority: low
```

The scheduler checks for due tasks on each tick (called from the API server lifespan). It supports:
- **Deduplication**: Won't re-enqueue if the same schedule already ran this minute
- **Active task tracking**: Won't enqueue if the previous run is still in progress
- **Hot-reload**: Detects file changes and reloads without restart

Manage schedules via CLI:

```bash
aca agent schedule                        # List all schedules
aca agent schedule --enable scan_sources  # Enable a schedule
aca agent schedule --disable scan_sources # Disable a schedule
```

### Approval Gates

Risk-tiered action control in `settings/approval.yaml`:

```yaml
risk_levels:
  # LOW — auto-approved silently
  search_content: low
  query_knowledge_graph: low
  analyze_themes: low

  # MEDIUM — auto-approved with logging
  ingest_source: medium
  summarize_content: medium
  run_pipeline: medium

  # HIGH — blocked, requires human approval
  create_digest: high
  send_email: high
  publish_digest: high

  # CRITICAL — blocked, requires approval + audit trail
  delete_content: critical
  modify_agent_config: critical
  bulk_operations: critical
```

When a specialist attempts a HIGH or CRITICAL action, the task enters `blocked` status. Approve or deny via:

```bash
aca agent approve <request-id>
aca agent deny <request-id> --reason "Too broad — narrow the scope"
```

Or via API:

```bash
curl -X POST http://localhost:8000/api/v1/agent/approval/<request-id> \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -d '{"approved": true, "reason": "Verified safe"}'
```

Approved tasks automatically resume execution.

## CLI Reference

All commands are under `aca agent`:

```bash
# Submit a task
aca agent task "Analyze trends in autonomous coding agents" \
  --type analysis \
  --persona ai-ml-technology \
  --output technical_report \
  --sources "arxiv,scholar"

# Check task status (single or recent list)
aca agent status                    # List recent tasks
aca agent status <task-id>          # Detailed view of one task

# Browse insights
aca agent insights                  # All recent insights
aca agent insights --type trend     # Filter by type
aca agent insights --since 2026-01-01  # Filter by date
aca agent insights --persona leadership  # Filter by persona

# Manage personas and schedules
aca agent personas                  # List available personas
aca agent schedule                  # List schedules

# Approval workflow
aca agent approve <request-id>
aca agent deny <request-id> --reason "Explanation"
```

All commands support `--json` for machine-readable output:

```bash
aca agent task "Analyze trends" --json | jq '.task_id'
```

## API Reference

Base path: `/api/v1/agent/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/task` | Submit a new task |
| GET | `/task/{task_id}` | Get task status and result |
| GET | `/tasks` | List tasks (filters: `status`, `persona`, `limit`, `offset`) |
| DELETE | `/task/{task_id}` | Cancel a task |
| GET | `/task/{task_id}/stream` | SSE stream of task progress |
| GET | `/insights` | List insights (filters: `insight_type`, `since`, `persona`) |
| GET | `/insights/{insight_id}` | Get a single insight |
| POST | `/approval/{request_id}` | Approve or deny a request |
| GET | `/schedules` | List all schedules |
| POST | `/schedules/{id}/enable` | Enable a schedule |
| POST | `/schedules/{id}/disable` | Disable a schedule |
| GET | `/personas` | List available personas |

All endpoints require authentication via `X-Admin-Key` header.

**Submit task example:**

```bash
curl -X POST http://localhost:8000/api/v1/agent/task \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -d '{
    "prompt": "What are the key developments in multimodal AI this week?",
    "task_type": "research",
    "persona": "ai-ml-technology",
    "params": {"lookback_days": 7}
  }'
```

**SSE streaming:**

```bash
curl -N http://localhost:8000/api/v1/agent/task/<task-id>/stream \
  -H "X-Admin-Key: $ADMIN_API_KEY"
```

Returns Server-Sent Events with `{"task_id", "status", "result", "error_message"}` every second until the task reaches a terminal state.

## Specialists

Four built-in specialists, each with their own tools and reasoning loop:

### Analysis Specialist

Detects themes, trends, and anomalies.

| Tool | Description | Status |
|------|-------------|--------|
| `analyze_themes` | Theme detection across content | Wired to ThemeAnalyzer |
| `get_historical_context` | Historical context for a topic | Wired to HistoricalContextAnalyzer |
| `detect_anomalies` | Anomaly detection in content trends | Queries Content DB + LLM analysis |
| `compare_periods` | Compare themes between time periods | Two-window content count comparison |

### Research Specialist

Deep research with iterative tool use.

| Tool | Description | Status |
|------|-------------|--------|
| `search_content` | Hybrid BM25+vector search | Wired to HybridSearchService |
| `query_knowledge_graph` | Neo4j knowledge graph queries | Wired to GraphitiClient |
| `search_web` | Web search for external context | Wired to WebSearchProvider (Tavily/Perplexity/Grok) |
| `fetch_url` | Fetch and extract URL content | httpx + html_to_text (5000 char limit) |

### Synthesis Specialist

Combines research and analysis into reports.

| Tool | Description | Status |
|------|-------------|--------|
| `create_report` | Structured report from findings | LLM-generated |
| `generate_insight` | Single insight from observations | LLM-generated |
| `draft_digest` | Draft a daily/weekly digest | Wired to DigestCreator |
| `create_briefing` | Concise topic briefing | LLM-generated |

### Ingestion Specialist

Manages content ingestion from sources.

| Tool | Description | Status |
|------|-------------|--------|
| `ingest_source` | Ingest from configured source | Wired to ingestion orchestrator |
| `scan_sources` | Scan sources for new content | Wired to ingestion orchestrator |
| `ingest_url` | Ingest from a specific URL | Wired to ingestion orchestrator |

## Memory System

The agent maintains persistent memory across tasks using three strategies combined via weighted Reciprocal Rank Fusion (RRF):

| Strategy | Backend | Strengths |
|----------|---------|-----------|
| **Vector** | pgvector (PostgreSQL) | Semantic similarity with recency boosting |
| **Keyword** | PostgreSQL FTS | Exact term matching, BM25 ranking |
| **Graph** | Neo4j (Graphiti) | Entity relationships, temporal context |

Memory is stored in the `agent_memories` table with types:
- `observation` — raw observations from tool calls
- `insight` — generated insights (stored after task completion)
- `task_result` — summarized task outcomes
- `preference` — learned user preferences
- `meta_learning` — patterns about what works well

The memory provider features:
- **Circuit breaker**: Failed strategies are skipped for 60 seconds
- **Graceful degradation**: If all strategies fail, returns empty (doesn't block)
- **Access tracking**: `access_count` and `last_accessed_at` updated on recall

## Best Practices

### Task Design

- **Be specific in prompts**: "Analyze trends in autonomous coding agents over the last 2 weeks" is better than "What's new in AI?"
- **Choose the right task type**: `research` for fact-finding, `analysis` for pattern detection, `synthesis` for report generation, `ingestion` for content gathering
- **Match persona to audience**: Use `ai-ml-technology` for technical deep-dives, `leadership` for executive summaries

### Persona Configuration

- **Start with defaults**: The built-in personas cover most use cases. Create custom personas only when the analysis perspective genuinely differs.
- **Keep weights balanced**: `relevance_weighting` values must sum to 1.0. Extreme weights (e.g., 0.9 on one dimension) produce skewed results.
- **Use model overrides sparingly**: The defaults are tuned for cost/quality balance. Override only when you need specific capabilities (e.g., Gemini for large context).
- **Tool restrictions are for safety**: `restricted_tools` prevents a persona from using tools that don't match its purpose (e.g., a read-only analyst shouldn't ingest content).

### Approval Workflow

- **Review pending approvals regularly**: Blocked tasks wait indefinitely. Check with `aca agent status` or the API.
- **Prefer MEDIUM over HIGH for iterative work**: HIGH blocks execution entirely. MEDIUM auto-approves with an audit log, which is usually sufficient for development.
- **Never lower CRITICAL actions**: Approvals for `delete_content`, `modify_agent_config`, and `bulk_operations` should always require explicit human approval.

### Scheduling

- **Stagger scheduled tasks**: Don't schedule multiple analysis tasks at the same minute — they compete for LLM rate limits.
- **Use appropriate priority levels**: `low` for background maintenance, `medium` for regular analysis, `high` for time-sensitive reports.
- **Monitor active tasks**: The scheduler won't re-enqueue a task if the previous run is still active. Long-running tasks can silently block scheduled execution.

### Cost Management

- **Monitor `cost_total`**: Each task tracks estimated LLM cost. Check via `aca agent status <id>` or the API.
- **Use Haiku for ingestion**: The ingestion specialist defaults to `claude-haiku-4-5` — the cheapest option for source scanning.
- **Set cost limits for expensive tasks**: The LLM router supports `cost_limit` to cap multi-step operations.

### Memory

- **Memory is cross-task**: Insights from one task are available to future tasks. Over time, the system builds up domain knowledge.
- **Vector strategy requires embeddings**: If `sentence-transformers` is not installed, vector memory degrades to keyword-only (BM25 still works).
- **Graph strategy requires Neo4j**: If Neo4j is not running, graph memory is skipped (circuit breaker activates).

## Task Lifecycle

```
1. RECEIVED    — Task created in DB, enqueued to worker
2. PLANNING    — Conductor loads persona, queries memory, decomposes into sub-tasks
3. DELEGATING  — Sub-tasks dispatched to specialists with retry (2s, 4s backoff)
4. MONITORING  — All specialist results collected
5. SYNTHESIZING — Results merged, insights extracted
6. COMPLETED   — Final result + insights persisted to DB
```

**Error states:**
- `BLOCKED` — A specialist attempted a HIGH/CRITICAL action. Resumes on approval.
- `FAILED` — Unrecoverable error after all retries exhausted. Partial results may be available.

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Task stuck in `received` | Worker not running | Check `WORKER_ENABLED=true`, restart API |
| Task fails immediately | Missing API keys | Set `ANTHROPIC_API_KEY` (minimum) |
| `search_web` returns empty | No search provider configured | Set `TAVILY_API_KEY` or `WEB_SEARCH_PROVIDER` |
| `query_knowledge_graph` fails | Neo4j not running | `docker compose up -d neo4j` |
| Insights are empty | Findings below confidence threshold | Lower the threshold or use a more specific prompt |
| Schedule not triggering | `enabled: false` in YAML | `aca agent schedule --enable <id>` |
| Approval never arrives | Task not in `blocked` status | Only HIGH/CRITICAL actions create approval requests |
| Memory recall empty | No prior tasks completed | Run a few tasks first to build up memory |
| `LLMRouter` error | Missing `ModelConfig` | Ensure API keys are set in environment |

## Data Model

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `agent_tasks` | Task lifecycle tracking | id (UUID), status, task_type, persona_name, prompt, result (JSONB), cost_total |
| `agent_insights` | Generated findings | id (UUID), task_id (FK), insight_type, title, content, confidence |
| `agent_memories` | Persistent memory | id (UUID), memory_type, content, embedding (vector), content_tsv (tsvector) |
| `approval_requests` | Action approval workflow | id (UUID), task_id (FK), action, risk_level, status |
| `agent_schedules` | Proactive task schedules | id, cron, task_type, persona, enabled |

All tables use VARCHAR for enum fields (not native PG enums) so new values can be added without migrations.
