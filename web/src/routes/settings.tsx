/**
 * Settings Layout Route
 *
 * Parent route for settings sub-pages with tab navigation.
 * Renders a tab bar and Outlet for child routes.
 *
 * Sub-routes:
 * - /settings/prompts (default)
 * - /settings/models
 * - /settings/voice
 * - /settings/notifications
 *
 * Route: /settings
 */

import {
  createRoute,
  Outlet,
  redirect,
  useMatches,
  Link,
} from "@tanstack/react-router"
import { Bell, Cpu, Volume2, MessageSquareCode } from "lucide-react"

import { Route as rootRoute } from "./__root"
import { PageContainer } from "@/components/layout"
import { cn } from "@/lib/utils"

const settingsTabs = [
  { path: "/settings/prompts", label: "Prompts", icon: MessageSquareCode },
  { path: "/settings/models", label: "Models", icon: Cpu },
  { path: "/settings/voice", label: "Voice", icon: Volume2 },
  { path: "/settings/notifications", label: "Notifications", icon: Bell },
] as const

export const SettingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "settings",
  // Redirect /settings to /settings/prompts before component renders.
  // Using beforeLoad avoids a back-button loop that <Navigate> would cause.
  beforeLoad: ({ location }) => {
    if (location.pathname === "/settings" || location.pathname === "/settings/") {
      throw redirect({ to: "/settings/prompts" })
    }
  },
  component: SettingsLayout,
})

function SettingsLayout() {
  const matches = useMatches()
  const currentPath = matches[matches.length - 1]?.pathname ?? ""

  return (
    <PageContainer
      title="Settings"
      description="Configure application behavior and integrations"
    >
      <nav role="tablist" className="flex border-b mb-6">
        {settingsTabs.map((tab) => {
          const isActive = currentPath.startsWith(tab.path)
          const Icon = tab.icon
          return (
            <Link
              key={tab.path}
              to={tab.path}
              role="tab"
              aria-selected={isActive}
              className={cn(
                "flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
                isActive
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground/50",
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </Link>
          )
        })}
      </nav>
      <Outlet />
    </PageContainer>
  )
}
