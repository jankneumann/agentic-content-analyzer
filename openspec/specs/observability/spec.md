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

### Requirement: Observability Provider Selection

The system SHALL support five observability providers: noop, opik, braintrust, otel, and langfuse.

#### Scenario: Valid provider values
- **WHEN** `OBSERVABILITY_PROVIDER` is set to any of `"noop"`, `"opik"`, `"braintrust"`, `"otel"`, or `"langfuse"`
- **THEN** the system SHALL accept the value and instantiate the corresponding provider

#### Scenario: Factory dispatch for langfuse
- **WHEN** `observability_provider` is `"langfuse"` in settings
- **THEN** the factory SHALL create a `LangfuseProvider` with `public_key`, `secret_key`, `base_url`, `service_name`, and `log_prompts` from settings

### Requirement: Langfuse Observability Provider

The system SHALL support Langfuse as an LLM observability provider using the native Langfuse Python SDK v4. Langfuse SHALL be selectable via `OBSERVABILITY_PROVIDER=langfuse` and support both Langfuse Cloud and self-hosted deployments. The provider SHALL create generation-typed observations for LLM calls, enabling cost tracking, token attribution, and rich trace visualization in the Langfuse UI.

#### Scenario: Select Langfuse provider via configuration
- **WHEN** `OBSERVABILITY_PROVIDER` is set to `"langfuse"`
- **THEN** the telemetry factory SHALL instantiate `LangfuseProvider`
- **AND** the provider SHALL initialize via `langfuse.Langfuse()` constructor (not raw `OTLPSpanExporter`)

#### Scenario: Langfuse Cloud authentication
- **WHEN** `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are configured
- **THEN** the provider SHALL pass these to the `Langfuse()` constructor as `public_key` and `secret_key`
- **AND** the default `base_url` SHALL be `https://cloud.langfuse.com`
- **AND** `langfuse.auth_check()` SHALL return `True` when credentials are valid

#### Scenario: Self-hosted Langfuse endpoint
- **WHEN** `LANGFUSE_BASE_URL` is set to a custom URL (e.g., `http://localhost:3100`)
- **THEN** the `Langfuse()` constructor SHALL use that base URL
- **AND** traces SHALL be sent to the self-hosted instance

#### Scenario: Missing API keys warning
- **WHEN** `OBSERVABILITY_PROVIDER=langfuse` is set without `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`
- **THEN** the system SHALL log at WARNING level about missing credentials
- **AND** the provider SHALL still attempt initialization (self-hosted may not require auth)

#### Scenario: Partial API keys warning
- **WHEN** only one of `LANGFUSE_PUBLIC_KEY` or `LANGFUSE_SECRET_KEY` is configured (not both)
- **THEN** the system SHALL log at WARNING level about incomplete credentials

#### Scenario: LLM call tracing as generation observation
- **WHEN** an LLM call is traced via `trace_llm_call()`
- **THEN** the provider SHALL create an observation with `as_type="generation"`
- **AND** the observation SHALL include `model`, `usage.input` (input tokens), and `usage.output` (output tokens)
- **AND** when `otel_log_prompts` is true, the observation SHALL include `input` (user prompt) and `output` (response text)
- **AND** when `otel_log_prompts` is false, the observation SHALL NOT include prompt/completion text

#### Scenario: Cost tracking for LLM calls
- **WHEN** a generation observation is created with a recognized model name
- **THEN** Langfuse SHALL automatically calculate and display the cost based on its model pricing database
- **AND** no manual cost calculation SHALL be required in the provider

#### Scenario: Pipeline span creation
- **WHEN** `start_span()` is called with a name and attributes
- **THEN** the provider SHALL create a Langfuse observation with `as_type="span"`
- **AND** custom attributes SHALL be set as metadata on the observation

#### Scenario: Provider lifecycle management
- **WHEN** `flush()` is called
- **THEN** the provider SHALL call `langfuse.flush()` to export buffered data
- **WHEN** `shutdown()` is called
- **THEN** the provider SHALL call `langfuse.flush()` followed by resource cleanup

#### Scenario: Graceful degradation without Langfuse package
- **WHEN** the `langfuse` package is not installed
- **THEN** the provider SHALL log an error with installation instructions
- **AND** all trace methods SHALL be no-ops (never raise exceptions)

#### Scenario: Trace export failure (Langfuse unreachable)
- **WHEN** the Langfuse endpoint is unreachable (connection refused, timeout, DNS failure)
- **THEN** the Langfuse SDK SHALL handle the failure internally (async background export with retry)
- **AND** the application SHALL NOT be affected (fail-safe design)
- **AND** no exceptions SHALL propagate to calling code

#### Scenario: Smart span filtering
- **WHEN** the Langfuse provider is initialized
- **THEN** the SDK SHALL use the default span filter that exports only Langfuse SDK spans, `gen_ai.*` spans, and known LLM instrumentor spans
- **AND** infrastructure spans from FastAPI, SQLAlchemy, and httpx auto-instrumentation SHALL NOT be exported to Langfuse

#### Scenario: Isolated TracerProvider
- **WHEN** the Langfuse provider is initialized
- **THEN** the Langfuse SDK SHALL use its own TracerProvider
- **AND** the global OTel TracerProvider used by `otel_setup.py` SHALL NOT be overwritten

### Requirement: Langfuse Local Development Infrastructure

The system SHALL provide Docker Compose configuration for running a self-hosted Langfuse stack alongside existing development services.

#### Scenario: Start Langfuse stack
- **WHEN** `make langfuse-up` is executed
- **THEN** the Langfuse stack SHALL start with all required services (web, worker, postgres, clickhouse, redis, minio)
- **AND** the Langfuse UI SHALL be accessible at `http://localhost:3100`
- **AND** the OTLP endpoint SHALL be accessible at `http://localhost:3100/api/public/otel`

#### Scenario: No port conflicts with existing services
- **WHEN** the Langfuse stack runs alongside the main application stack and Opik stack
- **THEN** there SHALL be no port conflicts
- **AND** Langfuse SHALL use port 3100 (not 3000, 5173, 5174, or 8000)

#### Scenario: Stop Langfuse stack
- **WHEN** `make langfuse-down` is executed
- **THEN** all Langfuse services SHALL be stopped

#### Scenario: Health check readiness
- **WHEN** `make langfuse-up` completes
- **THEN** the Langfuse health endpoint `/api/public/health` SHALL return HTTP 200

### Requirement: Langfuse Profile Configuration

The system SHALL provide a profile for local development with Langfuse.

#### Scenario: Activate Langfuse profile
- **WHEN** `PROFILE=local-langfuse` is set
- **THEN** `observability_provider` SHALL be `"langfuse"`
- **AND** `otel_enabled` SHALL be `true`
- **AND** `langfuse_base_url` SHALL be `"http://localhost:3100"`

#### Scenario: Langfuse secrets in base profile
- **WHEN** `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set in `.secrets.yaml` or environment
- **THEN** they SHALL be available to any profile extending base via `${LANGFUSE_PUBLIC_KEY:-}` interpolation

### Requirement: Anthropic Client Auto-Instrumentation

The system SHALL support automatic tracing of Anthropic Claude API calls via `opentelemetry-instrumentation-anthropic`, creating generation-typed observations with full request/response capture.

#### Scenario: Automatic Claude call tracing
- **GIVEN** `OBSERVABILITY_PROVIDER=langfuse` and `AnthropicInstrumentor` is enabled
- **WHEN** the Anthropic client makes a `messages.create()` call
- **THEN** a generation observation SHALL be automatically created in Langfuse
- **AND** the observation SHALL include model name, input/output tokens, and request duration
- **AND** no manual tracing code SHALL be required at the call site

#### Scenario: Instrumentor disabled for non-Langfuse providers
- **GIVEN** `OBSERVABILITY_PROVIDER` is not `"langfuse"`
- **WHEN** the application starts
- **THEN** `AnthropicInstrumentor` SHALL NOT be activated
- **AND** Anthropic client calls SHALL not be instrumented

#### Scenario: Instrumentor graceful degradation
- **WHEN** `opentelemetry-instrumentation-anthropic` is not installed
- **THEN** the Langfuse provider SHALL log a warning
- **AND** the provider SHALL continue functioning without auto-instrumentation
- **AND** explicit `trace_llm_call()` SHALL still work

### Requirement: Pipeline Function Observability Decorators

The system SHALL use `@observe()` decorators on all pipeline functions to create hierarchical trace trees showing the full execution flow from ingestion through summarization, theme analysis, digest creation, and podcast script generation.

#### Scenario: Decorated pipeline function creates trace span
- **GIVEN** `OBSERVABILITY_PROVIDER=langfuse`
- **WHEN** a `@observe()`-decorated pipeline function executes
- **THEN** a span observation SHALL be created in Langfuse with the function name
- **AND** function inputs and outputs SHALL be automatically captured
- **AND** child LLM calls within the function SHALL be nested under the function span

#### Scenario: Decorator is no-op without Langfuse
- **GIVEN** `OBSERVABILITY_PROVIDER` is `"noop"` or any non-Langfuse provider
- **WHEN** a `@observe()`-decorated function executes
- **THEN** the decorator SHALL have zero overhead
- **AND** the function SHALL execute normally without tracing

#### Scenario: Nested trace tree for daily pipeline
- **GIVEN** `OBSERVABILITY_PROVIDER=langfuse`
- **WHEN** the daily pipeline runs (ingest → summarize → digest)
- **THEN** the Langfuse trace SHALL show a hierarchical tree with pipeline stage spans
- **AND** individual LLM generation observations SHALL be nested under their pipeline stage

#### Scenario: Decorated function raises exception
- **GIVEN** `OBSERVABILITY_PROVIDER=langfuse`
- **WHEN** a `@observe()`-decorated function raises an exception
- **THEN** the span observation SHALL be set to ERROR status with the exception details
- **AND** the exception SHALL propagate to the caller unchanged
- **AND** the Langfuse SDK SHALL NOT swallow or modify the exception

#### Scenario: Legacy raw OTel span helpers removed
- **GIVEN** `@observe()` decorators are applied to pipeline functions
- **WHEN** the codebase is updated
- **THEN** `_summarization_span()` and `_get_tracer()` in `src/processors/summarizer.py` SHALL be removed
- **AND** `_get_tracer()` and raw OTel span creation in `_pipeline_stage_span()` and `_ingest_source()` in `src/cli/pipeline_commands.py` SHALL be replaced with `@observe()`
- **AND** OTel metrics calls (`record_pipeline_stage_*`) SHALL be preserved (metrics are orthogonal to Langfuse tracing)

### Requirement: Pipeline Context Propagation

The system SHALL use `propagate_attributes()` to flow session and user context to all observations within a pipeline run.

#### Scenario: Session context flows to child observations
- **GIVEN** `OBSERVABILITY_PROVIDER=langfuse`
- **WHEN** a pipeline run starts with `propagate_attributes(session_id=..., tags=[...])`
- **THEN** all child observations (spans and generations) SHALL inherit the session_id and tags
- **AND** the Langfuse UI SHALL group all observations under the same session

#### Scenario: Context propagation is no-op without Langfuse
- **GIVEN** `OBSERVABILITY_PROVIDER` is not `"langfuse"`
- **WHEN** `propagate_attributes()` is used
- **THEN** it SHALL have zero effect and zero overhead

### Requirement: Langfuse SDK Configuration Settings

The system SHALL support configuration settings for the Langfuse SDK v4 feature set.

#### Scenario: Sample rate configuration
- **WHEN** `LANGFUSE_SAMPLE_RATE` is set to a value between 0.0 and 1.0
- **THEN** the Langfuse SDK SHALL only export that fraction of traces
- **AND** the default SHALL be 1.0 (export all traces)

#### Scenario: Debug mode
- **WHEN** `LANGFUSE_DEBUG` is set to `"true"`
- **THEN** the Langfuse SDK SHALL enable debug logging for dropped spans and trace diagnostics

#### Scenario: Environment tagging
- **WHEN** `LANGFUSE_ENVIRONMENT` is set (e.g., `"production"`, `"staging"`)
- **THEN** all traces SHALL include the environment tag for filtering in the Langfuse UI

#### Scenario: Invalid sample rate clamped
- **WHEN** `LANGFUSE_SAMPLE_RATE` is set to a value outside the range 0.0-1.0
- **THEN** the system SHALL clamp the value to the nearest valid bound (0.0 or 1.0)
- **AND** the system SHALL log a WARNING about the invalid value
