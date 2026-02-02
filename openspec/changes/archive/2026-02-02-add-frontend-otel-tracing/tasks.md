# Implementation Tasks

## 1. Dependencies and Configuration

- [x] 1.1 Add frontend OTel dependencies to `web/package.json`:
  - `@opentelemetry/api`
  - `@opentelemetry/sdk-trace-web`
  - `@opentelemetry/instrumentation-fetch`
  - `@opentelemetry/exporter-trace-otlp-http`
  - `@opentelemetry/resources`
  - `@opentelemetry/semantic-conventions`
  - `web-vitals`
- [x] 1.2 Add `VITE_OTEL_ENABLED` to `web/.env.example` with documentation
- [x] 1.3 Add `VITE_OTEL_ENABLED` env passthrough in `web/vite.config.ts`
  - Note: Vite auto-exposes `VITE_` prefixed env vars; no config change needed

## 2. Backend OTLP Proxy

- [x] 2.1 Create `src/api/otel_proxy_routes.py` with:
  - `POST /api/v1/otel/v1/traces` — forwards trace data to OTLP endpoint
  - Validate content-type is `application/json` or `application/x-protobuf`
  - Add OTLP authentication headers from backend settings
  - Limit request body size (1MB max)
  - Return 204 on success, 502 on upstream failure
- [x] 2.2 Register proxy route in `src/api/app.py`
- [x] 2.3 Gate proxy behind `otel_enabled` setting (return 404 when disabled)

## 3. Frontend Telemetry Module

- [x] 3.1 Create `web/src/lib/telemetry/setup.ts`:
  - `initTelemetry()` function that configures WebTracerProvider
  - FetchInstrumentation with `propagateTraceHeaderCorsUrls` for same-origin
  - OTLPTraceExporter pointing to `/api/v1/otel/v1/traces` (proxied)
  - BatchSpanProcessor with 5s flush interval
  - Resource with `service.name: "newsletter-frontend"`, `deployment.environment`
  - No-op when `VITE_OTEL_ENABLED !== "true"`
- [x] 3.2 Create `web/src/lib/telemetry/web-vitals.ts`:
  - Bridge `web-vitals` metrics to OTel span observations
  - Metric names: `web_vital.{lcp,inp,cls,fcp,ttfb}`
  - Reported as spans with metric attributes
  - Report on page visibility change (standard web-vitals pattern)
- [x] 3.3 Create `web/src/lib/telemetry/index.ts`:
  - Export `initTelemetry()`, `getTracer()`, `isOtelEnabled()`
  - Re-export types for consumers

## 4. React Error Boundary

- [x] 4.1 Create `web/src/components/ErrorBoundary.tsx`:
  - Class component implementing `componentDidCatch`
  - On catch: create span, record OTel error event, set span status ERROR
  - Render fallback UI with error message and trace_id for support correlation
  - Falls back gracefully when OTel is disabled
- [x] 4.2 Wrap app root in `web/src/routes/__root.tsx` with ErrorBoundary
- [x] 4.3 Call `initTelemetry()` in root layout before React tree renders

## 5. Testing

- [x] 5.1 Create `tests/api/test_otel_proxy.py`:
  - Proxy returns 204 when OTLP endpoint is configured
  - Proxy returns 404 when otel_enabled=false
  - Proxy rejects oversized body (>1MB)
  - Proxy validates content-type header
  - Proxy forwards authentication headers
  - Proxy returns 502 on upstream error/timeout
  - Proxy returns 503 when endpoint not configured
- [x] 5.2 Create `web/tests/e2e/telemetry/trace-propagation.spec.ts`:
  - Verify no `traceparent` header when disabled
  - Verify error boundary renders correctly
  - Verify app renders normally with ErrorBoundary wrapper
  - Verify OTLP proxy route is accessible
- [x] 5.3 Verify existing E2E tests still pass with telemetry disabled
  - All 350 E2E tests pass (chromium project)

## 6. Documentation

- [x] 6.1 Update `web/.env.example` with `VITE_OTEL_ENABLED=false`
- [x] 6.2 Update `CLAUDE.md` observability section with frontend tracing setup
- [x] 6.3 Update `docs/SETUP.md` with frontend OTel configuration
