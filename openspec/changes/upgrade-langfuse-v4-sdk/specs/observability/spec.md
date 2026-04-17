## MODIFIED Requirements

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

## ADDED Requirements

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

The system SHALL use `@observe()` decorators on key pipeline functions to create hierarchical trace trees showing the full execution flow from ingestion through digest creation.

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

## REMOVED Requirements

### Requirement: Langfuse raw OTel export with gen_ai.* attributes
**Reason:** Replaced by native Langfuse SDK which provides generation-typed observations, automatic cost tracking, and `@observe()` support. Raw OTel export sent generic spans that Langfuse could not recognize as LLM generations.
**Migration:** No user action required. The `LangfuseProvider` internal implementation changes but the `ObservabilityProvider` Protocol interface is unchanged. If raw OTel export is needed, use `OBSERVABILITY_PROVIDER=otel` instead.
