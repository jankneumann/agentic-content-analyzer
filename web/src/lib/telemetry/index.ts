/**
 * Frontend Telemetry — Public API
 *
 * Re-exports telemetry utilities for use across the application.
 *
 * Usage:
 *   import { initTelemetry, getTracer, isOtelEnabled } from '@/lib/telemetry'
 *
 *   // Initialize once at app startup (before React renders)
 *   await initTelemetry()
 *
 *   // Get a tracer for custom spans (if needed later)
 *   const tracer = getTracer('my-component')
 */

/**
 * Check if OTel is enabled via the VITE_OTEL_ENABLED environment variable.
 */
export function isOtelEnabled(): boolean {
  return import.meta.env.VITE_OTEL_ENABLED === "true"
}

/**
 * Get an OTel Tracer instance for creating custom spans.
 *
 * Returns a no-op tracer when OTel is disabled (the OTel API
 * returns no-op implementations when no provider is registered).
 */
export async function getTracer(name: string) {
  const { trace } = await import("@opentelemetry/api")
  return trace.getTracer(name)
}

// Re-export initTelemetry (defined in setup.ts to avoid circular deps)
export { initTelemetry } from "./setup"
