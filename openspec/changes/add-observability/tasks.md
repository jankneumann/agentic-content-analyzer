# Implementation Tasks

## 1. Setup OpenTelemetry

- [ ] 1.1 Add OpenTelemetry dependencies to pyproject.toml:
  - `opentelemetry-api`
  - `opentelemetry-sdk`
  - `opentelemetry-exporter-otlp`
  - `opentelemetry-instrumentation-fastapi`
  - `opentelemetry-instrumentation-sqlalchemy`
  - `opentelemetry-instrumentation-httpx`
- [ ] 1.2 Create `src/telemetry/__init__.py`
- [ ] 1.3 Create `src/telemetry/config.py` with OTEL setup
- [ ] 1.4 Configure tracer provider and span processors
- [ ] 1.5 Add OTLP exporter configuration

## 2. Setup Opik

- [ ] 2.1 Add `opik` to pyproject.toml
- [ ] 2.2 Create Opik configuration in `src/telemetry/config.py`
- [ ] 2.3 Add Opik to docker-compose.yml (self-hosted option)
- [ ] 2.4 Document Comet Cloud setup option
- [ ] 2.5 Create helper for Opik initialization

## 3. Configuration

- [ ] 3.1 Add telemetry settings to `src/config/settings.py`:
  - `otel_enabled: bool = False`
  - `otel_service_name: str`
  - `otel_exporter_endpoint: str`
  - `opik_enabled: bool = False`
  - `opik_api_key: str | None`
  - `opik_workspace: str | None`
  - `opik_url: str | None` (self-hosted)
- [ ] 3.2 Add environment variable documentation
- [ ] 3.3 Create development defaults

## 4. Health Endpoints

- [ ] 4.1 Create `src/api/health_routes.py`
- [ ] 4.2 Implement `GET /health` (liveness)
- [ ] 4.3 Implement `GET /ready` (readiness with checks)
- [ ] 4.4 Add database health check
- [ ] 4.5 Add Redis health check
- [ ] 4.6 Add configurable timeout for checks
- [ ] 4.7 Register health routes in app.py

## 5. Metrics Endpoint

- [ ] 5.1 Add `prometheus-client` to dependencies
- [ ] 5.2 Create `src/telemetry/metrics.py`
- [ ] 5.3 Define core metrics:
  - `api_requests_total`
  - `api_request_duration_seconds`
  - `ingestion_total` by source
  - `summarization_total` by model
  - `llm_tokens_total` by model
- [ ] 5.4 Implement `GET /metrics` endpoint
- [ ] 5.5 Add metrics middleware to FastAPI

## 6. Instrument Pipeline

- [ ] 6.1 Create `src/telemetry/spans.py` with helpers
- [ ] 6.2 Add `@opik.track` to agent summarization methods
- [ ] 6.3 Add `@opik.track` to digest creation methods
- [ ] 6.4 Add OpenTelemetry spans to ingestion services
- [ ] 6.5 Add spans to parser operations
- [ ] 6.6 Ensure trace context propagates through async operations

## 7. Error Handling

- [ ] 7.1 Create structured error response model
- [ ] 7.2 Update exception handlers to include trace_id
- [ ] 7.3 Add error context capture in spans
- [ ] 7.4 Create error code enum for categorization

## 8. Middleware

- [ ] 8.1 Create `src/api/middleware/telemetry.py`
- [ ] 8.2 Add request tracing middleware
- [ ] 8.3 Add trace_id to response headers
- [ ] 8.4 Log trace_id with each request

## 9. Testing

- [ ] 9.1 Add telemetry disable flag for tests
- [ ] 9.2 Test health endpoints
- [ ] 9.3 Test metrics endpoint
- [ ] 9.4 Test error response format
- [ ] 9.5 Verify spans are created correctly (integration test)

## 10. Documentation

- [ ] 10.1 Document telemetry configuration
- [ ] 10.2 Document Opik setup (self-hosted and cloud)
- [ ] 10.3 Document metrics available
- [ ] 10.4 Add troubleshooting guide
