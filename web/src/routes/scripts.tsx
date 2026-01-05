/**
 * Scripts Page
 *
 * Displays podcast dialogue scripts.
 * Supports script review and section-by-section revision.
 *
 * Route: /scripts
 */

import { createRoute } from "@tanstack/react-router"
import { Mic, Plus } from "lucide-react"

import { Route as rootRoute } from "./__root"
import { PageContainer } from "@/components/layout"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export const ScriptsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/scripts",
  component: ScriptsPage,
})

function ScriptsPage() {
  return (
    <PageContainer
      title="Scripts"
      description="Podcast dialogue scripts generated from digests"
      actions={
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Generate Script
        </Button>
      }
    >
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Mic className="h-5 w-5 text-muted-foreground" />
            <CardTitle>Script List</CardTitle>
          </div>
          <CardDescription>
            Review and edit podcast scripts before audio generation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-64 items-center justify-center rounded-lg border border-dashed">
            <div className="text-center">
              <Mic className="mx-auto h-12 w-12 text-muted-foreground/50" />
              <p className="mt-2 text-sm text-muted-foreground">
                No scripts generated yet
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  )
}
