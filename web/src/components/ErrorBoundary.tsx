/**
 * React Error Boundary with OpenTelemetry Integration
 *
 * Catches uncaught React component errors and:
 * 1. Records an OTel event with error details and stack trace
 * 2. Sets the active span status to ERROR (if any)
 * 3. Renders a fallback UI with the trace_id for support correlation
 * 4. Logs to console when OTel is disabled
 *
 * Wraps the app root in __root.tsx to catch any rendering errors.
 */

import { Component } from "react"
import type { ErrorInfo, ReactNode } from "react"
import { isOtelEnabled } from "@/lib/telemetry"

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  traceId: string | null
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null, traceId: null }
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Always log to console
    console.error("[ErrorBoundary] Uncaught error:", error, errorInfo)

    if (isOtelEnabled()) {
      this.recordOtelError(error, errorInfo)
    }
  }

  private async recordOtelError(
    error: Error,
    errorInfo: ErrorInfo
  ): Promise<void> {
    try {
      const { trace, SpanStatusCode } = await import("@opentelemetry/api")

      const tracer = trace.getTracer("react-error-boundary")
      const span = tracer.startSpan("react.error_boundary.catch")

      // Record the error as an event on the span
      span.recordException(error)
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: error.message,
      })

      // Add component stack as an attribute
      if (errorInfo.componentStack) {
        span.setAttribute(
          "react.component_stack",
          errorInfo.componentStack.substring(0, 4096)
        )
      }

      span.end()

      // Extract trace_id for the fallback UI
      const spanContext = span.spanContext()
      if (spanContext.traceId) {
        this.setState({ traceId: spanContext.traceId })
      }
    } catch (otelError) {
      // OTel should never break error handling
      console.warn("[ErrorBoundary] Failed to record OTel error:", otelError)
    }
  }

  private handleReset = (): void => {
    this.setState({ hasError: false, error: null, traceId: null })
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="flex min-h-screen items-center justify-center bg-background p-4">
          <div className="max-w-md space-y-4 text-center">
            <h1 className="text-2xl font-bold text-foreground">
              Something went wrong
            </h1>
            <p className="text-muted-foreground">
              An unexpected error occurred. Please try refreshing the page.
            </p>
            {this.state.error && (
              <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {this.state.error.message}
              </p>
            )}
            {this.state.traceId && (
              <p className="text-xs text-muted-foreground">
                Trace ID:{" "}
                <code className="rounded bg-muted px-1 py-0.5 font-mono">
                  {this.state.traceId}
                </code>
              </p>
            )}
            <button
              onClick={this.handleReset}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Try Again
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
