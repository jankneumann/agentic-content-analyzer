# Observability Capability

## ADDED Requirements

### Requirement: Health Endpoints

The system SHALL provide health check endpoints for orchestration.

#### Scenario: Liveness check
- **GIVEN** the application is running
- **WHEN** `GET /health` is called
- **THEN** 200 status SHALL be returned
- **AND** response SHALL include `{"status": "healthy"}`

#### Scenario: Readiness check
- **GIVEN** all dependencies are available
- **WHEN** `GET /ready` is called
- **THEN** 200 status SHALL be returned
- **AND** response SHALL include check results for each dependency

#### Scenario: Readiness failure
- **GIVEN** database is unavailable
- **WHEN** `GET /ready` is called
- **THEN** 503 status SHALL be returned
- **AND** failed check SHALL be identified in response

### Requirement: Metrics Endpoint

The system SHALL expose Prometheus-compatible metrics.

#### Scenario: Metrics collection
- **WHEN** `GET /metrics` is called
- **THEN** Prometheus text format SHALL be returned
- **AND** metrics SHALL include request counts, durations, and LLM token usage

### Requirement: Distributed Tracing

The system SHALL support OpenTelemetry distributed tracing.

#### Scenario: Request tracing
- **GIVEN** tracing is enabled
- **WHEN** an API request is processed
- **THEN** a trace SHALL be created
- **AND** trace_id SHALL be included in response headers

#### Scenario: Pipeline tracing
- **GIVEN** content is being processed
- **WHEN** summarization runs
- **THEN** spans SHALL be created for each pipeline stage
- **AND** spans SHALL be linked to parent trace

### Requirement: LLM Observability

The system SHALL track LLM-specific metrics via Opik.

#### Scenario: LLM call tracking
- **GIVEN** Opik is enabled
- **WHEN** an LLM API call is made
- **THEN** prompt, completion, tokens, and latency SHALL be logged

### Requirement: Structured Errors

The system SHALL return structured error responses.

#### Scenario: Error with trace
- **GIVEN** an error occurs during request processing
- **WHEN** error response is returned
- **THEN** response SHALL include error code, message, and trace_id
