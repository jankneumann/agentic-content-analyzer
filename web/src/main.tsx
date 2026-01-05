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

// Log router initialization for debugging
console.log("[main.tsx] Initializing router with route tree:", routeTree)

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
  defaultPendingComponent: () => {
    console.log("[main.tsx] Rendering pending component")
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  },
  // Default error component for route errors
  defaultErrorComponent: ({ error }) => {
    console.error("[main.tsx] Route error:", error)
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-background">
        <h1 className="text-2xl font-bold text-red-500">Something went wrong</h1>
        <p className="text-gray-500">{error.message}</p>
        <pre className="max-w-lg overflow-auto text-xs">{error.stack}</pre>
      </div>
    )
  },
})

console.log("[main.tsx] Router created:", router)

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
console.log("[main.tsx] Rendering to root element")
const rootElement = document.getElementById("root")
console.log("[main.tsx] Root element:", rootElement)

if (rootElement) {
  const root = createRoot(rootElement)
  console.log("[main.tsx] Created React root, rendering...")
  root.render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>
  )
  console.log("[main.tsx] Render called")
} else {
  console.error("[main.tsx] Root element not found!")
}
