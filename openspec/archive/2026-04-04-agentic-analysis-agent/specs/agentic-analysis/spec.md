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

#### agentic-analysis.2 — Scheduler triggers a proactive task
**Given** the current time matches a cron expression in `settings/schedule.yaml`
**When** the scheduler enqueues an `agent_task` job with the schedule's `persona`, `output`, `sources`, and `params`
**Then** the conductor SHALL handle it identically to a user task, except:
  - The `source` field is `schedule` (not `user`)
  - Priority is as configured in the schedule entry
  - If a previous run of the same schedule is still in_progress or delegating, the scheduler SHALL skip enqueuing a new task

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
  - Check each ingestion action against the approval gate (actions classified as MEDIUM or higher in `approval.yaml` or persona overrides)
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
**Given** a memory provider is initialized with a strategy configuration dict (e.g., `{"graph": 0.4, "vector": 0.4, "keyword": 0.2}`)
**When** the provider validates and instantiates each configured strategy
**Then** the provider SHALL:
  - Support any combination of: `graph`, `vector`, `keyword`
  - Accept per-strategy weight configuration (0.0 to 1.0)
  - Gracefully degrade if a backend is unavailable (e.g., Neo4j down → skip graph strategy)
  - Log warnings for unavailable strategies without failing

### Proactive Scheduler

#### agentic-analysis.11 — Schedule execution
**Given** a schedule is defined in `settings/schedule.yaml`
**When** the current time matches the cron expression
**Then** the scheduler SHALL:
  - Check if a previous run of this schedule is still active (skip if so)
  - Enqueue an `agent_task` job with the schedule's `persona`, `output`, `sources`, and `params`
  - Update `last_run_at` and compute `next_run_at` in `agent_schedules`
  - Log the enqueued task with persona and output information

#### agentic-analysis.12 — Schedule management
**Given** a user wants to manage schedules
**Then** the system SHALL support:
  - Enabling/disabling individual schedules via API or CLI
  - Viewing schedule status (last run, next run, last status, persona used)
  - Manually triggering a scheduled task outside its normal schedule (with optional persona/output override)
  - Modifying schedules by editing `settings/schedule.yaml` (hot-reload on SIGHUP or API call)

#### agentic-analysis.12a — Schedule-level source filtering
**Given** a schedule specifies a `sources` field (e.g., `[arxiv, scholar]`)
**When** the conductor executes the scheduled task
**Then** it SHALL restrict content retrieval and analysis to only those source types, allowing the same persona to produce different analyses from different content subsets

### Approval Gates

#### agentic-analysis.13 — Risk classification with persona overrides
**Given** a specialist is about to execute an action under a specific persona
**When** the action is checked against approval configuration
**Then** the system SHALL:
  - Resolve effective risk level: persona `approval_overrides` > base `approval.yaml` > default MEDIUM
  - For LOW: execute immediately, no logging beyond standard OTel
  - For MEDIUM: execute immediately, log to audit trail
  - For HIGH: block and request approval
  - For CRITICAL: block, request approval, create full audit entry
  - Persona overrides can only lower risk levels, never escalate them

### Agent Persona

#### agentic-analysis.14 — Multi-persona loading and application
**Given** persona configurations exist in `settings/personas/` directory
**When** the conductor initializes for a task with a persona name
**Then** it SHALL:
  - Load the named persona YAML, inheriting missing fields from `default.yaml`
  - Resolve model overrides for each specialist step (persona override > global MODEL_* default)
  - Apply tool restrictions (filter out tools listed in `restricted_tools`)
  - Configure approval gate with persona's `approval_overrides`
  - Resolve output format (schedule override > persona `output_defaults.default_format`)
  - Inject persona context (name, role, domain_focus, communication_style) into the conductor's system prompt
  - Store `persona_name` and a full persona config snapshot in the task record for reproducibility

#### agentic-analysis.14a — Persona listing
**Given** a user wants to see available personas
**Then** the system SHALL:
  - List all YAML files in `settings/personas/` by name
  - Display each persona's name, role, and domain focus summary
  - Available via both API (`GET /api/v1/agent/personas`) and CLI (`aca agent personas`)

### API Endpoints

#### agentic-analysis.15 — Task submission and tracking
**Given** the FastAPI application is running with the agent router registered
**When** a user sends HTTP requests to agent endpoints
**Then** the following endpoints SHALL be available:
  - `POST /api/v1/agent/task` — Submit a task (accepts optional `persona`, `output`, `sources` params; returns task ID)
  - `GET /api/v1/agent/task/{id}` — Get task status, plan, and results
  - `GET /api/v1/agent/tasks` — List tasks with filtering (status, source, date range, persona)
  - `DELETE /api/v1/agent/task/{id}` — Cancel a running task
  - `GET /api/v1/agent/insights` — List generated insights with filtering
  - `GET /api/v1/agent/insights/{id}` — Get a specific insight
  - `POST /api/v1/agent/approval/{id}` — Approve or deny an approval request
  - `GET /api/v1/agent/schedules` — List schedules and status
  - `GET /api/v1/agent/personas` — List available personas with summary

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
  - `aca agent task "prompt" [--persona NAME] [--output FORMAT] [--sources SRC,SRC]` — Submit a task with optional persona, output format, and source filter
  - `aca agent status [task-id]` — View task status and progress
  - `aca agent insights [--type TYPE] [--since DATE] [--persona NAME]` — Browse insights
  - `aca agent personas` — List available personas with summary
  - `aca agent schedule [--enable|--disable SCHEDULE_ID]` — Manage schedules
  - `aca agent approve <request-id>` — Approve a pending request
  - `aca agent deny <request-id> --reason "..."` — Deny with reason

### LLMRouter Extensions

### Measurement & Thresholds

#### agentic-analysis.20 — Confidence scoring
**Given** any agent component produces a confidence value
**Then** the following scale SHALL apply:
  - Confidence is a float in `[0.0, 1.0]`
  - `>= 0.8` — high confidence (suitable for automated actions)
  - `0.5 – 0.79` — moderate confidence (suitable for human review)
  - `< 0.5` — low confidence (flagged as uncertain)
  - Insights stored with `confidence < 0.3` SHALL be tagged as `speculative`

#### agentic-analysis.21 — Iteration and cost budgets
**Given** a specialist or conductor executes a reasoning loop
**Then** the following defaults SHALL apply (overridable per task):
  - `max_iterations`: 10 (per specialist tool loop)
  - `max_plan_steps`: 5 (per conductor planning phase)
  - `cost_limit`: $1.00 USD (per individual task, including sub-tasks)
  - When `cost_limit` is exceeded, the task SHALL terminate gracefully with partial results and status `failed` with error `cost_limit_exceeded`
  - When `max_iterations` is exceeded, the specialist SHALL return its best current result with a reduced confidence score (multiplied by 0.7)

#### agentic-analysis.22 — Reciprocal Rank Fusion (RRF) formula
**Given** the memory provider merges results from multiple strategies
**Then** it SHALL use weighted RRF with the formula:
  - `score(d) = Σ_s (weight_s / (k + rank_s(d)))` where `k = 60` (standard RRF constant)
  - Default weights: `graph = 0.4`, `vector = 0.4`, `keyword = 0.2`
  - Results with `score < 0.01` SHALL be filtered out
  - Maximum returned entries: 20 (unless caller specifies a different limit)

#### agentic-analysis.23 — Retry policy
**Given** a specialist fails during execution
**Then** the conductor SHALL apply this retry policy:
  - Maximum retries per specialist: 2
  - Backoff: exponential with base 2 seconds (2s, 4s)
  - A different specialist MAY be tried if the original fails all retries
  - Total task timeout: 10 minutes (configurable per schedule or task submission)
  - Sub-task timeout: 3 minutes per specialist invocation

### Error Handling

#### agentic-analysis.24 — Specialist execution failure
**Given** a specialist raises an unhandled exception during execution
**When** the conductor receives the failure
**Then** it SHALL:
  - Log the exception with full traceback and task context
  - Apply the retry policy (agentic-analysis.23)
  - If all retries exhausted: store any partial results as insights with `confidence` multiplied by 0.5
  - Mark the sub-task as `failed` with the error message
  - Decide whether the parent task can still complete (partial success) or must also fail
  - A parent task with >= 1 successful sub-task and >= 1 failed sub-task SHALL be marked `completed` with `metadata.partial = true`

#### agentic-analysis.25 — Tool execution failure within specialist
**Given** a tool call within a specialist's reasoning loop raises an error
**When** the specialist receives the tool error
**Then** it SHALL:
  - Include the error in the conversation context for the LLM to reason about
  - Allow the LLM to decide: retry the tool, try an alternative tool, or return partial results
  - NOT automatically retry the same tool call with identical parameters
  - After 3 consecutive tool failures, abort the specialist and return partial results

#### agentic-analysis.26 — Memory backend unavailability
**Given** a memory strategy backend is unavailable (e.g., Neo4j down, pgvector timeout)
**When** the memory provider attempts to query that strategy
**Then** it SHALL:
  - Log a warning with the strategy name and error details
  - Skip the unavailable strategy and continue with remaining strategies
  - If all strategies are unavailable, return an empty result set (not an error)
  - Recalculate RRF weights among available strategies (redistribute proportionally)
  - Set a circuit breaker: skip the failed strategy for 60 seconds before retrying

#### agentic-analysis.27 — Approval request timeout
**Given** an approval request is created for a HIGH or CRITICAL action
**When** no human decision is received within the configured timeout
**Then** the system SHALL:
  - Default approval timeout: 24 hours (configurable)
  - After timeout: mark the approval as `expired`
  - Notify the conductor that the approval expired
  - The conductor SHALL treat an expired approval as a denial and re-plan without the blocked action

#### agentic-analysis.28 — Task timeout
**Given** a task has been running longer than its configured timeout
**When** the timeout is reached
**Then** the system SHALL:
  - Send a cancellation signal to the active specialist
  - Allow the specialist 30 seconds for graceful shutdown (store partial results)
  - Mark the task as `failed` with error `task_timeout`
  - Store any partial results or insights generated before timeout

### Integration with Existing Components

#### agentic-analysis.29 — LLMRouter backward compatibility
**Given** the LLMRouter is extended with new parameters
**When** existing callers invoke `generate_with_tools()` without new parameters
**Then** behavior SHALL be identical to the current implementation — no reflection, no memory injection, no cost tracking

#### agentic-analysis.30 — Pipeline Runner integration
**Given** the IngestionSpecialist delegates to the existing pipeline
**When** it requests a partial pipeline run (e.g., ingest-only)
**Then** it SHALL:
  - Call the existing pipeline runner with stage-specific parameters
  - Accept optional date ranges, source filters, and focus topics from the conductor
  - Return pipeline results (counts, errors) to the specialist for reporting back to the conductor
  - NOT modify the pipeline runner's existing behavior for full runs

#### agentic-analysis.31 — Job queue agent_task entrypoint
**Given** a new `agent_task` job type is registered with PGQueuer
**When** the worker picks up an `agent_task` job
**Then** it SHALL:
  - Instantiate a Conductor with the task's persona and parameters
  - Execute the task via the conductor's state machine
  - Track the job as a PGQueuer entry with standard retry/failure handling
  - NOT interfere with existing job types (`daily_pipeline`, `send_notification`, etc.)

### LLMRouter Extensions

#### agentic-analysis.18 — Enhanced tool calling
**Given** `generate_with_tools()` is called with new parameters
**Then** the router SHALL:
  - Support `enable_reflection=True` for post-loop self-review
  - Support `memory_context` parameter for injecting recalled memories
  - Support `cost_limit` to abort if LLM costs exceed threshold
  - Remain fully backward-compatible (new params are optional with defaults)

#### agentic-analysis.19 — Planning method
**Given** `generate_with_planning()` is called with a goal, tools, and tool executor
**When** the router begins the planning phase
**Then** the router SHALL:
  - First ask the model to create an explicit step-by-step plan (max `max_plan_steps` steps, default 5)
  - Execute each plan step via `generate_with_tools()` with the step's sub-goal
  - After each step, present intermediate results to the model and allow plan revision (max 2 revisions per plan)
  - Track total cost and tokens across all plan steps (subject to `cost_limit`)
  - If cost_limit is reached mid-plan, return results from completed steps with `partial = true`
