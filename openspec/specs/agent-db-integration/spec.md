# Agent DB Integration Specification

**Capability**: `agentic-analysis` (delta)
**Scope**: Database services, queue integration, API routes, CLI commands, SSE streaming

## Overview

Defines the data-access layer contracts for the agentic analysis agent: service classes that persist and query agent tasks, insights, and approval requests; the queue entrypoint that bridges PGQueuer to the Conductor lifecycle; the REST API surface; and the CLI commands.

## Service Contracts

### AgentTaskService

#### agent-db.1 -- create_task

The `create_task` method SHALL accept the following parameters:
- `db: Session` -- SQLAlchemy session
- `goal: str` -- the user's research prompt
- `source: str` -- `"user"` or `"schedule"`
- `persona_name: str` (default `"default"`) -- persona to use for execution
- `output_format: str | None` (default `None`) -- optional output format override
- `source_filter: list[str] | None` (default `None`) -- optional content source restriction
- `priority: str` (default `"medium"`) -- `low`, `medium`, `high`

It SHALL return an `AgentTask` ORM instance with:
- `status` set to `received`
- `created_at` set to current UTC time
- `persona_name` populated from the parameter
- A generated UUID `id`

It SHALL call `db.add()` and `db.flush()` to make the row visible within the same transaction.

#### agent-db.2 -- get_task

The `get_task` method SHALL accept `db: Session` and `task_id: str` (UUID).

It SHALL return `AgentTask | None`. When the task exists, the returned object SHALL include all columns including `result` (JSON) and `metadata` (JSON). When no task matches, it SHALL return `None` (not raise an exception).

#### agent-db.3 -- list_tasks

The `list_tasks` method SHALL accept:
- `db: Session`
- `status: str | None` -- filter by task status enum value
- `source: str | None` -- filter by `"user"` or `"schedule"`
- `persona_name: str | None` -- filter by persona
- `since: datetime | None` -- filter `created_at >= since`
- `limit: int` (default `50`)
- `offset: int` (default `0`)

It SHALL return `list[AgentTask]` ordered by `created_at` descending.

All filter parameters are optional and additive (AND logic).

#### agent-db.4 -- cancel_task

The `cancel_task` method SHALL accept `db: Session` and `task_id: str`.

It SHALL set `status` to `cancelled` and `completed_at` to current UTC time ONLY if the current status is in (`received`, `planning`, `delegating`, `monitoring`, `blocked`).

If the task is already in a terminal state (`completed`, `failed`, `cancelled`), it SHALL raise `ValueError` with a message indicating the task cannot be cancelled.

It SHALL return the updated `AgentTask`.

#### agent-db.5 -- update_task_status

The `update_task_status` method SHALL accept:
- `db: Session`
- `task_id: str`
- `status: str` -- the new status enum value
- `metadata_update: dict | None` (default `None`) -- partial JSON merge into `metadata`
- `result: dict | None` (default `None`) -- set when transitioning to `completed`
- `error: str | None` (default `None`) -- set when transitioning to `failed`

It SHALL validate state transitions against the Conductor state machine:
- `received` -> `planning`
- `planning` -> `delegating`
- `delegating` -> `monitoring`, `blocked`
- `monitoring` -> `synthesizing`
- `synthesizing` -> `completed`, `failed`
- `blocked` -> `delegating` (after approval)
- Any non-terminal -> `failed`, `cancelled`

Invalid transitions SHALL raise `ValueError`.

When transitioning to `completed` or `failed`, it SHALL set `completed_at`.

When `metadata_update` is provided, it SHALL merge (not replace) into the existing `metadata` JSON column.

### AgentInsightService

#### agent-db.6 -- create_insight

The `create_insight` method SHALL accept:
- `db: Session`
- `task_id: str` -- the originating agent task
- `title: str`
- `content: str`
- `insight_type: str` -- enum value from `InsightType`
- `confidence: float` -- value in `[0.0, 1.0]`
- `tags: list[str]` (default `[]`)
- `persona_name: str | None` (default `None`)

It SHALL return an `AgentInsight` ORM instance with a generated UUID `id`.

Insights with `confidence < 0.3` SHALL have `"speculative"` appended to `tags` automatically (per agentic-analysis.20).

#### agent-db.7 -- get_insight

The `get_insight` method SHALL accept `db: Session` and `insight_id: str`.

It SHALL return `AgentInsight | None`. When the insight exists, the returned object SHALL include the `persona_name` field populated via the JOIN to the parent `AgentTask` if `persona_name` is not stored directly on the insight.

#### agent-db.8 -- list_insights

The `list_insights` method SHALL accept:
- `db: Session`
- `insight_type: str | None` -- filter by InsightType enum value
- `persona_name: str | None` -- filter by persona
- `since: datetime | None` -- filter `created_at >= since`
- `min_confidence: float | None` -- filter `confidence >= min_confidence`
- `tags: list[str] | None` -- filter insights containing ALL specified tags
- `limit: int` (default `50`)
- `offset: int` (default `0`)

It SHALL return `list[AgentInsight]` ordered by `created_at` descending.

When `persona_name` is provided, the query SHALL JOIN to `agent_tasks` on `task_id` to filter by the task's persona (or use the insight's own `persona_name` column if denormalized).

### ApprovalService

#### agent-db.9 -- get_request

The `get_request` method SHALL accept `db: Session` and `request_id: str`.

It SHALL return `ApprovalRequest | None`.

#### agent-db.10 -- decide_request

The `decide_request` method SHALL accept:
- `db: Session`
- `request_id: str`
- `decision: str` -- `"approved"` or `"denied"`
- `reason: str | None` (default `None`) -- required when `decision` is `"denied"`

It SHALL update the `ApprovalRequest` record ONLY if `status` is `pending`. If the status is not `pending` (already decided or expired), it SHALL raise `ValueError`.

On approval:
- Set `status` to `approved`, `decided_at` to current UTC time
- Update the parent `AgentTask` status from `blocked` to `delegating`

On denial:
- Set `status` to `denied`, `decided_at` to current UTC time, `denial_reason` to the provided reason
- The parent task status change is left to the Conductor (it re-plans)

It SHALL return the updated `ApprovalRequest`.

#### agent-db.11 -- list_pending

The `list_pending` method SHALL accept:
- `db: Session`
- `limit: int` (default `20`)

It SHALL return `list[ApprovalRequest]` filtered to `status = 'pending'`, ordered by `created_at` ascending (oldest first).

It SHALL NOT return expired, approved, or denied requests.

## Queue Integration

#### agent-db.12 -- execute_agent_task entrypoint

The `execute_agent_task` function SHALL be registered as a PGQueuer job handler with job type `"agent_task"`.

The job payload schema SHALL be:
```json
{
  "task_id": "uuid-string",
  "persona": "persona-name",
  "output": "output-format-or-null",
  "sources": ["source-type", "..."]
}
```

The handler SHALL:
1. Look up the `AgentTask` by `task_id` from the payload
2. Instantiate a `Conductor` with the task's persona and parameters
3. Call `conductor.execute_task(task)` which drives the full state machine
4. On success: the Conductor sets task status to `completed` (handler does not duplicate this)
5. On unhandled exception: set task status to `failed` with the exception message
6. NOT interfere with existing job types (`extract_url_content`, `process_content`, `scan_newsletters`, `summarize_content`, `ingest_content`)

#### agent-db.13 -- Conductor lifecycle bridge

The queue handler SHALL bridge the Conductor's async execution to the PGQueuer worker's event loop.

The Conductor's `execute_task` method is async. The handler SHALL `await` it directly (the PGQueuer custom worker already runs in an async context per the existing `src/queue/worker.py` implementation).

If the Conductor raises `TaskCancelledException`, the handler SHALL set status to `cancelled` and NOT retry.

If the Conductor raises `TaskTimeoutError`, the handler SHALL set status to `failed` with error `"task_timeout"` and NOT retry.

For all other exceptions, standard PGQueuer retry policy applies.

## API Routes

All endpoints are mounted under `/api/v1/agent` and require authentication via `AuthMiddleware` (session cookie or `X-Admin-Key` header).

#### agent-db.14 -- POST /api/v1/agent/task

Request body:
```json
{
  "goal": "string (required)",
  "persona": "string (optional, default 'default')",
  "output": "string (optional)",
  "sources": ["string"] ,
  "priority": "string (optional, default 'medium')"
}
```

Response (201):
```json
{
  "task_id": "uuid",
  "status": "received",
  "created_at": "iso8601"
}
```

SHALL enqueue an `agent_task` job into PGQueuer after creating the DB record.

#### agent-db.15 -- GET /api/v1/agent/task/{id}

Response (200): Full `AgentTask` serialized as JSON including `result`, `metadata`, `persona_name`.

Response (404): `{"detail": "Task not found"}` when no task matches.

#### agent-db.16 -- GET /api/v1/agent/tasks

Query parameters: `status`, `source`, `persona`, `since` (ISO 8601), `limit`, `offset`.

Response (200):
```json
{
  "tasks": [...],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

#### agent-db.17 -- DELETE /api/v1/agent/task/{id}

Calls `AgentTaskService.cancel_task()`. Returns 200 on success, 404 if not found, 409 if task is in a terminal state.

#### agent-db.18 -- GET /api/v1/agent/insights

Query parameters: `type`, `persona`, `since`, `min_confidence`, `tags` (comma-separated), `limit`, `offset`.

Response (200):
```json
{
  "insights": [...],
  "total": 15,
  "limit": 50,
  "offset": 0
}
```

#### agent-db.19 -- GET /api/v1/agent/insights/{id}

Response (200): Full `AgentInsight` serialized as JSON.

Response (404): `{"detail": "Insight not found"}`.

#### agent-db.20 -- POST /api/v1/agent/approval/{id}

Request body:
```json
{
  "decision": "approved | denied",
  "reason": "string (required when denied)"
}
```

Response (200): Updated `ApprovalRequest` serialized as JSON.

Response (404): When request not found.

Response (409): When request is not in `pending` status.

#### agent-db.21 -- GET /api/v1/agent/approvals

Returns pending approval requests via `ApprovalService.list_pending()`.

Response (200):
```json
{
  "approvals": [...],
  "total": 3
}
```

#### agent-db.22 -- GET /api/v1/agent/schedules

Returns schedule definitions and their status (last run, next run, active persona).

Response (200):
```json
{
  "schedules": [
    {
      "id": "trend_detection_tech",
      "cron": "0 9 * * *",
      "persona": "ai-ml-technology",
      "output": "technical_report",
      "sources": null,
      "enabled": true,
      "last_run_at": "iso8601 | null",
      "next_run_at": "iso8601"
    }
  ]
}
```

#### agent-db.23 -- GET /api/v1/agent/personas

Returns available personas with summary from `PersonaLoader`.

Response (200):
```json
{
  "personas": [
    {
      "name": "default",
      "role": "General-purpose AI analyst",
      "domain_focus": ["ai", "technology"]
    }
  ]
}
```

#### agent-db.24 -- GET /api/v1/agent/task/{id}/events (SSE)

Returns a `text/event-stream` response. The endpoint SHALL:
- Poll the `agent_tasks` row for status changes at 2-second intervals
- Emit an SSE event for each status transition, specialist delegation, and intermediate finding
- Include `event:` field typed as `status_change`, `delegation`, `finding`, `approval_request`, `complete`, or `error`
- Send `event: complete` with the final result when task reaches a terminal state
- Close the stream after the terminal event
- Send `event: keepalive` every 15 seconds to prevent connection timeout

Data format per event:
```
event: status_change
data: {"task_id": "uuid", "status": "planning", "timestamp": "iso8601"}

event: complete
data: {"task_id": "uuid", "status": "completed", "result": {...}}
```

## CLI Commands

All commands are registered under the `aca agent` subcommand group in `src/cli/agent_commands.py`.

#### agent-db.25 -- aca agent task

```
aca agent task "prompt text" [--persona NAME] [--output FORMAT] [--sources SRC,SRC] [--wait]
```

- Calls `POST /api/v1/agent/task` (or directly invokes `AgentTaskService.create_task` + enqueue)
- `--wait` flag: poll task status until terminal, displaying progress updates
- Without `--wait`: print task ID and exit immediately
- SHALL respect `is_json_mode()` for structured output

#### agent-db.26 -- aca agent status

```
aca agent status <task-id>
```

- Displays task status, current phase, persona, elapsed time, and result summary if completed
- SHALL respect `is_json_mode()` for structured output

#### agent-db.27 -- aca agent insights

```
aca agent insights [--type TYPE] [--since DATE] [--persona NAME] [--min-confidence FLOAT]
```

- Lists insights with optional filters
- Displays title, type, confidence, tags, and creation date in tabular format
- SHALL respect `is_json_mode()` for structured output

#### agent-db.28 -- aca agent personas

```
aca agent personas
```

- Lists all available personas from `settings/personas/` directory
- Displays name, role, and domain focus for each
- SHALL respect `is_json_mode()` for structured output

#### agent-db.29 -- aca agent schedule

```
aca agent schedule [--enable SCHEDULE_ID] [--disable SCHEDULE_ID]
```

- Without flags: list all schedules with status
- With `--enable`/`--disable`: toggle the specified schedule
- SHALL respect `is_json_mode()` for structured output

#### agent-db.30 -- aca agent approve

```
aca agent approve <request-id>
```

- Approves a pending approval request
- Prints confirmation with the action that was approved
- SHALL guard `typer.echo()` calls with `not is_json_mode()`

#### agent-db.31 -- aca agent deny

```
aca agent deny <request-id> --reason "explanation"
```

- Denies a pending approval request with a required reason
- `--reason` is a required option (not optional)
- SHALL guard `typer.echo()` calls with `not is_json_mode()`
