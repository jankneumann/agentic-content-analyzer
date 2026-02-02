# Design: Frontend OTel Tracing

## Context

The backend has full OTel observability (traces via `otel_setup.py`, metrics via `metrics.py`,
logs via `log_setup.py`). The frontend is a React 19 SPA built with Vite 7, TanStack Router,
and TanStack React Query. All API calls use a custom `apiClient` wrapper around the native
`fetch()` API (`web/src/lib/api/client.ts`). There is currently no frontend telemetry.

The frontend also uses SSE for long-running operations (summarization, digest generation),
which start with a `fetch()` call that opens an event stream. Trace context on the initial
SSE request would link the entire progress stream to the backend processing span tree.

## Goals

1. Propagate W3C `traceparent` header on all `fetch()` calls (automatic, zero code changes)
2. Export Core Web Vitals (LCP, INP, CLS, FCP, TTFB) as OTel metrics
3. Capture React Error Boundary crashes as OTel events with trace correlation
4. Route OTLP export through backend proxy to avoid CORS and credential exposure
5. Feature-flag the entire setup behind `VITE_OTEL_ENABLED`

## Non-Goals

1. Frontend log export (browser logs are noisy; backend log bridge handles server-side)
2. User session tracking or RUM (Real User Monitoring) — use dedicated tools for that
3. Custom spans for UI interactions (future enhancement; start with auto-instrumentation)
4. Offline trace buffering in the service worker (SW operates outside tracing context)

## Decisions

### Decision 1: Auto-Instrument Fetch, Not Patch apiClient

Use `@opentelemetry/instrumentation-fetch` which monkey-patches the global `fetch()` function.
This automatically instruments all calls made by `apiClient`, React Query, and SSE without
modifying any application code. The `propagateTraceHeaderCorsUrls` option is scoped to the
API origin only (same-origin in dev, `VITE_API_URL` origin in production) to prevent leaking
trace context to third-party CDNs or analytics services.

Alternative considered: manually adding `traceparent` headers in `apiClient`. Rejected because
it would miss SSE calls and any future direct `fetch()` usage.

### Decision 2: OTLP Export via Backend Proxy

Route browser OTLP exports through `POST /api/v1/otel/v1/traces` on the backend, which
forwards to the real OTLP collector endpoint. This avoids:
- CORS configuration on the OTLP collector
- Exposing collector credentials (API keys) in browser JavaScript
- Network issues from direct browser → collector connections

The proxy is a thin FastAPI route that forwards the request body and content-type header,
adding the backend's OTLP authentication headers server-side.

### Decision 3: Web Vitals via `web-vitals` Library

Use Google's `web-vitals` library to measure LCP, INP, CLS, FCP, and TTFB, then report
them as OTel metric observations. The `web-vitals` library is the de facto standard (used
by Chrome's CrUX report) and handles the complexity of when/how each metric is reported.

OTel metric names follow semantic conventions:
- `browser.web_vital.lcp` (histogram, milliseconds)
- `browser.web_vital.inp` (histogram, milliseconds)
- `browser.web_vital.cls` (histogram, unitless score)
- `browser.web_vital.fcp` (histogram, milliseconds)
- `browser.web_vital.ttfb` (histogram, milliseconds)

### Decision 4: React Error Boundary with OTel Integration

Create an `ErrorBoundary` component that wraps the app root. On `componentDidCatch`:
1. Gets the current active span (if any)
2. Records an OTel event with the error details
3. Sets span status to ERROR
4. Falls back to an error UI with the trace_id for support correlation

This captures React rendering errors that would otherwise be silent in production.

### Decision 5: Feature Flag via VITE_OTEL_ENABLED

The telemetry module is a no-op when `VITE_OTEL_ENABLED` is not `true`. This means:
- Zero performance overhead in development by default
- No network requests to OTLP proxy unless explicitly enabled
- Tree-shaking removes OTel SDK code in production builds when disabled

### Decision 6: Initialization Timing

`initTelemetry()` runs in `__root.tsx` before the React tree renders. This ensures the
fetch instrumentation is active before TanStack Query makes its first API call.

## Architecture

```
Browser (React SPA)
  │
  ├── User interaction triggers API call
  │     └── fetch("GET /api/v1/digests")
  │           │
  │           ├── [FetchInstrumentation] creates span + injects traceparent header
  │           │
  │           └── Request: GET /api/v1/digests
  │                 Headers: traceparent: 00-<trace_id>-<span_id>-01
  │
  ├── [ErrorBoundary] catches React errors → OTel event
  │
  ├── [WebVitals] observes LCP/INP/CLS → OTel metrics
  │
  └── [OTLPTraceExporter] → POST /api/v1/otel/v1/traces
        │
        └── Backend proxy → forwards to OTEL_EXPORTER_OTLP_ENDPOINT
              (adds authentication headers server-side)

Backend (FastAPI)
  │
  ├── [FastAPIInstrumentor] extracts traceparent → creates child span
  │     └── Same trace_id as browser span!
  │
  └── [OTel proxy] /api/v1/otel/* → forwards to OTLP collector
```

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Bundle size increase from OTel SDK | Tree-shake when disabled; SDK is ~30KB gzipped |
| OTLP proxy becomes a bottleneck | Batch exporter with 5s flush interval; proxy is passthrough |
| Fetch instrumentation conflicts with service worker | SW uses separate fetch scope; no conflict |
| Web Vitals reported inconsistently across browsers | `web-vitals` library handles browser compat |
| Error boundary catches expected errors (React suspense) | Only record errors that are actual crashes |
| OTLP proxy abused for arbitrary requests | Validate content-type, limit body size, rate-limit |
