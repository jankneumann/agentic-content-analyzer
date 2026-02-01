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

#### Scenario: Trace-log correlation
- **GIVEN** tracing and logging are both enabled
- **WHEN** log statements are emitted within a traced request
- **THEN** log records SHALL contain the same TraceId as the request trace
- **AND** log records SHALL contain the SpanId of the current span
