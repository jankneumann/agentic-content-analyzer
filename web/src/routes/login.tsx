/**
 * Login Route
 *
 * Password-only login page for owner authentication.
 * No email/username — just a password field.
 *
 * In development mode (auth disabled), redirects to /.
 */

import { createRoute, useNavigate, useSearch } from "@tanstack/react-router"
import { useState, type FormEvent } from "react"
import { Route as rootRoute } from "./__root"

import { isAuthEnabled, login } from "@/lib/api"
import { isApiError } from "@/lib/api/client"

export const Route = createRoute({
  getParentRoute: () => rootRoute,
  path: "login",
  validateSearch: (search: Record<string, unknown>) => ({
    returnTo: (search.returnTo as string) || "/",
  }),
  component: LoginPage,
})

function LoginPage() {
  const navigate = useNavigate()
  const { returnTo } = useSearch({ from: Route.fullPath })
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)

  // In dev mode (auth disabled), redirect to home
  if (!isAuthEnabled()) {
    navigate({ to: "/" })
    return null
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError("")
    setIsLoading(true)

    try {
      await login(password)
      navigate({ to: returnTo || "/" })
    } catch (err) {
      if (isApiError(err)) {
        if (err.status === 429) {
          setError(err.message || "Too many attempts. Please try again later.")
        } else if (err.status === 401) {
          setError("Invalid password")
        } else {
          setError(err.message || "Login failed")
        }
      } else {
        setError("Unable to connect. Please check your network.")
      }
      setIsLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-bold tracking-tight">Newsletter Aggregator</h1>
          <p className="text-sm text-muted-foreground">Enter your password to continue</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="password" className="text-sm font-medium leading-none">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoFocus
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isLoading}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              placeholder="Enter your password"
              aria-describedby={error ? "login-error" : undefined}
            />
          </div>

          {error && (
            <p id="login-error" role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={isLoading || !password}
            className="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                Signing in...
              </span>
            ) : (
              "Sign in"
            )}
          </button>
        </form>
      </div>
    </div>
  )
}
