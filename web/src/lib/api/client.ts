/**
 * API Client Configuration and Base Functions
 *
 * This module provides a typed fetch wrapper for making API requests
 * to the FastAPI backend. It handles:
 * - Base URL configuration
 * - JSON serialization/deserialization
 * - Error handling and typed error responses
 * - Request/response interceptors (future: auth tokens)
 *
 * @example
 * // GET request
 * const contents = await apiClient.get<Content[]>('/contents')
 *
 * @example
 * // POST request with body
 * const result = await apiClient.post<IngestResponse>('/contents/ingest', {
 *   source: 'gmail',
 *   maxItems: 10
 * })
 */

import type { ApiError } from "@/types"
import type { Problem } from "@/generated/workflow-contracts"

/**
 * API configuration
 *
 * In development, Vite proxies /api requests to the backend (uses relative URL).
 * In production, VITE_API_URL environment variable points to the backend service.
 *
 * @example Production: VITE_API_URL=https://api.example.com
 */
export const API_BASE_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL.replace(/\/$/, "")}/api/v1`
  : "/api/v1"

/**
 * Default request timeout in milliseconds
 */
const DEFAULT_TIMEOUT = 30000

/**
 * Custom error class for API errors
 *
 * Extends Error to include structured error information
 * from the API response.
 */
export class ApiClientError extends Error {
  /** HTTP status code */
  status: number
  /** Error code from API */
  code: string
  /** Additional error details */
  details?: Record<string, unknown>
  /** Complete RFC 7807 response returned by canonical endpoints. */
  problem: Problem

  constructor(problem: Problem, status?: number)
  constructor(message: string, status: number, code: string, details?: Record<string, unknown>)
  constructor(
    problemOrMessage: Problem | string,
    status = 0,
    code = "HTTP_ERROR",
    details?: Record<string, unknown>,
  ) {
    const problem: Problem = typeof problemOrMessage === "string"
      ? { type: "about:blank", title: problemOrMessage, status, detail: problemOrMessage, code, ...(details ? { errors: [details] } : {}) }
      : problemOrMessage
    super(problem.detail)
    this.name = "ApiClientError"
    this.status = problem.status
    this.code = problem.code ?? code
    this.details = details
    this.problem = problem
  }

  /**
   * Check if error is a specific type
   */
  is(code: string): boolean {
    return this.code === code
  }

  /**
   * Check if error is a network/timeout error
   */
  isNetworkError(): boolean {
    return this.code === "NETWORK_ERROR" || this.code === "TIMEOUT"
  }

  /**
   * Check if error is an authentication error
   */
  isAuthError(): boolean {
    return this.status === 401 || this.status === 403
  }

  /**
   * Check if error is a not found error
   */
  isNotFound(): boolean {
    return this.status === 404
  }
}

/**
 * Request options extending standard fetch options
 */
interface RequestOptions extends Omit<RequestInit, "body"> {
  /** Request body (will be JSON serialized) */
  body?: unknown
  /** Query parameters */
  params?: Record<string, string | number | boolean | undefined>
  /** Request timeout in milliseconds */
  timeout?: number
}

/**
 * Build URL with query parameters
 *
 * @param path - API endpoint path
 * @param params - Query parameters object
 * @returns Full URL with query string
 */
function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin)

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.append(key, String(value))
      }
    })
  }

  return url.toString()
}

/**
 * Parse error response from API
 *
 * @param response - Fetch response object
 * @returns Parsed ApiError or default error
 */
async function parseErrorResponse(response: Response): Promise<Problem> {
  try {
    const data = await response.json()
    return {
      type: data.type || "about:blank",
      title: data.title || response.statusText || "Request failed",
      status: data.status || response.status,
      detail: data.detail || data.message || "An error occurred",
      instance: data.instance,
      code: data.code || `HTTP_${response.status}`,
      errors: data.errors || (data.details ? [data.details] : undefined),
    }
  } catch {
    return { type: "about:blank", title: response.statusText || "Request failed", status: response.status, detail: response.statusText || "An error occurred", code: `HTTP_${response.status}` }
  }
}

/**
 * Make an API request
 *
 * Core function that handles all HTTP methods.
 * Automatically serializes JSON bodies and parses responses.
 *
 * @param method - HTTP method
 * @param path - API endpoint path
 * @param options - Request options
 * @returns Parsed response data
 * @throws ApiClientError on error
 */
async function request<T>(
  method: string,
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { body, params, timeout = DEFAULT_TIMEOUT, headers, ...fetchOptions } = options

  // Build URL with query params
  const url = buildUrl(path, params)

  // Create abort controller for timeout
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeout)

  try {
    const response = await fetch(url, {
      method,
      headers: {
        ...(body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        Accept: "application/json",
        ...headers,
      },
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
      // Include cookies in cross-origin requests when API is on a different host.
      // Harmless for unauthenticated endpoints (cookies are simply absent or ignored).
      credentials: import.meta.env.VITE_API_URL ? "include" : "same-origin",
      ...fetchOptions,
    })

    clearTimeout(timeoutId)

    // Handle error responses
    if (!response.ok) {
      const error = await parseErrorResponse(response)
      throw new ApiClientError(error, response.status)
    }

    // Handle empty responses (204 No Content)
    if (response.status === 204) {
      return undefined as T
    }

    // Parse JSON response
    return await response.json()
  } catch (error) {
    clearTimeout(timeoutId)

    // Handle abort/timeout
    if (error instanceof Error && error.name === "AbortError") {
      throw new ApiClientError("Request timed out", 0, "TIMEOUT")
    }

    // Re-throw ApiClientError as-is
    if (error instanceof ApiClientError) {
      throw error
    }

    // Handle network errors
    throw new ApiClientError(
      error instanceof Error ? error.message : "Network error",
      0,
      "NETWORK_ERROR"
    )
  }
}

/**
 * API Client object
 *
 * Provides typed methods for all HTTP verbs.
 * Use this for making API requests throughout the application.
 *
 * @example
 * // Import and use
 * import { apiClient } from '@/lib/api/client'
 *
 * // GET request
 * const data = await apiClient.get<MyType>('/endpoint')
 *
 * // POST with body
 * const result = await apiClient.post<ResultType>('/endpoint', { data })
 */
export const apiClient = {
  /**
   * Make a GET request
   *
   * @param path - API endpoint path
   * @param options - Request options (params, headers, etc.)
   * @returns Parsed response data
   */
  get<T>(path: string, options?: Omit<RequestOptions, "body">): Promise<T> {
    return request<T>("GET", path, options)
  },

  /**
   * Make a POST request
   *
   * @param path - API endpoint path
   * @param body - Request body (will be JSON serialized)
   * @param options - Additional request options
   * @returns Parsed response data
   */
  post<T>(path: string, body?: unknown, options?: Omit<RequestOptions, "body">): Promise<T> {
    return request<T>("POST", path, { ...options, body })
  },

  /**
   * Make a PUT request
   *
   * @param path - API endpoint path
   * @param body - Request body (will be JSON serialized)
   * @param options - Additional request options
   * @returns Parsed response data
   */
  put<T>(path: string, body?: unknown, options?: Omit<RequestOptions, "body">): Promise<T> {
    return request<T>("PUT", path, { ...options, body })
  },

  /**
   * Make a PATCH request
   *
   * @param path - API endpoint path
   * @param body - Request body (will be JSON serialized)
   * @param options - Additional request options
   * @returns Parsed response data
   */
  patch<T>(path: string, body?: unknown, options?: Omit<RequestOptions, "body">): Promise<T> {
    return request<T>("PATCH", path, { ...options, body })
  },

  /**
   * Make a DELETE request
   *
   * @param path - API endpoint path
   * @param options - Request options
   * @returns Parsed response data (often void)
   */
  delete<T>(path: string, options?: Omit<RequestOptions, "body">): Promise<T> {
    return request<T>("DELETE", path, options)
  },
}

/**
 * Type guard to check if an error is an ApiClientError
 *
 * @param error - Error to check
 * @returns True if error is ApiClientError
 */
export function isApiError(error: unknown): error is ApiClientError {
  return error instanceof ApiClientError
}
