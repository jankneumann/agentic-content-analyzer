# Implementation Tasks

## 1. Setup OpenTelemetry SDK

- [x] 1.1 Add OpenTelemetry dependencies to pyproject.toml:
  - `opentelemetry-api`
  - `opentelemetry-sdk`
  - `opentelemetry-exporter-otlp-proto-http` (NOT grpc - Opik requires HTTP)
  - `opentelemetry-instrumentation-fastapi`
  - `opentelemetry-instrumentation-sqlalchemy`
  - `opentelemetry-instrumentation-httpx`
- [x] 1.2 Create `src/telemetry/__init__.py`
- [x] 1.3 Create `src/telemetry/otel_setup.py` with OTel setup (replaces config.py)
- [x] 1.4 Configure tracer provider with batch span processor
- [x] 1.5 Configure OTLP HTTP exporter (configurable endpoint)

## 2. Configure Provider Factory Pattern

- [x] 2.1 Create `src/telemetry/providers/base.py` (ObservabilityProvider Protocol)
- [x] 2.2 Create `src/telemetry/providers/noop.py` (NoopProvider — default)
- [x] 2.3 Create `src/telemetry/providers/factory.py` (get_observability_provider)
- [x] 2.4 Create `src/telemetry/providers/opik.py` (Opik/Comet Cloud via OTel + gen_ai.*)
- [x] 2.5 Create `src/telemetry/providers/braintrust.py` (Braintrust native SDK)
- [x] 2.6 Create `src/telemetry/providers/otel_provider.py` (generic OTLP backend)

## 3. Configuration Settings

- [x] 3.1 Add telemetry settings to `src/config/settings.py`:
  - `observability_provider: ObservabilityProviderType = "noop"`
  - `otel_enabled: bool = False`
  - `otel_service_name: str = "newsletter-aggregator"`
  - `otel_exporter_otlp_endpoint: str | None`
  - `otel_exporter_otlp_headers: str | None`
  - `otel_log_prompts: bool = False` (PII control)
  - `otel_traces_sampler: str` and `otel_traces_sampler_arg: float`
  - `opik_api_key: str | None`
  - `opik_workspace: str | None`
  - `opik_project_name: str`
  - `braintrust_api_key: str | None`
  - `braintrust_project_name: str`
  - `braintrust_api_url: str`
  - `health_check_timeout_seconds: int = 5`
- [x] 3.2 Add environment variable documentation (.env.example)
- [x] 3.3 Add provider validation (braintrust requires API key, otel requires endpoint)

## 4. Health Endpoints

- [x] 4.1 Create `src/api/health_routes.py`
- [x] 4.2 Implement `GET /health` (liveness)
- [x] 4.3 Implement `GET /ready` (readiness with checks)
- [x] 4.4 Add database health check (via existing storage.database.health_check)
- [x] 4.5 Add queue health check (PGQueuer connection check)
- [x] 4.6 Add configurable timeout for checks
- [x] 4.7 Register health routes in app.py (replaces inline /health)

## 5. Metrics

- [x] 5.1 Create `src/telemetry/metrics.py`
- [x] 5.2 Define core metrics using OTel Metrics API:
  - `llm.requests` (Counter) by model, provider
  - `llm.tokens` (Counter) by model, provider, direction
  - `llm.request.duration` (Histogram) by model, provider
  - `ingestion.total` (Counter) by source_type
- [ ] 5.3 Implement `GET /metrics` endpoint (Prometheus format) — deferred
- [ ] 5.4 Configure PrometheusMetricReader — deferred

## 6. LLM Instrumentation

- [x] 6.1 Add `_trace_llm_call()` helper to LLMRouter
- [x] 6.2 Instrument `generate()` with timing and telemetry
- [x] 6.3 Instrument `generate_with_tools()` with timing, telemetry, and metadata
- [x] 6.4 Telemetry failures are silently caught (never affect LLM calls)

## 7. Pipeline Instrumentation

- [x] 7.1 Provider protocol includes `start_span()` context manager
- [ ] 7.2 Add spans to ingestion services (Gmail, RSS, YouTube) — deferred
- [ ] 7.3 Add spans to parser operations — deferred
- [ ] 7.4 Add spans to content processing pipeline — deferred

## 8. Auto-Instrumentation

- [x] 8.1 Configure FastAPIInstrumentor in app startup
- [x] 8.2 Configure SQLAlchemyInstrumentor for database queries
- [x] 8.3 Configure HTTPXClientInstrumentor for outbound HTTP
- [x] 8.4 Only set TracerProvider if not already set by LLM provider

## 9. Error Handling

- [x] 9.1 Create structured error response model with trace_id
- [x] 9.2 Create `src/api/middleware/error_handler.py` with register_error_handlers()
- [x] 9.3 Unhandled exceptions return JSON with error, detail, trace_id

## 10. Middleware

- [x] 10.1 Create `src/api/middleware/telemetry.py`
- [x] 10.2 Add trace_id to response headers (`X-Trace-Id`)
- [x] 10.3 Register TraceIdMiddleware in app.py

## 11. Testing

- [x] 11.1 Tests run with noop provider by default (OTEL_ENABLED=false)
- [x] 11.2 Test health endpoints (200 when healthy, 503 when not)
- [x] 11.3 Test metrics record functions (no-op when disabled, counters when enabled)
- [x] 11.4 Test error response includes trace_id
- [x] 11.5 Test provider factory, protocol compliance, noop behavior
- [x] 11.6 Test settings defaults and validation
- [x] 11.7 Test OTel setup (disabled, no endpoint, header parsing)
- [x] 11.8 Test LLM Router telemetry integration
- [x] 11.9 All 67 observability tests passing

## 12. Documentation

- [x] 12.1 Add observability section to CLAUDE.md
- [x] 12.2 Add telemetry configuration to docs/SETUP.md
- [x] 12.3 Add environment variables to .env.example
- [ ] 12.4 Document LLM attributes for custom dashboards — deferred
- [ ] 12.5 Add troubleshooting guide (OTLP HTTP vs gRPC, etc.) — deferred
