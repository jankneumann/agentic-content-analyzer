# Spec: Agentic Analysis Agent

**Capability**: `agentic-analysis`
**Status**: Draft

## Overview

An autonomous analysis layer that uses a Conductor + Specialist agent topology to proactively identify AI trends, perform deep research on demand, and generate novel insights by connecting information across the knowledge base. Built on top of the existing LLMRouter tool-calling infrastructure with an abstracted memory provider and tiered approval gates.

## Scenarios

### Conductor Agent

#### agentic-analysis.1 — User submits a research task
**Given** a user submits a task via API or CLI (e.g., "What are the emerging trends in AI agents for enterprise?")
**When** the conductor receives the task
**Then** it SHALL:
  - Create an `agent_tasks` record with status `received`
  - Load the active persona configuration
  - Query the memory provider for relevant prior research
  - Use `LLMRouter.generate_with_planning()` to decompose the goal into sub-tasks
  - Update status to `planning`, then `delegating`
  - Delegate each sub-task to the appropriate specialist
  - Monitor specialist completion and synthesize results
  - Store the final result and any generated insights
  - Update status to `completed`

#### agentic-analysis.2 — Heartbeat triggers a proactive task
**Given** the heartbeat scheduler determines a scheduled task is due
**When** it enqueues an `agent_task` job
**Then** the conductor SHALL handle it identically to a user task, except:
  - The `source` field is `heartbeat` (not `user`)
  - Priority is as configured in `heartbeat.yaml`
  - If a previous run of the same schedule is still active, the new task SHALL be skipped

#### agentic-analysis.3 — Task requires human approval
**Given** a specialist needs to perform a HIGH or CRITICAL risk action
**When** it calls `request_approval(action, context, risk_level)`
**Then** the system SHALL:
  - Create an `approval_requests` record with status `pending`
  - Set the parent task status to `blocked`
  - Notify the user via configured notification channels
  - Wait for user decision (approve/deny)
  - On approval: resume the task from where it was blocked
  - On denial: pass the denial reason to the conductor for re-planning

#### agentic-analysis.4 — Task failure and recovery
**Given** a specialist fails during execution
**When** the conductor receives the failure notification
**Then** it SHALL:
  - Log the error with full context
  - Decide whether to retry, delegate to a different specialist, or adjust the plan
  - If all retries exhausted: mark task as `failed` with error details
  - Store any partial results as insights with reduced confidence

### Specialist Agents

#### agentic-analysis.5 — Research specialist performs deep investigation
**Given** the conductor delegates a research sub-task
**When** the ResearchSpecialist receives it
**Then** it SHALL:
  - Use its own tool-calling loop to plan and execute research steps
  - Available tools: `search_content`, `query_knowledge_graph`, `search_web`, `fetch_url`
  - Respect the iteration budget (max_iterations from task or default)
  - Return structured findings with sources and confidence scores
  - Store research observations as memories via the memory provider

#### agentic-analysis.6 — Analysis specialist detects trends
**Given** the conductor delegates a trend analysis sub-task
**When** the AnalysisSpecialist receives it
**Then** it SHALL:
  - Invoke ThemeAnalyzer for the specified date range
  - Invoke HistoricalContextAnalyzer for temporal enrichment
  - Use its reasoning loop to identify anomalies and emerging patterns
  - Return structured themes with trend classifications and confidence
  - Cross-reference with memory provider for historical comparisons

#### agentic-analysis.7 — Synthesis specialist generates insights
**Given** the conductor provides research and analysis results for synthesis
**When** the SynthesisSpecialist receives them
**Then** it SHALL:
  - Identify novel connections between themes, entities, and time periods
  - Generate structured insights with titles, content, confidence, and tags
  - Format output according to persona preferences (depth, perspective, style)
  - Store insights in `agent_insights` table
  - Optionally draft a digest or briefing if requested

#### agentic-analysis.8 — Ingestion specialist acquires content
**Given** the conductor delegates a content acquisition sub-task
**When** the IngestionSpecialist receives it
**Then** it SHALL:
  - Request approval for medium-risk ingestion actions
  - Invoke the appropriate ingestion service(s)
  - Report back the count and summary of new content acquired
  - Trigger summarization for new content if requested

### Memory Provider

#### agentic-analysis.9 — Store and recall with hybrid strategy
**Given** an agent stores a memory entry
**When** a subsequent recall query is made
**Then** the memory provider SHALL:
  - Query all configured strategies (graph, vector, keyword) in parallel
  - Merge results using weighted Reciprocal Rank Fusion
  - Apply recency and frequency weighting to the merged results
  - Return deduplicated, ranked memory entries
  - Update `access_count` and `last_accessed_at` for returned entries

#### agentic-analysis.10 — Memory strategy configuration
**Given** a memory provider is initialized with a strategy configuration
**When** strategies are loaded
**Then** the provider SHALL:
  - Support any combination of: `graph`, `vector`, `keyword`
  - Accept per-strategy weight configuration (0.0 to 1.0)
  - Gracefully degrade if a backend is unavailable (e.g., Neo4j down → skip graph strategy)
  - Log warnings for unavailable strategies without failing

### Heartbeat Scheduler

#### agentic-analysis.11 — Schedule execution
**Given** a heartbeat schedule is defined in `heartbeat.yaml`
**When** the current time matches the cron expression
**Then** the scheduler SHALL:
  - Check if a previous run of this schedule is still active (skip if so)
  - Enqueue an `agent_task` job with the configured parameters
  - Update `last_run_at` and compute `next_run_at` in `heartbeat_schedules`
  - Log the enqueued task

#### agentic-analysis.12 — Schedule management
**Given** a user wants to manage heartbeat schedules
**Then** the system SHALL support:
  - Enabling/disabling individual schedules via API or CLI
  - Viewing schedule status (last run, next run, last status)
  - Manually triggering a scheduled task outside its normal schedule
  - Modifying schedules by editing `heartbeat.yaml` (hot-reload on SIGHUP or API call)

### Approval Gates

#### agentic-analysis.13 — Risk classification
**Given** a specialist is about to execute an action
**When** the action is checked against `approval.yaml`
**Then** the system SHALL:
  - Look up the action's configured risk level
  - For LOW: execute immediately, no logging beyond standard OTel
  - For MEDIUM: execute immediately, log to audit trail
  - For HIGH: block and request approval
  - For CRITICAL: block, request approval, create full audit entry
  - For unconfigured actions: default to MEDIUM

### Agent Persona

#### agentic-analysis.14 — Persona loading and application
**Given** a persona configuration exists in `settings/persona.yaml`
**When** the conductor initializes for a task
**Then** it SHALL:
  - Load persona via ConfigRegistry (supporting env var / DB overrides)
  - Inject persona context into the conductor's system prompt
  - Pass relevant persona attributes to specialists (domain focus, depth preference)
  - Store a snapshot of the active persona in the task record

### API Endpoints

#### agentic-analysis.15 — Task submission and tracking
**Given** a user interacts with the agent API
**Then** the following endpoints SHALL be available:
  - `POST /api/v1/agent/task` — Submit a task (returns task ID)
  - `GET /api/v1/agent/task/{id}` — Get task status, plan, and results
  - `GET /api/v1/agent/tasks` — List tasks with filtering (status, source, date range)
  - `DELETE /api/v1/agent/task/{id}` — Cancel a running task
  - `GET /api/v1/agent/insights` — List generated insights with filtering
  - `GET /api/v1/agent/insights/{id}` — Get a specific insight
  - `POST /api/v1/agent/approval/{id}` — Approve or deny an approval request
  - `GET /api/v1/agent/schedules` — List heartbeat schedules and status

#### agentic-analysis.16 — SSE progress streaming
**Given** a user submits a task via API
**When** they request progress updates
**Then** the system SHALL provide SSE streaming of:
  - Task status changes
  - Specialist delegation events
  - Intermediate findings
  - Approval requests
  - Final results

### CLI Commands

#### agentic-analysis.17 — Agent CLI interface
**Given** a user interacts via CLI
**Then** the following commands SHALL be available:
  - `aca agent task "prompt"` — Submit a research/analysis task
  - `aca agent status [task-id]` — View task status and progress
  - `aca agent insights [--type TYPE] [--since DATE]` — Browse insights
  - `aca agent schedule [--enable|--disable SCHEDULE_ID]` — Manage schedules
  - `aca agent approve <request-id>` — Approve a pending request
  - `aca agent deny <request-id> --reason "..."` — Deny with reason

### LLMRouter Extensions

#### agentic-analysis.18 — Enhanced tool calling
**Given** `generate_with_tools()` is called with new parameters
**Then** the router SHALL:
  - Support `enable_reflection=True` for post-loop self-review
  - Support `memory_context` parameter for injecting recalled memories
  - Support `cost_limit` to abort if LLM costs exceed threshold
  - Remain fully backward-compatible (new params are optional with defaults)

#### agentic-analysis.19 — Planning method
**Given** `generate_with_planning()` is called
**Then** the router SHALL:
  - First ask the model to create an explicit step-by-step plan
  - Execute each plan step via `generate_with_tools()`
  - Allow the model to revise the plan based on intermediate results
  - Track total cost and tokens across all plan steps
