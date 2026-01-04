/**
 * Server-Sent Events (SSE) Utilities
 *
 * Provides utilities for connecting to SSE endpoints for real-time
 * progress updates during long-running operations like:
 * - Newsletter summarization
 * - Digest generation
 * - Podcast audio generation
 *
 * @example
 * // Subscribe to progress updates
 * const unsubscribe = subscribeToProgress('/summaries/123/status', {
 *   onProgress: (data) => setProgress(data.progress),
 *   onComplete: (data) => handleComplete(data),
 *   onError: (error) => handleError(error),
 * })
 *
 * // Later: clean up
 * unsubscribe()
 */

/**
 * Base URL for SSE endpoints
 */
const SSE_BASE_URL = "/api/v1"

/**
 * Progress event data from SSE
 */
export interface ProgressEvent<T = unknown> {
  /** Event type */
  type: "progress" | "complete" | "error"
  /** Task identifier */
  taskId: string
  /** Current step description */
  step: string
  /** Progress percentage (0-100) */
  progress: number
  /** Status message */
  message: string
  /** Additional data (varies by event type) */
  data?: T
  /** Error message (for error events) */
  error?: string
}

/**
 * SSE subscription options
 */
export interface SSEOptions<T = unknown> {
  /** Called on each progress update */
  onProgress?: (event: ProgressEvent<T>) => void
  /** Called when operation completes successfully */
  onComplete?: (event: ProgressEvent<T>) => void
  /** Called on error */
  onError?: (error: Error) => void
  /** Called when connection is established */
  onOpen?: () => void
  /** Reconnect on disconnect (default: false) */
  reconnect?: boolean
  /** Max reconnection attempts (default: 3) */
  maxReconnectAttempts?: number
}

/**
 * Subscribe to SSE progress updates
 *
 * Creates an EventSource connection to the specified endpoint
 * and calls the appropriate callback for each event type.
 *
 * @param path - SSE endpoint path
 * @param options - Subscription options with callbacks
 * @returns Unsubscribe function to close the connection
 */
export function subscribeToProgress<T = unknown>(
  path: string,
  options: SSEOptions<T>
): () => void {
  const {
    onProgress,
    onComplete,
    onError,
    onOpen,
    reconnect = false,
    maxReconnectAttempts = 3,
  } = options

  let eventSource: EventSource | null = null
  let reconnectAttempts = 0
  let isManualClose = false

  /**
   * Create and configure EventSource
   */
  function connect() {
    const url = `${SSE_BASE_URL}${path}`
    eventSource = new EventSource(url)

    // Connection opened
    eventSource.onopen = () => {
      reconnectAttempts = 0
      onOpen?.()
    }

    // Handle messages
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ProgressEvent<T>

        switch (data.type) {
          case "progress":
            onProgress?.(data)
            break
          case "complete":
            onComplete?.(data)
            // Auto-close on completion
            close()
            break
          case "error":
            onError?.(new Error(data.error || data.message))
            close()
            break
        }
      } catch (error) {
        onError?.(new Error("Failed to parse SSE message"))
      }
    }

    // Handle errors
    eventSource.onerror = () => {
      if (isManualClose) return

      // Close the current connection
      eventSource?.close()

      // Attempt reconnection if enabled
      if (reconnect && reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++
        setTimeout(connect, 1000 * reconnectAttempts) // Exponential backoff
      } else {
        onError?.(new Error("SSE connection lost"))
      }
    }
  }

  /**
   * Close the EventSource connection
   */
  function close() {
    isManualClose = true
    eventSource?.close()
    eventSource = null
  }

  // Start connection
  connect()

  // Return unsubscribe function
  return close
}

/**
 * Create a Promise-based SSE subscription
 *
 * Useful when you want to await the completion of an SSE stream.
 *
 * @param path - SSE endpoint path
 * @param onProgress - Optional progress callback
 * @returns Promise that resolves with the complete event data
 *
 * @example
 * const result = await waitForProgress('/digests/123/status', (event) => {
 *   setProgress(event.progress)
 * })
 */
export function waitForProgress<T = unknown>(
  path: string,
  onProgress?: (event: ProgressEvent<T>) => void
): Promise<ProgressEvent<T>> {
  return new Promise((resolve, reject) => {
    subscribeToProgress<T>(path, {
      onProgress,
      onComplete: resolve,
      onError: reject,
    })
  })
}
