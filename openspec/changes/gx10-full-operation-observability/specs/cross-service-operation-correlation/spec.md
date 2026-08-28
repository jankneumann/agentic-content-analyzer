## Purpose

Provide one attempt-aware, privacy-safe correlation contract that makes every meaningful backend operation diagnosable across process, queue, persistence, provider, and service boundaries.

## ADDED Requirements

### Requirement: Canonical operation context envelope

The system SHALL represent execution context with a versioned envelope containing operation ID, root operation ID, optional parent operation ID, traceparent, optional tracestate, trace ID, the current span ID, claim generation, nullable attempt number, entrypoint, service name, service instance ID, release revision, and optional bounded stage, resource kind, and opaque resource key.

Every nullable envelope key SHALL be present with an explicit null value when absent. Before a claim, attempt number SHALL be null; after a claim it SHALL equal claim generation plus one. Claim generation SHALL retain the existing 64-bit database width. The envelope SHALL use W3C Trace Context encodings, SHALL reject malformed or oversized untrusted values at ingress, and SHALL never contain credentials, raw source URLs, unrestricted prompts, unrestricted source content, or exception text.

#### Scenario: [CORR-001] Valid context crosses an asynchronous boundary

- **WHEN** an API request submits a durable operation and a worker later claims it
- **THEN** the queued record contains a validated versioned context envelope
- **AND** the worker continues the stored trace with a new attempt span
- **AND** the operation, root, parent, trace, claim, service, and release identifiers are available to logs and Langfuse observations

#### Scenario: [CORR-002] Malformed external trace context is isolated

- **WHEN** a caller supplies malformed traceparent, tracestate, or correlation metadata
- **THEN** the system discards the invalid external context and starts a valid local trace
- **AND** it records a bounded diagnostic code without reflecting the rejected value

### Requirement: Universal propagation across meaningful operations

Every meaningful execution initiated by HTTP, CLI, MCP, scheduler, queue, worker, agent, maintenance, backup, alert, or operator command SHALL establish operation context. The system SHALL propagate that context across child operations, queue submissions, retries, ingestion items, parsers, LLM/provider calls, PostgreSQL writes, graph operations, indexing, storage, delivery, and supported external API calls.

Low-level health probes and static asset requests MAY be excluded only by an explicit documented allowlist.

#### Scenario: [CORR-003] One operation remains navigable end to end

- **WHEN** an operation traverses API, queue, worker, parser, model, PostgreSQL, graph, and delivery boundaries
- **THEN** every service hop emits a child observation or span linked to the same root operation and trace
- **AND** child durable operations retain both their own operation identity and their parent/root identities

#### Scenario: [CORR-004] Non-HTTP work receives correlation

- **WHEN** a scheduled cleanup, backup, alert, CLI, or agent action starts without an inbound HTTP trace
- **THEN** it creates a canonical root operation context before performing side effects
- **AND** its durable and detailed evidence is queryable by the resulting operation identity

### Requirement: Attempt-aware execution topology

Each queue claim SHALL create exactly one attempt root span beneath the stored submission context. Claim generation SHALL be the fencing identity and SHALL disambiguate retries, stale workers, and reclaimed work. Stage spans SHALL nest beneath the active attempt and SHALL not overwrite evidence from earlier attempts.

#### Scenario: [CORR-005] Retry preserves prior evidence

- **WHEN** claim generation 2 retries an operation after claim generation 1 fails
- **THEN** both attempts remain independently queryable
- **AND** the retry is linked to the same durable operation and root trace
- **AND** stale generation 1 cannot finalize generation 2 state

#### Scenario: [CORR-006] Process restart continues stored context

- **WHEN** a worker restarts after a job was submitted but before it was claimed
- **THEN** the next worker extracts context from PostgreSQL rather than process memory
- **AND** the resulting attempt remains correlated with the original submission

### Requirement: PostgreSQL correlation and attempt evidence

PostgreSQL SHALL remain authoritative for durable operation state. It SHALL persist indexed correlation fields on the operation record and append one bounded summary per claim attempt without duplicating full stage history, full telemetry payloads, or a second workflow state machine. Detailed stage history SHALL remain in Langfuse; the attempt summary SHALL retain only its current or terminal stage plus bounded diagnostic codes and omitted-detail counts.

Attempt evidence SHALL include operation ID, claim generation, trace ID, root span/observation identifier when available, service identity, release, start/end timestamps, outcome, current/terminal stage, diagnostic codes, retryability, and omitted-detail counts. Stack traces, unrestricted input/output, and secrets SHALL NOT be stored in these fields.

#### Scenario: [CORR-007] Exact operation lookup survives restart

- **WHEN** an operator reads an operation after all originating processes have restarted
- **THEN** PostgreSQL returns its trace ID and ordered attempt summaries
- **AND** each attempt provides enough safe identifiers to locate detailed Langfuse evidence

#### Scenario: [CORR-008] Telemetry outage does not become workflow truth

- **WHEN** Langfuse or the OTLP receiver is unavailable
- **THEN** the operation lifecycle continues according to domain policy
- **AND** PostgreSQL records the attempt outcome plus a telemetry-delivery diagnostic
- **AND** no synthetic completed or failed workflow state is created solely by the telemetry outage

### Requirement: Stable stage outcome and error vocabulary

Instrumentation SHALL use centrally defined bounded vocabularies for stage, outcome, error class, retryability, and evidence level. Outcomes SHALL distinguish succeeded, partial, skipped policy, skipped duplicate, filtered, retryable failure, permanent failure, and cancelled.

Exceptions SHALL NOT be translated into a successful skip unless a domain rule explicitly classifies the condition as non-error.

#### Scenario: [CORR-009] Caught exception remains a failure

- **WHEN** an adapter catches an exception to preserve batch continuation
- **THEN** it emits an exception event in the active stage span
- **AND** it persists a retryable or permanent failure diagnostic
- **AND** aggregate failed counts include that item

#### Scenario: [CORR-010] Intentional exclusion remains non-error

- **WHEN** an item is excluded by length, age, duplicate, or configured filtering policy
- **THEN** its outcome uses the matching skip/filter classification
- **AND** no exception evidence is fabricated

### Requirement: Safe exact-operation diagnostics

The exact-operation surface SHALL expose a bounded observability summary containing trace ID, root operation ID, latest attempt, stage/outcome codes, telemetry-delivery state, and a server-generated Langfuse lookup URL only to authorized callers. A separate authorized attempt endpoint SHALL return all attempts through stable cursor pagination ordered by ascending claim generation, with a default page size of 50 and a maximum of 100. Collection/list responses SHALL remain bounded summaries and SHALL not expose detailed attempts or unrestricted diagnostic messages.

#### Scenario: [CORR-011] Authorized operator follows a trace

- **WHEN** an authorized operator requests one operation
- **THEN** the response includes safe correlation and attempt summaries
- **AND** any Langfuse link is generated from trusted configuration and opaque identifiers

#### Scenario: [CORR-012] Lists remain low-volume and safe

- **WHEN** a caller lists operations or ingestion history
- **THEN** each row contains at most a trace ID and bounded outcome/error codes
- **AND** no stack, excerpt, internal host, or secret-bearing link is included

#### Scenario: [CORR-015] Attempt history exceeds one page

- **WHEN** an authorized operator requests an operation with more attempts than the selected page limit
- **THEN** the endpoint returns attempts in ascending claim-generation order and a cursor for the next page
- **AND** following the cursor returns the remaining attempts without duplicates or gaps

### Requirement: Correlated telemetry delivery health

Each emitting process SHALL heartbeat bounded health keyed by environment, service, and instance: required/initialized state, release, export target, last heartbeat, last successful and failed export timestamps and ages in seconds, last error code, buffered count and capacity, dropped count, and final flush timestamp/outcome. Long-running process rows SHALL become stale after the configured freshness bound; short-lived processes SHALL persist final flush evidence. The authenticated observability health API SHALL aggregate all nonexpired deployment rows rather than presenting one API process as deployment health. Readiness policy SHALL be configurable, but silent disablement while observability is required SHALL be prohibited.

#### Scenario: [CORR-013] Missing endpoint is visible

- **WHEN** a production profile enables required observability without a valid local OTLP or Langfuse endpoint
- **THEN** profile validation or readiness fails with a bounded actionable diagnostic
- **AND** the process does not report fully ready

#### Scenario: [CORR-014] Short-lived process flushes evidence

- **WHEN** a CLI, scheduler, backup, or maintenance process exits
- **THEN** it performs a bounded telemetry flush
- **AND** flush failure is surfaced in its exit evidence without leaking payloads
