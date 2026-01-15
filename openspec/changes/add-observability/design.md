# Design: Observability with OpenTelemetry and Opik

## Context

The application processes content through multiple stages (ingestion → summarization → digest creation) using LLM APIs. Without observability, debugging production issues requires log diving and guesswork.

## Goals

1. Trace requests through the entire pipeline with unified instrumentation
2. Track LLM-specific metrics (tokens, latency, costs) via standard OTel attributes
3. Provide health endpoints for orchestration
4. Capture errors with context for debugging

## Non-Goals

1. Full APM solution (Datadog/New Relic level)
2. Log aggregation (separate concern)
3. Alerting configuration (done in Opik dashboard)
4. Separate Opik SDK (use pure OpenTelemetry)

## Decisions

### Decision 1: OpenTelemetry as Single Instrumentation Layer

**What**: Use OpenTelemetry exclusively for all telemetry, export to Opik via OTLP.

**Why**:
- Single, consistent instrumentation API
- Opik natively supports OTel traces via OTLP endpoint
- No need to learn multiple SDKs
- Future-proof: can switch backends without code changes

```python
# All tracing through OpenTelemetry
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

# Configure exporter to send to Opik
exporter = OTLPSpanExporter(
    endpoint="https://www.comet.com/opik/api/v1/traces",
    headers={"opik-project-name": "newsletter-aggregator"}
)
```

### Decision 2: LLM Semantic Conventions

**What**: Use emerging gen_ai.* OTel semantic conventions for LLM calls.

**Why**: Opik recognizes these attributes and provides LLM-specific visualization.

```python
with tracer.start_as_current_span("llm.completion") as span:
    # Standard gen_ai attributes that Opik understands
    span.set_attribute("gen_ai.system", "anthropic")
    span.set_attribute("gen_ai.request.model", "claude-sonnet-4-20250514")
    span.set_attribute("gen_ai.usage.input_tokens", usage.input_tokens)
    span.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens)
    span.set_attribute("gen_ai.request.max_tokens", 4096)
    span.set_attribute("gen_ai.response.finish_reason", "stop")

    # Optional: prompt/completion content (may contain PII)
    if settings.log_prompts:
        span.set_attribute("gen_ai.prompt", prompt[:1000])
        span.set_attribute("gen_ai.completion", completion[:1000])
```

### Decision 3: Auto-Instrumentation

**What**: Use OTel auto-instrumentation for common libraries.

**Why**: Automatic tracing without manual code changes.

```python
# src/telemetry/config.py
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def configure_telemetry(app: FastAPI, engine: Engine):
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
    HTTPXClientInstrumentor().instrument()
```

### Decision 4: Opik Deployment Options

**What**: Support both self-hosted and Comet Cloud.

**Self-hosted** (development):
```yaml
# docker-compose.yml
services:
  opik:
    image: ghcr.io/comet-ml/opik:latest
    ports:
      - "5173:5173"   # UI
    environment:
      - OPIK_OTEL_ENABLED=true
```

**Comet Cloud** (production):
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=https://www.comet.com/opik/api
OPIK_API_KEY=your-api-key
OPIK_WORKSPACE=your-workspace
```

### Decision 5: Health Check Endpoints

**What**: Kubernetes-style health endpoints.

```python
# /health - Liveness (is the process alive?)
@router.get("/health")
async def health():
    return {"status": "healthy"}

# /ready - Readiness (can it handle traffic?)
@router.get("/ready")
async def ready():
    checks = {
        "database": await check_database(),
        "redis": await check_redis(),
    }
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    return JSONResponse(
        content={
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks
        },
        status_code=status_code
    )
```

### Decision 6: Structured Error Responses

**What**: Consistent error format with trace IDs.

```python
{
    "error": {
        "code": "SUMMARIZATION_FAILED",
        "message": "Failed to generate summary",
        "trace_id": "abc123def456",  # From current OTel span
        "details": {
            "content_id": 42,
            "model": "claude-haiku-4-5"
        }
    }
}
```

### Decision 7: Pipeline Instrumentation

**What**: Add spans at pipeline boundaries with parent-child relationships.

```
[Request] ──▶ [Ingestion] ──▶ [Parsing] ──▶ [Summarization] ──▶ [Response]
    │              │              │               │
    └──────────────┴──────────────┴───────────────┘
                    All spans linked by trace_id
                    LLM calls have gen_ai.* attributes
```

```python
# src/processors/summarizer.py
async def summarize_content(content_id: int) -> Summary:
    with tracer.start_as_current_span("summarize_content") as span:
        span.set_attribute("content_id", content_id)

        with tracer.start_as_current_span("fetch_content"):
            content = await get_content(content_id)

        with tracer.start_as_current_span("llm.completion") as llm_span:
            llm_span.set_attribute("gen_ai.system", "anthropic")
            llm_span.set_attribute("gen_ai.request.model", model)

            response = await client.messages.create(...)

            llm_span.set_attribute("gen_ai.usage.input_tokens", response.usage.input_tokens)
            llm_span.set_attribute("gen_ai.usage.output_tokens", response.usage.output_tokens)

        return summary
```

### Decision 8: Metrics via OTel Metrics API

**What**: Use OTel Metrics API with Prometheus exporter.

```python
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader

meter = metrics.get_meter(__name__)

# Counters
requests_counter = meter.create_counter(
    "api_requests_total",
    description="Total API requests"
)

# Histograms
llm_latency = meter.create_histogram(
    "llm_request_duration_seconds",
    description="LLM request latency"
)

# Observable gauges
token_usage = meter.create_observable_gauge(
    "llm_tokens_total",
    callbacks=[get_token_usage]
)
```

## File Structure

```
src/
├── telemetry/
│   ├── __init__.py
│   ├── config.py           # OTel SDK + Opik exporter setup
│   ├── spans.py            # Custom span helpers for LLM calls
│   └── metrics.py          # Prometheus metrics
├── api/
│   ├── health_routes.py    # /health, /ready, /metrics
│   └── middleware/
│       └── error_handler.py  # Structured errors with trace_id
```

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Performance overhead | Sampling in production (configurable %) |
| Sensitive data in traces | Config flag to disable prompt logging |
| Opik availability | Async exporter with buffer, graceful degradation |
| OTLP HTTP vs gRPC | Use HTTP (Opik requires http exporter, not gRPC) |
