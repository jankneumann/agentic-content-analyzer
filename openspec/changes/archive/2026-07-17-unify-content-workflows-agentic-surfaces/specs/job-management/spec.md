## ADDED Requirements

### Requirement: Job records project canonical operations

`pgqueuer_jobs` payload schema version 2 SHALL include operation type, normalized input, progress, message, cancellation request, optional resource reference, and optional result. Job status APIs and services SHALL project this data as the canonical `OperationHandle` without exposing queue-library-specific fields as the primary contract.

#### Scenario: Version 2 job is queryable as operation
- **WHEN** a version 2 job is fetched
- **THEN** its operation handle validates against the shared OpenAPI schema
- **AND** timestamps and retry count reflect the durable queue record

#### Scenario: Deployment reads version 1 jobs
- **WHEN** a version 1 job remains during the coordinated deployment window
- **THEN** workers and status readers continue to process it through a compatibility parser
- **AND** new submissions emit only version 2

### Requirement: Complete workflow handler registry

The worker SHALL register handlers for ingestion, summarization, theme analysis, digest creation, pipeline execution, podcast script creation, podcast audio creation, and audio digest creation. Handler registration MUST be validated against declared operation types at startup.

#### Scenario: Missing workflow handler fails startup
- **WHEN** an operation type is declared without a worker handler
- **THEN** worker startup fails with the missing operation type

### Requirement: Operation cancellation state

The job lifecycle SHALL include `cancelled`. Queued operations SHALL cancel atomically; running operations SHALL expose `cancel_requested` and stop only at workflow-declared checkpoints. Completed and non-cancellable operations MUST reject cancellation with a conflict problem.

#### Scenario: Running operation acknowledges cancellation request
- **WHEN** a cancellable running operation receives cancellation
- **THEN** its handle exposes that cancellation was requested
- **AND** the handler transitions to `cancelled` at its next safe checkpoint

#### Scenario: Completed operation cannot be cancelled
- **WHEN** cancellation is requested for a completed operation
- **THEN** the service returns a conflict problem
- **AND** the resource and operation status remain unchanged
