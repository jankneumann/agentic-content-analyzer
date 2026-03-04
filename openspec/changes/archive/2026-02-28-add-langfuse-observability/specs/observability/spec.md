# observability Delta Spec

## ADDED Requirements

### Requirement: Langfuse Observability Provider

The system SHALL support Langfuse as an LLM observability provider, using OpenTelemetry with OTLP/HTTP export and gen_ai.* semantic conventions. Langfuse SHALL be selectable via `OBSERVABILITY_PROVIDER=langfuse` and support both Langfuse Cloud and self-hosted deployments.

#### Scenario: Select Langfuse provider via configuration
- **WHEN** `OBSERVABILITY_PROVIDER` is set to `"langfuse"`
- **THEN** the telemetry factory SHALL instantiate `LangfuseProvider`
- **AND** the provider SHALL use `OTLPSpanExporter` with HTTP protocol (not gRPC)

#### Scenario: Langfuse Cloud authentication
- **WHEN** `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are configured
- **THEN** the provider SHALL construct a Basic Auth header as `base64(public_key:secret_key)`
- **AND** the OTLP endpoint SHALL be `{LANGFUSE_BASE_URL}/api/public/otel`
- **AND** the default base URL SHALL be `https://cloud.langfuse.com`

#### Scenario: Self-hosted Langfuse endpoint
- **WHEN** `LANGFUSE_BASE_URL` is set to a custom URL (e.g., `http://localhost:3100`)
- **THEN** the OTLP endpoint SHALL use that base URL instead of the cloud default
- **AND** traces SHALL be sent to `{custom_base_url}/api/public/otel`

#### Scenario: Missing API keys warning
- **WHEN** `OBSERVABILITY_PROVIDER=langfuse` is set without `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`
- **THEN** the system SHALL log at WARNING level about missing credentials
- **AND** the provider SHALL still attempt to send traces without authentication (self-hosted may not require auth)

#### Scenario: Partial API keys warning
- **WHEN** only one of `LANGFUSE_PUBLIC_KEY` or `LANGFUSE_SECRET_KEY` is configured (not both)
- **THEN** the system SHALL log at WARNING level about incomplete credentials
- **AND** the provider SHALL NOT send an auth header (partial Basic Auth is invalid)

#### Scenario: Trace export failure (Langfuse unreachable)
- **WHEN** the Langfuse OTLP endpoint is unreachable (connection refused, timeout, DNS failure)
- **THEN** the OTel BatchSpanProcessor SHALL handle the failure internally (retry then drop)
- **AND** the application SHALL NOT be affected (fail-safe design)
- **AND** no exceptions SHALL propagate to calling code

#### Scenario: Authentication rejection
- **WHEN** Langfuse rejects traces with HTTP 401 or 403 (invalid credentials)
- **THEN** the OTel BatchSpanProcessor SHALL handle the failure internally
- **AND** the application SHALL NOT be affected

#### Scenario: LLM call tracing with gen_ai attributes
- **WHEN** an LLM call is traced via `trace_llm_call()`
- **THEN** the provider SHALL create an `llm.completion` span
- **AND** the span SHALL include attributes: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`
- **AND** when `otel_log_prompts` is true, the span SHALL include `gen_ai.prompt` and `gen_ai.completion` (truncated to 1000 chars)
- **AND** when `otel_log_prompts` is false, the span SHALL NOT include `gen_ai.prompt` or `gen_ai.completion`

#### Scenario: Pipeline span creation
- **WHEN** `start_span()` is called with a name and attributes
- **THEN** the provider SHALL create an OTel span with the given name
- **AND** custom attributes SHALL be set on the span

#### Scenario: Provider lifecycle management
- **WHEN** `flush()` is called
- **THEN** the provider SHALL force-flush the OTel span processor
- **WHEN** `shutdown()` is called
- **THEN** the provider SHALL shut down the OTel tracer provider and release resources

#### Scenario: Graceful degradation without OTel packages
- **WHEN** OpenTelemetry packages are not installed
- **THEN** the provider SHALL log an error with installation instructions
- **AND** all trace methods SHALL be no-ops (never raise exceptions)

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

## MODIFIED Requirements

### Requirement: Observability Provider Selection

The system SHALL support five observability providers: noop, opik, braintrust, otel, and langfuse.

#### Scenario: Valid provider values
- **WHEN** `OBSERVABILITY_PROVIDER` is set to any of `"noop"`, `"opik"`, `"braintrust"`, `"otel"`, or `"langfuse"`
- **THEN** the system SHALL accept the value and instantiate the corresponding provider

#### Scenario: Factory dispatch for langfuse
- **WHEN** `observability_provider` is `"langfuse"` in settings
- **THEN** the factory SHALL create a `LangfuseProvider` with `public_key`, `secret_key`, `base_url`, `service_name`, and `log_prompts` from settings
