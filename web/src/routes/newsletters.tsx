/**
 * Newsletters Page - DEPRECATED
 *
 * This route redirects to /contents as part of the Newsletter deprecation.
 * The Newsletter model has been replaced by the unified Content model.
 *
 * @deprecated Use /contents instead
 * @see openspec/changes/deprecate-newsletter-model/
 *
 * Route: /newsletters -> redirects to /contents
 */

import { useEffect } from "react"
import { createRoute, useNavigate } from "@tanstack/react-router"

import { Route as rootRoute } from "./__root"

/**
 * Redirect component for the deprecated /newsletters route.
 * Performs a client-side redirect to /contents with replace (no back-button entry).
 */
function NewslettersRedirect() {
  const navigate = useNavigate()

  useEffect(() => {
    // Redirect to the unified Content page
    navigate({ to: "/contents", replace: true })
  }, [navigate])

  // Show nothing during redirect (happens instantly)
  return null
}

export const NewslettersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/newsletters",
  component: NewslettersRedirect,
})
