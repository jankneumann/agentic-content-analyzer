# Implementation Tasks

## 1. Setup OpenTelemetry SDK

- [ ] 1.1 Add OpenTelemetry dependencies to pyproject.toml:
  - `opentelemetry-api`
  - `opentelemetry-sdk`
  - `opentelemetry-exporter-otlp-proto-http` (NOT grpc - Opik requires HTTP)
  - `opentelemetry-instrumentation-fastapi`
  - `opentelemetry-instrumentation-sqlalchemy`
  - `opentelemetry-instrumentation-httpx`
- [ ] 1.2 Create `src/telemetry/__init__.py`
- [ ] 1.3 Create `src/telemetry/config.py` with OTel setup
- [ ] 1.4 Configure tracer provider with batch span processor
- [ ] 1.5 Configure OTLP HTTP exporter to send to Opik

## 2. Configure Opik as OTel Backend

- [ ] 2.1 Configure OTLP endpoint for Comet Cloud:
  - `OTEL_EXPORTER_OTLP_ENDPOINT=https://www.comet.com/opik/api`
  - `OTEL_EXPORTER_OTLP_HEADERS=opik-project-name=<project>`
- [ ] 2.2 Configure OTLP endpoint for self-hosted Opik
- [ ] 2.3 Add Opik service to docker-compose.yml (self-hosted option)
- [ ] 2.4 Document both deployment options
- [ ] 2.5 Add `OPIK_API_KEY` and `OPIK_WORKSPACE` for Comet Cloud auth

## 3. Configuration Settings

- [ ] 3.1 Add telemetry settings to `src/config/settings.py`:
  - `otel_enabled: bool = False`
  - `otel_service_name: str = "newsletter-aggregator"`
  - `otel_exporter_otlp_endpoint: str | None`
  - `otel_exporter_otlp_headers: str | None`
  - `otel_log_prompts: bool = False` (PII control)
  - `opik_api_key: str | None` (for Comet Cloud)
  - `opik_workspace: str | None`
- [ ] 3.2 Add environment variable documentation
- [ ] 3.3 Create development defaults (localhost Opik)

## 4. Health Endpoints

- [ ] 4.1 Create `src/api/health_routes.py`
- [ ] 4.2 Implement `GET /health` (liveness)
- [ ] 4.3 Implement `GET /ready` (readiness with checks)
- [ ] 4.4 Add database health check
- [ ] 4.5 Add Redis health check
- [ ] 4.6 Add configurable timeout for checks
- [ ] 4.7 Register health routes in app.py

## 5. Metrics Endpoint

- [ ] 5.1 Add `opentelemetry-exporter-prometheus` to dependencies
- [ ] 5.2 Create `src/telemetry/metrics.py`
- [ ] 5.3 Define core metrics using OTel Metrics API:
  - `api_requests_total` (Counter)
  - `api_request_duration_seconds` (Histogram)
  - `ingestion_total` by source (Counter)
  - `llm_requests_total` by model (Counter)
  - `llm_tokens_total` by model, direction (Counter)
  - `llm_request_duration_seconds` (Histogram)
- [ ] 5.4 Implement `GET /metrics` endpoint (Prometheus format)
- [ ] 5.5 Configure PrometheusMetricReader

## 6. LLM Instrumentation (gen_ai.* attributes)

- [ ] 6.1 Create `src/telemetry/llm.py` with LLM span helper
- [ ] 6.2 Define `@trace_llm_call` decorator that adds:
  - `gen_ai.system` (anthropic, openai, etc.)
  - `gen_ai.request.model`
  - `gen_ai.usage.input_tokens`
  - `gen_ai.usage.output_tokens`
  - `gen_ai.request.max_tokens`
  - `gen_ai.response.finish_reason`
- [ ] 6.3 Optionally log prompt/completion (controlled by setting)
- [ ] 6.4 Apply to Claude SDK agent
- [ ] 6.5 Apply to OpenAI agent (if used)
- [ ] 6.6 Apply to summarization processors
- [ ] 6.7 Apply to digest creation processors

## 7. Pipeline Instrumentation

- [ ] 7.1 Create `src/telemetry/spans.py` with span helpers
- [ ] 7.2 Add spans to ingestion services (Gmail, RSS, YouTube)
- [ ] 7.3 Add spans to parser operations
- [ ] 7.4 Add spans to content processing pipeline
- [ ] 7.5 Ensure trace context propagates through async operations
- [ ] 7.6 Add relevant attributes (content_id, source_type, etc.)

## 8. Auto-Instrumentation

- [ ] 8.1 Configure FastAPIInstrumentor in app startup
- [ ] 8.2 Configure SQLAlchemyInstrumentor for database queries
- [ ] 8.3 Configure HTTPXClientInstrumentor for outbound HTTP
- [ ] 8.4 Verify trace propagation across services

## 9. Error Handling

- [ ] 9.1 Create structured error response model with trace_id
- [ ] 9.2 Update exception handlers to get trace_id from current span
- [ ] 9.3 Add error context capture in spans (set_status, record_exception)
- [ ] 9.4 Create error code enum for categorization

## 10. Middleware

- [ ] 10.1 Create `src/api/middleware/telemetry.py`
- [ ] 10.2 Add trace_id to response headers (`X-Trace-Id`)
- [ ] 10.3 Log trace_id with structured logging

## 11. Testing

- [ ] 11.1 Add telemetry disable flag for tests (OTEL_ENABLED=false)
- [ ] 11.2 Test health endpoints (200 when healthy, 503 when not)
- [ ] 11.3 Test metrics endpoint returns Prometheus format
- [ ] 11.4 Test error response includes trace_id
- [ ] 11.5 Integration test: verify spans created and exported

## 12. Documentation

- [ ] 12.1 Document telemetry configuration options
- [ ] 12.2 Document Opik setup (self-hosted and Comet Cloud)
- [ ] 12.3 Document available metrics
- [ ] 12.4 Document LLM attributes for custom dashboards
- [ ] 12.5 Add troubleshooting guide (OTLP HTTP vs gRPC, etc.)
