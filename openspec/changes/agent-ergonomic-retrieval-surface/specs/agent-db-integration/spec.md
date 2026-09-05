## MODIFIED Requirements

### Requirement: AgentInsightService

`AgentInsightService` SHALL provide the persistence contract for agent-generated
insights: creation, retrieval, listing, and lifecycle transitions.

#### Scenario: create_insight

The `create_insight` method SHALL accept:
- `db: Session`
- `task_id: str` -- the originating agent task
- `title: str`
- `content: str`
- `insight_type: str` -- enum value from `InsightType`
- `confidence: float` -- value in `[0.0, 1.0]`
- `tags: list[str]` (default `[]`)
- `related_content_ids: list[int]` (default `[]`)
- `related_theme_ids: list[int]` (default `[]`)
- `metadata: dict` (default `{}`)
- `persona_name: str | None` (default `None`)

It SHALL return an `AgentInsight` ORM instance with a generated UUID `id` and `maturity` set to `candidate` when `confidence < 0.3` and `active` otherwise.

Insights with `confidence < 0.3` SHALL have `"speculative"` appended to `tags` automatically (per agentic-analysis.20).

#### Scenario: get_insight

The `get_insight` method SHALL accept `db: Session` and `insight_id: str`.

It SHALL return `AgentInsight | None`. When the insight exists, the returned object SHALL include the `persona_name` field populated via the JOIN to the parent `AgentTask` if `persona_name` is not stored directly on the insight.

#### Scenario: list_insights

The `list_insights` method SHALL accept:
- `db: Session`
- `insight_type: str | None` -- filter by InsightType enum value
- `persona_name: str | None` -- filter by persona
- `since: datetime | None` -- filter `created_at >= since`
- `min_confidence: float | None` -- filter `confidence >= min_confidence`
- `tags: list[str] | None` -- filter insights containing ALL specified tags
- `maturity: list[str] | None` -- filter by `InsightMaturity` values (default excludes `superseded` and `withdrawn`)
- `limit: int` (default `50`)
- `cursor: str | None` -- keyset cursor over `(created_at, id)`

It SHALL return `(list[AgentInsight], total: int, next_cursor: str | None)` ordered by `created_at` descending.

When `persona_name` is provided, the query SHALL JOIN to `agent_tasks` on `task_id` to filter by the task's persona (or use the insight's own `persona_name` column if denormalized).

#### Scenario: set_maturity
- **WHEN** `set_maturity(insight_id, maturity)` is called with a valid `InsightMaturity` value
- **THEN** it SHALL update `maturity` and return the row
- **AND** it SHALL raise `ValueError` for `superseded`, which is reachable only through `supersede`

#### Scenario: supersede
- **WHEN** `supersede(insight_id, successor_id)` is called
- **THEN** it SHALL set `superseded_by = successor_id` and `maturity = superseded` on the target
- **AND** it SHALL NOT modify the target's `title`, `content`, `confidence`, or evidence fields
- **AND** it SHALL raise `ValueError` when `successor_id` equals `insight_id` or does not exist

#### Scenario: mark_stale_for_schedule
- **WHEN** `mark_stale_for_schedule(schedule_id, before_task_id)` is called
- **THEN** every `active` insight whose `metadata.schedule_id` matches and whose task is not `before_task_id` SHALL become `stale`
- **AND** `candidate`, `superseded`, and `withdrawn` insights SHALL be unchanged

### Requirement: API Routes

The API SHALL expose agent task submission and tracking, insights, approvals,
schedules, personas, and an SSE event stream under `/api/v1/agent/`, with task submission
returning a canonical operation handle and insight listing returning a cursor envelope.

All endpoints are mounted under `/api/v1/agent` and require authentication via `AuthMiddleware` (session cookie or `X-Admin-Key` header).

#### Scenario: POST /api/v1/agent/task

Request body:
```json
{
  "prompt": "string (required)",
  "task_type": "research | analysis | synthesis | ingestion (optional, default 'research')",
  "persona": "string (optional, default 'default')",
  "params": {}
}
```

Response (202): an `OperationHandle` with `operation_type = "agent_task.execute"` and `resource = {type: "agent_task", id, url}`.

SHALL create the `agent_tasks` record with status `received` and submit one `agent_task.execute` operation through `OperationService`. It SHALL NOT enqueue a transport-owned `execute_agent_task` job. Resubmitting the same normalized input while the operation is active SHALL return the existing handle.

#### Scenario: GET /api/v1/agent/task/{id}

Response (200): Full `AgentTask` serialized as JSON including `result`, `metadata`, `persona_name`.

Response (404): `{"detail": "Task not found"}` when no task matches.

#### Scenario: GET /api/v1/agent/tasks

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

#### Scenario: DELETE /api/v1/agent/task/{id}

Cancels the task's `agent_task.execute` operation through `OperationService.cancel`, which cascades to any waiting `approval.wait` child, and calls `AgentTaskService.cancel_task()`. Returns 200 on success, 404 if not found, 409 if task is in a terminal state.

#### Scenario: GET /api/v1/agent/insights

Query parameters: `type`, `persona`, `since`, `min_confidence`, `tags` (comma-separated), `maturity` (comma-separated, default excludes `superseded` and `withdrawn`), `limit`, `cursor`.

Response (200):
```json
{
  "data": [
    {
      "id": "uuid",
      "insight_type": "trend",
      "title": "...",
      "content": "...",
      "confidence": 0.82,
      "tags": [],
      "related_content_ids": [101, 205],
      "related_theme_ids": [7],
      "metadata": {"schedule_id": "trend_detection_tech"},
      "maturity": "active",
      "superseded_by": null,
      "persona_name": "ai-ml-technology",
      "task_id": "uuid",
      "created_at": "iso8601"
    }
  ],
  "total": 15,
  "next_cursor": null
}
```

#### Scenario: GET /api/v1/agent/insights/{id}

Response (200): Full `AgentInsight` serialized as JSON with the same fields as a list item.

Response (404): `{"detail": "Insight not found"}`.

#### Scenario: PATCH /api/v1/agent/insights/{id}

Request body: exactly one of `{"maturity": "active | candidate | stale | withdrawn"}` or `{"superseded_by": "uuid"}`.

Response (200): the updated insight. Response (404) when not found. Response (422) when both or neither field is present, when `maturity` is `superseded`, or when `superseded_by` is the insight itself or unknown.

#### Scenario: POST /api/v1/agent/approval/{id}

Request body:
```json
{
  "approved": true,
  "reason": "string (required when approved is false)"
}
```

Response (200): Updated `ApprovalRequest` serialized as JSON. The route SHALL record the decision and call `OperationService.wake` on the linked `approval.wait` operation; the parent `agent_task.execute` operation resumes through the queue and the route SHALL NOT enqueue anything directly.

Response (404): When request not found.

Response (409): RFC 7807 problem when the request is not in `pending` status or its operation was cancelled; the stored decision SHALL be unchanged.

#### Scenario: GET /api/v1/agent/approvals

Query parameters: `status` (default `pending`), `limit`, `cursor`.

Response (200):
```json
{
  "data": [
    {
      "id": "uuid",
      "task_id": "uuid",
      "operation_id": "4712",
      "action": "delegate.ingestion",
      "risk_level": "high",
      "context": {},
      "status": "pending",
      "decision_reason": null,
      "decided_at": null,
      "created_at": "iso8601"
    }
  ],
  "next_cursor": null
}
```

#### Scenario: GET /api/v1/agent/schedules

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

#### Scenario: GET /api/v1/agent/personas

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

#### Scenario: GET /api/v1/agent/task/{id}/events (SSE)

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
