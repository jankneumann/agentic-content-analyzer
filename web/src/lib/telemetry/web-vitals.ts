/**
 * Web Vitals → OpenTelemetry Metrics Bridge
 *
 * Measures Core Web Vitals (LCP, INP, CLS, FCP, TTFB) using Google's
 * web-vitals library and reports them as OTel histogram observations.
 *
 * Metric names follow the pattern: browser.web_vital.{metric_name}
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
  // Report each metric as it becomes available
  import("web-vitals").then(({ onLCP, onINP, onCLS, onFCP, onTTFB }) => {
    const reportMetric = (metric: Metric) => {
      // Use the OTel API to record the metric
      // We use console for now + a custom event that the OTel SDK can pick up.
      // In a full implementation, we'd use MeterProvider, but the browser
      // OTel metrics SDK is still experimental. Instead, we create spans
      // that represent the web vital measurements.
      import("@opentelemetry/api").then(({ trace }) => {
        const tracer = trace.getTracer("web-vitals")
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
      })
    }

    onLCP(reportMetric)
    onINP(reportMetric)
    onCLS(reportMetric)
    onFCP(reportMetric)
    onTTFB(reportMetric)
  })
}
