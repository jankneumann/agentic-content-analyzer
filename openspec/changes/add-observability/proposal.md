# Change: Add Observability with OpenTelemetry and Opik

## Why

The application lacks production observability, making it difficult to:
- Debug issues in LLM pipelines (summarization, digest creation)
- Track token usage and costs across different models
- Monitor API health and performance
- Identify slow or failing operations

By adding observability with OpenTelemetry and Opik:

1. **LLM-specific monitoring**: Track prompts, completions, token usage, and latency per model
2. **Distributed tracing**: Follow requests across ingestion → processing → delivery
3. **Production debugging**: Identify issues with traces, not guesswork
4. **Cost visibility**: Monitor token consumption to optimize model selection
5. **Standards-based**: OpenTelemetry ensures vendor-neutral instrumentation

## Technology Stack

### OpenTelemetry
- **Purpose**: Vendor-neutral instrumentation standard
- **Components**: Traces, metrics, logs
- **Why**: Future-proof, can export to any backend (Jaeger, Grafana, Datadog)

### Opik (comet-ml/opik)
- **Purpose**: LLM-specific observability platform
- **Features**:
  - Prompt/completion logging
  - Token usage tracking
  - LLM-as-judge evaluation
  - Hallucination detection
  - RAG metrics
- **Deployment**: Self-hosted (Docker Compose) or Comet Cloud
- **Why**: Purpose-built for LLM apps, integrates with Anthropic, OpenAI, LangChain

## What Changes

### Instrumentation Layer
- **NEW**: OpenTelemetry SDK configuration in `src/telemetry/`
- **NEW**: Opik integration for LLM call tracing
- **NEW**: Custom spans for pipeline stages (ingestion, summarization, digest)
- **MODIFIED**: Agent implementations to use `@opik.track` decorator
- **MODIFIED**: Settings for telemetry configuration

### Health & Metrics
- **NEW**: `/health` endpoint (liveness)
- **NEW**: `/ready` endpoint (readiness with DB/Redis checks)
- **NEW**: `/metrics` endpoint (Prometheus format)
- **MODIFIED**: API app to expose health endpoints

### Error Handling
- **NEW**: Structured error response format
- **NEW**: Error context capture in traces
- **MODIFIED**: Exception handlers to include trace IDs

## Configuration

```bash
# OpenTelemetry
OTEL_ENABLED=true
OTEL_SERVICE_NAME=newsletter-aggregator
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Opik
OPIK_ENABLED=true
OPIK_API_KEY=your-api-key           # For Comet Cloud
OPIK_WORKSPACE=your-workspace
# OR for self-hosted:
OPIK_URL=http://localhost:5173

# Health Checks
HEALTH_CHECK_TIMEOUT_SECONDS=5
```

## Impact

- **New spec**: `observability` - Telemetry and monitoring
- **New code**:
  - `src/telemetry/` - OpenTelemetry setup, Opik integration
  - `src/api/health_routes.py` - Health endpoints
- **Modified**:
  - `src/agents/` - Add tracing decorators
  - `src/processors/` - Add span instrumentation
  - `src/api/app.py` - Register health routes, add middleware
  - `src/config/settings.py` - Telemetry settings
- **Dependencies**:
  - `opentelemetry-api`, `opentelemetry-sdk`
  - `opentelemetry-instrumentation-fastapi`
  - `opentelemetry-instrumentation-sqlalchemy`
  - `opik`

## Related Proposals

- **add-deployment-pipeline**: Includes Opik service in docker-compose
- **add-test-infrastructure**: Telemetry disabled in tests by default
- **add-api-security-hardening**: Health endpoints need auth consideration

## Non-Goals

- Full APM solution (use Datadog/New Relic if needed)
- Log aggregation (can add ELK/Loki later)
- Alerting rules (configure in Opik dashboard)
