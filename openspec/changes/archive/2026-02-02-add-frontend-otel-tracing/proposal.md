# Change: Add Frontend OpenTelemetry Tracing and Web Vitals

## Why

The backend now has full three-pillar observability (traces + metrics + logs via the OTel log
bridge), but the frontend has **zero telemetry**. When a user clicks "Generate Digest" and
the request takes 8 seconds, operators cannot tell whether the latency was in the browser,
network, or backend — because frontend-originated requests carry no trace context.

Without frontend OTel:
- No trace propagation: backend traces start at the API boundary, missing the user action
- No performance visibility: Core Web Vitals (LCP, INP, CLS) are invisible to the backend
- No error correlation: React component crashes are logged to `console.error` with no trace_id
- SSE progress streams (`src/lib/api/sse.ts`) have no parent span linking them to the request

By adding frontend tracing:
1. **End-to-end trace propagation**: `traceparent` header on every `fetch()` call connects the
   browser click to the backend span tree — one trace_id across the full request lifecycle
2. **Web Vitals as OTel metrics**: LCP, INP, CLS, FCP, TTFB exported to the same OTLP backend
3. **React Error Boundary spans**: Uncaught component errors create OTel events with stack trace,
   component name, and the active trace_id for correlation
4. **OTLP export via backend proxy**: Avoids CORS by proxying `/api/v1/otel` to the OTLP
   collector, reusing the backend's existing endpoint configuration

## What Changes

- **NEW** `web/src/lib/telemetry/setup.ts` — OTel SDK initialization (TracerProvider,
  FetchInstrumentation, OTLP exporter via backend proxy)
- **NEW** `web/src/lib/telemetry/web-vitals.ts` — Web Vitals → OTel metrics bridge
- **NEW** `web/src/lib/telemetry/index.ts` — Public API (`initTelemetry`, `getTracer`)
- **NEW** `web/src/components/ErrorBoundary.tsx` — React Error Boundary with OTel span creation
- **MODIFIED** `web/src/routes/__root.tsx` — Initialize telemetry and wrap app in ErrorBoundary
- **MODIFIED** `web/src/lib/api/client.ts` — No changes needed (fetch auto-instrumented)
- **MODIFIED** `web/vite.config.ts` — Add `VITE_OTEL_ENABLED` env passthrough
- **NEW** `src/api/routes/otel_proxy.py` — Backend OTLP proxy endpoint (`/api/v1/otel/*`)
- **MODIFIED** `src/api/main.py` — Register OTel proxy route
- **NEW** `web/tests/e2e/telemetry/` — E2E tests for trace propagation header
- **NEW** `tests/api/test_otel_proxy.py` — Backend proxy endpoint tests

### Not Changed (by design)
- No modification to `web/src/lib/api/client.ts` — the `@opentelemetry/instrumentation-fetch`
  package auto-instruments all `fetch()` calls including the custom `apiClient`
- No modification to SSE streams — trace context propagates via the initial fetch for SSE
- No modification to service worker — SW operates outside the tracing context

## Impact

- Affected specs: `observability` (add frontend tracing requirements)
- Affected code:
  - `web/src/` (new telemetry module, ErrorBoundary, root layout)
  - `web/vite.config.ts` (env passthrough)
  - `src/api/` (new OTLP proxy route)
  - `web/package.json` (new dependencies)
- New dependencies (frontend):
  - `@opentelemetry/sdk-trace-web`
  - `@opentelemetry/instrumentation-fetch`
  - `@opentelemetry/exporter-trace-otlp-http`
  - `@opentelemetry/resources`
  - `@opentelemetry/semantic-conventions`
  - `web-vitals`
- New dependencies (backend): None (uses existing FastAPI routing)

## Related Proposals

- `add-otel-log-bridge` — Backend log bridge; this extends observability to the frontend
- `add-observability` — Parent observability proposal
