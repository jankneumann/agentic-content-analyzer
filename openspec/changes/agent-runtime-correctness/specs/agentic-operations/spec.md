## MODIFIED Requirements

### Requirement: Canonical operation handle

Every long-running mutation SHALL return an `OperationHandle` projected from `pgqueuer_jobs`. The handle MUST include schema version, operation ID, operation type, lifecycle status, progress, message, cancellability, retry count, timestamps, status URL, events URL, and optional resource, result, or RFC 7807 problem fields. The closed `operation_type` set SHALL include `agent_task.execute` and `approval.wait`.

#### Scenario: Submission returns durable handle
- **WHEN** a caller submits any long-running mutation, including an agent task
- **THEN** the response contains a queued operation ID that remains queryable after process restart
- **AND** no transport-specific task identifier is returned instead

#### Scenario: Completion links persisted resource
- **WHEN** a resource-producing operation completes
- **THEN** its handle has status `completed`
- **AND** it contains the persisted resource type, ID, and result URL
- **AND** the resource exists before completion is reported

#### Scenario: Agent task operations project their resource
- **WHEN** an `agent_task.execute` operation completes
- **THEN** its handle resource is `{type: "agent_task", id: <uuid>, url: "/api/v1/agent/task/<uuid>"}`
- **AND** an `approval.wait` child's resource is `{type: "approval_request", id: <uuid>, url: "/api/v1/agent/approvals/<uuid>"}`

## ADDED Requirements

### Requirement: Deferred operations wait on events

A deferred parent operation SHALL be able to wait for a child terminal transition or an
external decision without being re-claimed on a fixed interval.

#### Scenario: Parent waits on children
- **WHEN** a workflow defers with `wait_on = "children_terminal"`
- **THEN** the parent is released as `queued` with `execute_after` set to now plus `operation_wait_fallback_seconds`
- **AND** it is not claimed by any worker before a child reaches `completed`, `failed`, or `cancelled`

#### Scenario: Child terminal transition wakes the parent
- **WHEN** a child of a waiting parent reaches a terminal status
- **THEN** in the same transaction the parent's `execute_after` is reset to now, `wait_on` is cleared, and `pg_notify('pgqueuer', ...)` is issued
- **AND** the parent's `claim_generation` is unchanged

#### Scenario: External event wakes a waiting operation
- **WHEN** `OperationService.wake(operation_id)` is called on an operation deferred with `wait_on = "external_event"`
- **THEN** the operation becomes claimable immediately
- **AND** calling `wake` on an operation that is not waiting is a no-op that returns the current handle

#### Scenario: Lost wake is recovered
- **WHEN** the notify is not delivered and no wake call occurs
- **THEN** the waiting parent is re-claimed after `operation_wait_fallback_seconds`
- **AND** it re-evaluates its checkpoint and defers again if the child is still active

#### Scenario: Cancelling a waiting parent cascades
- **WHEN** a waiting parent is cancelled
- **THEN** its active children are cancelled in the same cascade
- **AND** a later decision on a cancelled `approval.wait` child is rejected with a conflict
