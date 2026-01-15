# Change: Add Observability with OpenTelemetry and Opik

## Why

The application lacks production observability, making it difficult to:
- Debug issues in LLM pipelines (summarization, digest creation)
- Track token usage and costs across different models
- Monitor API health and performance
- Identify slow or failing operations

By adding observability with OpenTelemetry and Opik:

1. **Unified telemetry**: Single instrumentation layer for all traces (HTTP, DB, LLM)
2. **LLM-specific insights**: Token usage, prompt/completion logging, hallucination detection
3. **Distributed tracing**: Follow requests across ingestion → processing → delivery
4. **Production debugging**: Identify issues with traces, not guesswork
5. **Standards-based**: OpenTelemetry ensures vendor-neutral instrumentation

## Technology Stack

### OpenTelemetry (Unified Instrumentation)
- **Purpose**: Single instrumentation layer for ALL telemetry
- **Components**: Traces, metrics, logs
- **Exporters**: OTLP HTTP exporter to Opik
- **Why**: Vendor-neutral, consistent API, future-proof

### Opik as OpenTelemetry Backend
- **Purpose**: Receive and visualize OTel traces with LLM-specific features
- **Integration**: Native OTel support via OTLP HTTP endpoint
- **Features**:
  - Standard trace visualization
  - LLM-specific attributes (tokens, model, prompt/completion)
  - LLM-as-judge evaluation
  - Hallucination detection
  - RAG metrics (answer relevance, context precision)
- **Deployment**: Self-hosted (Docker Compose) or Comet Cloud
- **Reference**: [Opik OpenTelemetry Integration](https://www.comet.com/docs/opik/tracing/opentelemetry/overview)

## Unified Telemetry Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Application Code                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  FastAPI          SQLAlchemy        LLM Calls        Custom     │
│  Requests         Queries           (Claude, etc)    Spans      │
│     │                │                   │             │        │
│     └────────────────┴───────────────────┴─────────────┘        │
│                              │                                   │
│                    OpenTelemetry SDK                             │
│                    (single instrumentation layer)                │
│                              │                                   │
│                    OTLP HTTP Exporter                            │
│                              │                                   │
└──────────────────────────────┼───────────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │        Opik         │
                    │  (OTel Backend)     │
                    │                     │
                    │  • Trace viewer     │
                    │  • LLM insights     │
                    │  • Token tracking   │
                    │  • Evaluations      │
                    └─────────────────────┘
```

## What Changes

### Instrumentation Layer (OpenTelemetry)
- **NEW**: OpenTelemetry SDK configuration in `src/telemetry/`
- **NEW**: OTLP HTTP exporter configured to send to Opik
- **NEW**: Auto-instrumentation for FastAPI, SQLAlchemy, httpx
- **NEW**: Custom spans with LLM attributes for pipeline stages
- **MODIFIED**: Agent implementations to add OTel attributes (model, tokens)
- **MODIFIED**: Settings for telemetry configuration

### Health & Metrics
- **NEW**: `/health` endpoint (liveness)
- **NEW**: `/ready` endpoint (readiness with DB/Redis checks)
- **NEW**: `/metrics` endpoint (Prometheus format)
- **MODIFIED**: API app to expose health endpoints

### Error Handling
- **NEW**: Structured error response format with trace_id
- **NEW**: Error context capture in OTel spans
- **MODIFIED**: Exception handlers to include trace IDs in responses

## Configuration

```bash
# OpenTelemetry (unified telemetry layer)
OTEL_ENABLED=true
OTEL_SERVICE_NAME=newsletter-aggregator
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf

# Opik as OTel backend
OTEL_EXPORTER_OTLP_ENDPOINT=https://www.comet.com/opik/api  # Comet Cloud
# OR for self-hosted Opik:
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:5173/api

# Opik project (via OTel headers)
OTEL_EXPORTER_OTLP_HEADERS="opik-project-name=newsletter-aggregator"

# For Comet Cloud authentication
OPIK_API_KEY=your-api-key
OPIK_WORKSPACE=your-workspace

# Health Checks
HEALTH_CHECK_TIMEOUT_SECONDS=5
```

## LLM Span Attributes

For LLM calls, we add semantic conventions:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("llm.completion") as span:
    span.set_attribute("gen_ai.system", "anthropic")
    span.set_attribute("gen_ai.request.model", "claude-sonnet-4-20250514")
    span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
    span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
    span.set_attribute("gen_ai.request.max_tokens", max_tokens)
    # Opik will recognize these and provide LLM-specific visualization
```

## Impact

- **New spec**: `observability` - Telemetry and monitoring
- **New code**:
  - `src/telemetry/` - OpenTelemetry setup, exporter config
  - `src/api/health_routes.py` - Health endpoints
- **Modified**:
  - `src/agents/` - Add OTel span attributes for LLM calls
  - `src/processors/` - Add span instrumentation
  - `src/api/app.py` - Register health routes, add OTel middleware
  - `src/config/settings.py` - Telemetry settings
- **Dependencies**:
  - `opentelemetry-api`, `opentelemetry-sdk`
  - `opentelemetry-exporter-otlp-proto-http`
  - `opentelemetry-instrumentation-fastapi`
  - `opentelemetry-instrumentation-sqlalchemy`
  - `opentelemetry-instrumentation-httpx`

## Related Proposals

- **add-deployment-pipeline**: Includes Opik service in docker-compose for self-hosted
- **add-test-infrastructure**: Telemetry disabled in tests by default
- **add-api-security-hardening**: Health endpoints publicly accessible, metrics may need auth
- **add-supabase-cloud-database**: Database health checks in `/ready` endpoint

## Non-Goals

- Separate Opik SDK (use OTel for everything)
- Full APM solution (use Datadog/New Relic if needed)
- Log aggregation (can add ELK/Loki later)
- Alerting rules (configure in Opik dashboard)
