/**
 * Application Entry Point
 *
 * Sets up the React application with:
 * - TanStack Router for client-side routing
 * - React StrictMode for development warnings
 * - Global CSS styles
 *
 * The router is configured with the route tree from routeTree.gen.ts
 * which defines all available routes and their components.
 */

import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { RouterProvider, createRouter } from "@tanstack/react-router"

// Import global styles (Tailwind CSS)
import "./index.css"

// Import the route tree
import { routeTree } from "./routeTree.gen"

/**
 * Create the router instance
 *
 * TanStack Router provides:
 * - Type-safe routing
 * - Automatic code splitting (when configured)
 * - Built-in suspense support
 * - Search params management
 */
const router = createRouter({
  routeTree,
  // Default pending component while routes load
  defaultPendingComponent: () => (
    <div className="flex h-screen items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  ),
  // Default error component for route errors
  defaultErrorComponent: ({ error }) => (
    <div className="flex h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-bold text-destructive">Something went wrong</h1>
      <p className="text-muted-foreground">{error.message}</p>
    </div>
  ),
})

/**
 * Declare router type for TypeScript
 *
 * This enables type inference for route paths and params
 * throughout the application.
 */
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

/**
 * Render the application
 *
 * Uses createRoot for React 18+ concurrent features.
 * StrictMode enables additional development checks.
 */
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>
)
