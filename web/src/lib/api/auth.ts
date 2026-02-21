/**
 * Authentication API functions
 *
 * Provides login, logout, and session check functions.
 * Uses cookies (HttpOnly) for session management — no token
 * stored in JavaScript.
 */

import { API_BASE_URL, ApiClientError } from "./client"

/** Session check response */
interface SessionResponse {
  authenticated: boolean
}

/** Login response */
interface LoginResponse {
  authenticated: boolean
}

/**
 * Whether auth is enabled for this frontend build.
 *
 * In development (VITE_AUTH_ENABLED unset or "false"), auth is skipped
 * to match the backend's dev-mode bypass.
 */
export function isAuthEnabled(): boolean {
  return import.meta.env.VITE_AUTH_ENABLED === "true"
}

/**
 * Credentials mode for fetch requests.
 *
 * Cross-origin deployments (VITE_API_URL set) need "include" to send
 * cookies across origins. Same-origin uses "same-origin" (default).
 */
function getCredentials(): RequestCredentials {
  return import.meta.env.VITE_API_URL ? "include" : "same-origin"
}

/**
 * Check if the current session is valid.
 *
 * Calls GET /api/v1/auth/session which returns {authenticated: true/false}
 * without triggering a 401. Safe to call without a session.
 */
export async function checkSession(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/session`, {
      credentials: getCredentials(),
      headers: { Accept: "application/json" },
    })
    if (!res.ok) return false
    const data: SessionResponse = await res.json()
    return data.authenticated
  } catch {
    // Network error — treat as unknown, not unauthenticated
    // Let the caller handle this (show retry, not login redirect)
    throw new ApiClientError("Session check failed", 0, "NETWORK_ERROR")
  }
}

/**
 * Log in with the app password.
 *
 * On success, the backend sets an HttpOnly session cookie.
 * No token is returned to JavaScript.
 */
export async function login(password: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    credentials: getCredentials(),
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ password }),
  })

  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new ApiClientError(
      data.detail || data.error || "Login failed",
      res.status,
      `HTTP_${res.status}`,
    )
  }

  const data: LoginResponse = await res.json()
  if (!data.authenticated) {
    throw new ApiClientError("Login failed", 401, "HTTP_401")
  }
}

/**
 * Log out and clear the session cookie.
 */
export async function logout(): Promise<void> {
  await fetch(`${API_BASE_URL}/auth/logout`, {
    method: "POST",
    credentials: getCredentials(),
    headers: { Accept: "application/json" },
  })
}
