/**
 * Status Page
 *
 * System health dashboard showing connection status for all
 * backend services. Moved from /settings to its own top-level page
 * since it's read-only operational status, not a configurable setting.
 *
 * Route: /status
 */

import { createRoute } from "@tanstack/react-router"
import { Database } from "lucide-react"

import { Route as rootRoute } from "./__root"
import { PageContainer, PageSection } from "@/components/layout"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ConnectionDashboard } from "@/components/settings/ConnectionDashboard"

export const StatusRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "status",
  component: StatusPage,
})

function StatusPage() {
  return (
    <PageContainer
      title="System Status"
      description="Health status of all configured backend services"
    >
      <PageSection title="Connections">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-muted-foreground" />
              <CardTitle className="text-base">API Connections</CardTitle>
            </div>
            <CardDescription>
              Health status of all configured backend services. Auto-refreshes
              every 60 seconds.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ConnectionDashboard />
          </CardContent>
        </Card>
      </PageSection>
    </PageContainer>
  )
}
