## ADDED Requirements

### Requirement: Canonical operation handle

Every long-running mutation SHALL return an `OperationHandle` projected from `pgqueuer_jobs`. The handle MUST include schema version, operation ID, operation type, lifecycle status, progress, message, cancellability, retry count, timestamps, status URL, events URL, and optional resource, result, or RFC 7807 problem fields.

#### Scenario: Submission returns durable handle
- **WHEN** a caller submits any long-running mutation
- **THEN** the response contains a queued operation ID that remains queryable after process restart
- **AND** no transport-specific task identifier is returned instead

#### Scenario: Completion links persisted resource
- **WHEN** a resource-producing operation completes
- **THEN** its handle has status `completed`
- **AND** it contains the persisted resource type, ID, and result URL
- **AND** the resource exists before completion is reported

### Requirement: Universal queue execution

Ingestion, summarization, theme analysis, digest creation, pipeline execution, podcast script creation, podcast audio creation, and audio digest creation SHALL execute through PostgreSQL queue handlers. API background tasks and direct transport execution paths for these mutations MUST NOT remain after cutover.

#### Scenario: Equivalent interfaces enqueue the same operation
- **WHEN** equivalent commands are submitted through CLI, HTTP, MCP, and the frontend
- **THEN** each uses the same operation type and normalized job payload schema
- **AND** each worker invokes the same application workflow service

### Requirement: Idempotency and operation control

Operation submission SHALL use the existing queue idempotency key. The system SHALL support bounded waiting, safe cancellation, and retry of failed operations through the shared operation service. A repeated active request with the same idempotency key MUST return the existing operation.

#### Scenario: Idempotent resubmission
- **WHEN** the same normalized command and idempotency key are submitted while an operation is queued or running
- **THEN** the existing operation handle is returned
- **AND** no duplicate job or resource is created

#### Scenario: Queued operation is cancelled
- **WHEN** a cancellable queued operation receives a cancellation request
- **THEN** its status becomes `cancelled`
- **AND** no worker executes the operation

#### Scenario: Failed operation is retried
- **WHEN** a retryable failed operation receives a retry request
- **THEN** retry count is incremented
- **AND** the normalized input is requeued without changing its operation type

#### Scenario: Bounded wait times out cleanly
- **WHEN** a caller waits for less time than the operation needs
- **THEN** the latest nonterminal operation handle is returned
- **AND** execution continues in the queue

### Requirement: Agent-usable structured interfaces

CLI JSON output, HTTP responses, MCP structured results, and frontend client models SHALL conform to the same operation and resource schemas. Expected failures MUST be represented as RFC 7807 problems over HTTP and as protocol-level MCP errors rather than successful payloads containing an `error` key.

#### Scenario: MCP failure is a tool error
- **WHEN** an MCP workflow tool receives a validation or operation failure
- **THEN** the tool raises an MCP error with stable code and structured problem data
- **AND** it does not return a successful JSON string containing the error

#### Scenario: Pagination uses cursors
- **WHEN** an agent lists operations or capabilities beyond one response page
- **THEN** the response contains an opaque next cursor
- **AND** passing that cursor continues without duplicate records
