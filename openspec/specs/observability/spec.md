# observability Specification

## Purpose
TBD - created by archiving change add-otel-log-bridge. Update Purpose after archive.
## Requirements
### Requirement: OTel Log Bridge

The system SHALL bridge Python stdlib logging to the OpenTelemetry Log Data Model
for automatic trace-log correlation and structured log export.

#### Scenario: Automatic trace-log correlation
- **GIVEN** OTel tracing is enabled and a request is being processed
- **WHEN** a log statement is emitted within an active trace span
- **THEN** the log record SHALL automatically include the TraceId and SpanId
- **AND** no code changes at the log call site SHALL be required

#### Scenario: OTLP log export
- **GIVEN** `OTEL_ENABLED=true` and `OTEL_LOGS_ENABLED=true`
- **WHEN** a log statement at or above the configured export level is emitted
- **THEN** the log record SHALL be exported via OTLP HTTP to the configured endpoint
- **AND** the exported log SHALL include Resource attributes matching the trace exporter

#### Scenario: Log export disabled
- **GIVEN** `OTEL_ENABLED=false` or `OTEL_LOGS_ENABLED=false`
- **WHEN** a log statement is emitted
- **THEN** logs SHALL only be written to the console handler
- **AND** no OTLP export SHALL occur
- **AND** existing logging behavior SHALL be unchanged

#### Scenario: Export level filtering
- **GIVEN** `OTEL_LOGS_EXPORT_LEVEL=WARNING`
- **WHEN** an INFO-level log is emitted
- **THEN** the log SHALL appear on the console but SHALL NOT be exported via OTLP

### Requirement: Structured Console Output

The system SHALL support structured JSON and human-readable log output formats.

#### Scenario: JSON format (default)
- **GIVEN** `LOG_FORMAT=json` or no LOG_FORMAT is set
- **WHEN** logs are written to the console
- **THEN** each log line SHALL be a valid JSON object
- **AND** JSON SHALL include timestamp, level, logger name, message, and trace context
- **AND** JSON SHALL include exception details when `exc_info` is set
- **AND** JSON SHALL include stack trace when `stack_info` is set
- **AND** framework-injected duplicate attributes (e.g. uvicorn `color_message`) SHALL be excluded

#### Scenario: Text format
- **GIVEN** `LOG_FORMAT=text`
- **WHEN** logs are written to the console
- **THEN** output SHALL be human-readable plain text
- **AND** trace context (trace_id, span_id) SHALL be appended when available

### Requirement: Shared OTel Resource

The system SHALL use the same OTel Resource identity across traces, metrics, and logs.

#### Scenario: Resource consistency
- **GIVEN** OTel is enabled with traces and logs
- **WHEN** a trace and a log are exported from the same request
- **THEN** both SHALL have identical service.name and deployment.environment attributes

### Requirement: Distributed Tracing

The system SHALL support OpenTelemetry distributed tracing across frontend and backend.

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

#### Scenario: Trace-log correlation
- **GIVEN** tracing and logging are both enabled
- **WHEN** log statements are emitted within a traced request
- **THEN** log records SHALL contain the same TraceId as the request trace
- **AND** log records SHALL contain the SpanId of the current span

#### Scenario: End-to-end trace from browser to backend
- **GIVEN** frontend and backend tracing are both enabled
- **WHEN** a user action triggers an API request from the browser
- **THEN** the browser span and backend spans SHALL share the same trace_id
- **AND** the backend span SHALL be a child of the browser span

### Requirement: Frontend Trace Propagation

The frontend SHALL propagate W3C Trace Context headers on all API requests for end-to-end
distributed tracing between browser and backend.

#### Scenario: Trace header on API fetch
- **GIVEN** frontend OTel is enabled via `VITE_OTEL_ENABLED=true`
- **WHEN** the frontend makes a fetch request to the backend API
- **THEN** the request SHALL include a `traceparent` header with a valid W3C trace context
- **AND** the backend span SHALL be a child of the frontend span (same trace_id)

#### Scenario: Trace propagation disabled
- **GIVEN** `VITE_OTEL_ENABLED` is not set or is `false`
- **WHEN** the frontend makes a fetch request to the backend API
- **THEN** no `traceparent` header SHALL be added
- **AND** no OTel SDK code SHALL execute (zero overhead)

#### Scenario: SSE stream trace correlation
- **GIVEN** frontend OTel is enabled
- **WHEN** the frontend opens an SSE stream for a long-running operation
- **THEN** the initial fetch request SHALL carry the `traceparent` header
- **AND** the backend processing spans SHALL be children of the frontend trace

### Requirement: Web Vitals Metrics

The frontend SHALL report Core Web Vitals as OpenTelemetry metrics for performance monitoring.

#### Scenario: Web Vitals reported
- **GIVEN** frontend OTel is enabled
- **WHEN** the user interacts with the application
- **THEN** LCP, INP, CLS, FCP, and TTFB SHALL be measured
- **AND** each metric SHALL be exported as an OTel histogram observation
- **AND** metric names SHALL follow the pattern `browser.web_vital.{metric_name}`

#### Scenario: Web Vitals disabled
- **GIVEN** frontend OTel is disabled
- **WHEN** the page loads
- **THEN** no Web Vitals measurement code SHALL execute

### Requirement: React Error Boundary with OTel

The frontend SHALL capture uncaught React component errors as OTel events for error tracking
and trace correlation.

#### Scenario: Component error captured
- **GIVEN** frontend OTel is enabled and a React component throws during rendering
- **WHEN** the Error Boundary catches the error
- **THEN** an OTel event SHALL be recorded with the error message and stack trace
- **AND** the active span (if any) SHALL be set to ERROR status
- **AND** a fallback UI SHALL be rendered with the trace_id for support correlation

#### Scenario: Error boundary without OTel
- **GIVEN** frontend OTel is disabled and a React component throws
- **WHEN** the Error Boundary catches the error
- **THEN** a fallback UI SHALL be rendered
- **AND** no OTel event SHALL be recorded
- **AND** the error SHALL be logged to the browser console

### Requirement: OTLP Backend Proxy

The backend SHALL provide a proxy endpoint for frontend OTLP trace export to avoid CORS
issues and credential exposure.

#### Scenario: Trace data forwarded
- **GIVEN** backend OTel is enabled and the OTLP endpoint is configured
- **WHEN** the frontend sends trace data to `POST /api/v1/otel/v1/traces`
- **THEN** the backend SHALL forward the request to the configured OTLP endpoint
- **AND** the backend SHALL add authentication headers from its configuration
- **AND** the backend SHALL return 204 on successful forwarding

#### Scenario: Proxy disabled
- **GIVEN** backend OTel is disabled (`OTEL_ENABLED=false`)
- **WHEN** the frontend sends trace data to `POST /api/v1/otel/v1/traces`
- **THEN** the backend SHALL return 404

#### Scenario: Oversized payload rejected
- **GIVEN** the OTLP proxy is enabled
- **WHEN** the frontend sends a request body larger than 1MB
- **THEN** the backend SHALL return 413 (Payload Too Large)
- **AND** the request SHALL NOT be forwarded to the OTLP endpoint
