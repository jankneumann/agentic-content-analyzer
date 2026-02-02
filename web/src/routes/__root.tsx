/**
 * Root Route
 *
 * The root layout route that wraps all other routes.
 * Provides the AppShell layout with sidebar and header.
 *
 * TanStack Router uses file-based routing where:
 * - __root.tsx defines the root layout
 * - index.tsx in routes/ is the home page
 * - [name].tsx files define individual routes
 */

import { createRootRoute, Outlet } from "@tanstack/react-router"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import { AppShell, BackgroundTasksIndicator } from "@/components/layout"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import { PWAUpdatePrompt } from "@/components/PWAUpdatePrompt"
import { Toaster } from "@/components/ui/sonner"
import { BackgroundTasksProvider } from "@/contexts/BackgroundTasksContext"
import { initTelemetry } from "@/lib/telemetry"

// Initialize OTel before React renders so fetch instrumentation
// is active before TanStack Query makes its first API call.
// This is a fire-and-forget call — telemetry initialization
// should never block app rendering.
initTelemetry()

/**
 * TanStack Query client
 *
 * Configured with sensible defaults for the application.
 * - staleTime: 30 seconds (data considered fresh)
 * - gcTime: 5 minutes (unused data garbage collected)
 * - retry: 1 (retry failed requests once)
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000, // 30 seconds
      gcTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

/**
 * Root route component
 *
 * Wraps the entire app with:
 * - QueryClientProvider for data fetching
 * - AppShell for layout (sidebar, header)
 * - Outlet for child route content
 */
function RootComponent() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BackgroundTasksProvider>
          <AppShell>
            <Outlet />
          </AppShell>
          <BackgroundTasksIndicator />
          <PWAUpdatePrompt />
          <Toaster />
        </BackgroundTasksProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}

/**
 * Root route definition
 *
 * This is the entry point for TanStack Router.
 * All other routes are children of this route.
 */
export const Route = createRootRoute({
  component: RootComponent,
})
