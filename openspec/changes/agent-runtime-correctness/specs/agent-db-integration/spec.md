## MODIFIED Requirements

### Requirement: ApprovalService

`ApprovalService` SHALL provide the persistence contract for approval requests: creation,
retrieval, decision recording, and listing.

#### Scenario: create_request
- **WHEN** `create_request(task_id, action, risk_level, context, operation_id)` is called
- **THEN** it SHALL insert an `ApprovalRequest` with status `pending`, the given action, risk level, context, and the `approval.wait` operation ID
- **AND** return the row with a generated UUID

#### Scenario: get_request

The `get_request` method SHALL accept `db: Session` and `request_id: str`.

It SHALL return `ApprovalRequest | None`.

#### Scenario: decide_request

The `decide_request` method SHALL accept:
- `db: Session`
- `request_id: str`
- `decision: str` -- `"approved"` or `"denied"`
- `reason: str | None` (default `None`) -- required when `decision` is `"denied"`

It SHALL update the `ApprovalRequest` record ONLY if `status` is `pending`. If the status is not `pending` (already decided or expired), it SHALL raise `ApprovalAlreadyDecidedError` (a `ValueError` subclass) and SHALL NOT modify the row.

On approval:
- Set `status` to `approved`, `decided_at` to current UTC time
- The parent `AgentTask` status transition from `blocked` is performed by the resumed `agent_task.execute` operation, not by the service

On denial:
- Set `status` to `denied`, `decided_at` to current UTC time, `decision_reason` to the provided reason
- The parent task status change is left to the Conductor (it re-plans once)

It SHALL return the updated `ApprovalRequest`.

#### Scenario: list_pending

The `list_pending` method SHALL accept `db: Session` and `limit: int` (default `20`) and SHALL be equivalent to `list_requests(status="pending", limit=limit)`.

It SHALL return `list[ApprovalRequest]` filtered to `status = 'pending'`, ordered by `created_at` ascending (oldest first).

It SHALL NOT return expired, approved, or denied requests.

#### Scenario: list_requests
- **WHEN** `list_requests(status, limit, cursor)` is called
- **THEN** it SHALL return `(rows, next_cursor)` filtered by status, ordered by `created_at` ascending, using a keyset cursor over `(created_at, id)`
- **AND** `status = "pending"` SHALL exclude approved, denied, and expired rows

### Requirement: API Routes

The API SHALL expose agent task submission and tracking, insights, approvals,
schedules, personas, and an SSE event stream under `/api/v1/agent/`, with task submission
returning a canonical operation handle.

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

#### Scenario: GET /api/v1/agent/insights/{id}

Response (200): Full `AgentInsight` serialized as JSON.

Response (404): `{"detail": "Insight not found"}`.

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
