/**
 * API Module Exports
 *
 * Central export point for all API-related functionality.
 */

// Core client
export { apiClient, ApiClientError, isApiError } from "./client"

// Query keys for TanStack Query
export { queryKeys } from "./query-keys"

// SSE utilities
export { subscribeToProgress, waitForProgress } from "./sse"
export type { ProgressEvent, SSEOptions } from "./sse"

// Entity-specific API functions
export * from "./newsletters"
export * from "./summaries"
