# Design: Observability with OpenTelemetry and Opik

## Context

The application processes content through multiple stages (ingestion → summarization → digest creation) using LLM APIs. Without observability, debugging production issues requires log diving and guesswork.

## Goals

1. Trace requests through the entire pipeline
2. Track LLM-specific metrics (tokens, latency, costs)
3. Provide health endpoints for orchestration
4. Capture errors with context for debugging

## Non-Goals

1. Full APM solution (Datadog/New Relic level)
2. Log aggregation (separate concern)
3. Alerting configuration (done in Opik dashboard)

## Decisions

### Decision 1: Dual Telemetry Stack

**What**: Use OpenTelemetry for general tracing + Opik for LLM-specific monitoring.

**Why**:
- OpenTelemetry provides vendor-neutral instrumentation
- Opik adds LLM-specific features (prompt logging, token tracking)
- Both integrate seamlessly

```python
# General tracing with OpenTelemetry
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("process_content"):
    # Generic span for any operation
    pass

# LLM-specific tracing with Opik
import opik

@opik.track
def summarize_content(content: Content) -> Summary:
    # Automatically logs: prompt, completion, tokens, latency
    pass
```

### Decision 2: Opik Deployment

**What**: Support both self-hosted and Comet Cloud.

**Why**: Self-hosted for development, cloud option for production simplicity.

```yaml
# docker-compose.yml addition for self-hosted
services:
  opik:
    image: ghcr.io/comet-ml/opik:latest
    ports:
      - "5173:5173"   # UI
      - "5174:5174"   # API
```

### Decision 3: Health Check Endpoints

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
    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks
    }
```

### Decision 4: Structured Error Responses

**What**: Consistent error format with trace IDs.

```python
{
    "error": {
        "code": "SUMMARIZATION_FAILED",
        "message": "Failed to generate summary",
        "trace_id": "abc123def456",
        "details": {
            "content_id": 42,
            "model": "claude-haiku-4-5"
        }
    }
}
```

### Decision 5: Pipeline Instrumentation

**What**: Add spans at pipeline boundaries.

```
[Request] ──▶ [Ingestion] ──▶ [Parsing] ──▶ [Summarization] ──▶ [Response]
    │              │              │               │
    └──────────────┴──────────────┴───────────────┘
                    Trace spans
```

```python
# src/processors/summarizer.py
@opik.track(name="summarize_content")
async def summarize_content(content_id: int) -> Summary:
    with tracer.start_as_current_span("fetch_content"):
        content = await get_content(content_id)

    with tracer.start_as_current_span("generate_summary"):
        # Opik tracks the LLM call automatically
        summary = await agent.summarize(content)

    return summary
```

### Decision 6: Metrics Collection

**What**: Prometheus-compatible metrics endpoint.

```python
# Key metrics
newsletter_ingestion_total      # Counter
summarization_duration_seconds  # Histogram
llm_tokens_used_total          # Counter by model
api_requests_total             # Counter by endpoint, status
```

## File Structure

```
src/
├── telemetry/
│   ├── __init__.py
│   ├── config.py           # OpenTelemetry + Opik setup
│   ├── spans.py            # Custom span helpers
│   └── metrics.py          # Prometheus metrics
├── api/
│   ├── health_routes.py    # /health, /ready, /metrics
│   └── middleware/
│       └── telemetry.py    # Request tracing middleware
```

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Performance overhead | Sampling in production (10% of traces) |
| Sensitive data in traces | Scrub PII from span attributes |
| Opik availability | Graceful degradation if Opik down |
