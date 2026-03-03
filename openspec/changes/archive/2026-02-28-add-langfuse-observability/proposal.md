# Proposal: Add Langfuse Observability Provider

## Summary

Add [Langfuse](https://langfuse.com) as a fifth observability provider alongside Noop, Opik, Braintrust, and OTel. Langfuse is an open-source LLM engineering platform that provides trace visualization, evaluation, prompt management, and cost tracking — available both as a managed cloud service and self-hosted.

## Motivation

The project currently supports four observability providers, but none offer the combination of:

1. **Open-source with managed cloud option** — Langfuse is fully open-source (MIT) with optional hosted cloud, giving flexibility between self-hosted and SaaS without vendor lock-in.
2. **Native OTLP ingestion** — Since v3.22.0, Langfuse accepts standard OpenTelemetry traces via its `/api/public/otel` HTTP endpoint, making it a natural fit for our OTel-first architecture.
3. **LLM-native UI** — Unlike generic OTel backends (Jaeger, Grafana), Langfuse renders LLM traces with input/output visualization, token counting, cost estimation, and model comparison dashboards.

Adding Langfuse follows the established provider pattern (Protocol + factory + settings + profile + Docker Compose) and requires **zero new Python dependencies** since we already use the OpenTelemetry SDK.

## Scope

### In Scope
- `LangfuseProvider` class implementing `ObservabilityProvider` protocol via OTel
- Settings fields for Langfuse configuration (public key, secret key, base URL)
- Factory dispatch for `OBSERVABILITY_PROVIDER=langfuse`
- `docker-compose.langfuse.yml` for local self-hosted Langfuse stack
- `profiles/local-langfuse.yaml` profile
- Makefile targets: `langfuse-up`, `langfuse-down`, `langfuse-logs`, `dev-langfuse`, `verify-langfuse`, `test-langfuse`
- Integration test fixtures and tests following the Opik pattern
- Documentation updates (CLAUDE.md, relevant docs)
- Wiring in `profiles/base.yaml` for Langfuse secrets

### Out of Scope
- Langfuse native Python SDK integration (we use OTel, not the `langfuse` package)
- Langfuse prompt management features (separate concern)
- Langfuse evaluation/scoring features (future enhancement)
- Kubernetes/Helm deployment (local Docker Compose only)
- Replacing or deprecating any existing provider

## Design Approach

The Langfuse provider will follow the same OTel-based approach as `OpikProvider` and `OTelProvider`:

1. **OTel SDK** with `OTLPSpanExporter` pointing at Langfuse's OTLP endpoint
2. **Basic Auth** header auto-constructed from `LANGFUSE_PUBLIC_KEY:LANGFUSE_SECRET_KEY` (base64-encoded)
3. **Endpoint auto-construction** from `LANGFUSE_BASE_URL + /api/public/otel`
4. **Same `gen_ai.*` semantic conventions** as existing OTel-based providers
5. **No new dependencies** — uses existing `opentelemetry-exporter-otlp-proto-http`

The key differentiator from the generic `otel` provider is the authentication mechanism (Basic Auth vs. arbitrary headers) and the auto-constructed endpoint URL, providing a cleaner UX: `OBSERVABILITY_PROVIDER=langfuse` instead of manually configuring `otel` with Langfuse-specific headers.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Langfuse self-hosted stack is heavier than Opik (needs ClickHouse + Redis + MinIO + PG) | Use separate Docker Compose project like Opik; document resource requirements |
| Port conflicts with existing services | Use port 3100 for Langfuse UI; all infrastructure services (PG, ClickHouse, Redis, MinIO) are internal-only with no host ports |
| Langfuse OTLP endpoint is HTTP-only (no gRPC) | We already use `OTLPSpanExporter` (HTTP), not gRPC — no issue |
| `gen_ai.*` semantic conventions are experimental | Already used by Opik/OTel providers; Langfuse explicitly supports them |
