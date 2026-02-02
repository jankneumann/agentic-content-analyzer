/**
 * Web Vitals → OpenTelemetry Spans Bridge
 *
 * Measures Core Web Vitals (LCP, INP, CLS, FCP, TTFB) using Google's
 * web-vitals library and reports them as OTel spans with metric attributes.
 *
 * The browser OTel metrics SDK is still experimental, so we use spans as the
 * transport mechanism — each Web Vital measurement becomes a zero-duration span
 * with structured attributes (name, value, rating, delta, navigation_type).
 *
 * Only active when OTel is enabled (initWebVitals is only called from setup.ts
 * which already gates on VITE_OTEL_ENABLED).
 */

import type { Metric } from "web-vitals"

/**
 * Initialize Web Vitals measurement and OTel reporting.
 *
 * Called from setup.ts after the OTel SDK is initialized.
 * Uses dynamic imports so web-vitals is tree-shaken when OTel is disabled.
 */
export function initWebVitals(): void {
  // Pre-load the tracer once to avoid repeated dynamic imports on each metric callback
  import("@opentelemetry/api").then(({ trace }) => {
    const tracer = trace.getTracer("web-vitals")

    const reportMetric = (metric: Metric) => {
      const span = tracer.startSpan(`web_vital.${metric.name}`, {
        attributes: {
          "web_vital.name": metric.name,
          "web_vital.id": metric.id,
          "web_vital.value": metric.value,
          "web_vital.rating": metric.rating,
          "web_vital.delta": metric.delta,
          "web_vital.navigation_type": metric.navigationType,
        },
      })
      span.end()
    }

    import("web-vitals").then(({ onLCP, onINP, onCLS, onFCP, onTTFB }) => {
      onLCP(reportMetric)
      onINP(reportMetric)
      onCLS(reportMetric)
      onFCP(reportMetric)
      onTTFB(reportMetric)
    })
  })
}
