/**
 * OpenTelemetry SDK Initialization for Browser
 *
 * Configures WebTracerProvider with:
 * - FetchInstrumentation for automatic traceparent header injection
 * - OTLPTraceExporter pointing to the backend proxy (/api/v1/otel/v1/traces)
 * - BatchSpanProcessor with 5s flush interval
 * - Resource with service.name and deployment.environment
 *
 * No-op when VITE_OTEL_ENABLED !== "true" — zero overhead in that case.
 */

import { isOtelEnabled } from "./index"

let initialized = false

/**
 * Build the OTLP proxy URL using the same base URL logic as apiClient.
 * In dev: relative URL (Vite proxy handles routing)
 * In prod: prepend VITE_API_URL if set
 */
function getOtlpProxyUrl(): string {
  const apiUrl = import.meta.env.VITE_API_URL
  if (apiUrl) {
    return `${apiUrl.replace(/\/$/, "")}/api/v1/otel/v1/traces`
  }
  return "/api/v1/otel/v1/traces"
}

/**
 * Build a regex that matches the API origin for trace header propagation.
 * Only propagates traceparent to our own backend — not to third-party CDNs.
 */
function getApiOriginPattern(): RegExp {
  const apiUrl = import.meta.env.VITE_API_URL
  if (apiUrl) {
    // Match the configured API origin
    try {
      const url = new URL(apiUrl)
      // Escape special regex chars in the origin
      const escaped = url.origin.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
      return new RegExp(`^${escaped}`)
    } catch {
      // Fallback to same-origin if URL is invalid
      return new RegExp(`^${window.location.origin.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`)
    }
  }
  // Dev mode: same-origin (Vite proxy)
  return new RegExp(`^${window.location.origin.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`)
}

/**
 * Initialize the OpenTelemetry SDK for the browser.
 *
 * Must be called before any fetch() calls are made (i.e., before React renders)
 * so that FetchInstrumentation can monkey-patch the global fetch.
 *
 * Safe to call multiple times — subsequent calls are no-ops.
 */
export async function initTelemetry(): Promise<void> {
  if (initialized || !isOtelEnabled()) {
    return
  }

  initialized = true

  try {
    // Dynamic imports to enable tree-shaking when OTel is disabled
    const { WebTracerProvider, BatchSpanProcessor } = await import(
      "@opentelemetry/sdk-trace-web"
    )
    const { OTLPTraceExporter } = await import(
      "@opentelemetry/exporter-trace-otlp-http"
    )
    const { resourceFromAttributes } = await import("@opentelemetry/resources")
    const { ATTR_SERVICE_NAME } = await import(
      "@opentelemetry/semantic-conventions"
    )
    const { FetchInstrumentation } = await import(
      "@opentelemetry/instrumentation-fetch"
    )
    const { registerInstrumentations } = await import(
      "@opentelemetry/instrumentation"
    )

    // Build the OTLP exporter pointing to our backend proxy
    const exporter = new OTLPTraceExporter({
      url: getOtlpProxyUrl(),
    })

    // Create resource identifying this service
    const resource = resourceFromAttributes({
      [ATTR_SERVICE_NAME]: "newsletter-frontend",
      "deployment.environment":
        import.meta.env.MODE === "production" ? "production" : "development",
    })

    // Configure the tracer provider
    const provider = new WebTracerProvider({
      resource,
      spanProcessors: [
        new BatchSpanProcessor(exporter, {
          scheduledDelayMillis: 5000, // Flush every 5 seconds
          maxQueueSize: 100,
          maxExportBatchSize: 20,
        }),
      ],
    })

    // Register the provider globally
    provider.register()

    // Auto-instrument all fetch() calls with traceparent header injection.
    // Only propagate to our own API origin — not to third-party CDNs/analytics.
    registerInstrumentations({
      instrumentations: [
        new FetchInstrumentation({
          propagateTraceHeaderCorsUrls: [getApiOriginPattern()],
          clearTimingResources: true,
        }),
      ],
    })

    // Initialize Web Vitals reporting
    const { initWebVitals } = await import("./web-vitals")
    initWebVitals()

    console.debug("[OTel] Frontend telemetry initialized")
  } catch (error) {
    // Telemetry should never break the app
    console.warn("[OTel] Failed to initialize frontend telemetry:", error)
    initialized = false
  }
}
