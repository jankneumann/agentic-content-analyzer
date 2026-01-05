/**
 * Digests Page
 *
 * Displays daily and weekly digest documents.
 * Supports review workflow and revision.
 *
 * Route: /digests
 */

import { createRoute } from "@tanstack/react-router"
import { FileText, Plus } from "lucide-react"

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

export const DigestsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "digests",
  component: DigestsPage,
})

function DigestsPage() {
  return (
    <PageContainer
      title="Digests"
      description="Daily and weekly aggregated reports for your audience"
      actions={
        <div className="flex gap-2">
          <Button variant="outline">Create Daily</Button>
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Create Weekly
          </Button>
        </div>
      }
    >
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-muted-foreground" />
            <CardTitle>Digest List</CardTitle>
          </div>
          <CardDescription>
            View, review, and manage your generated digests.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-64 items-center justify-center rounded-lg border border-dashed">
            <div className="text-center">
              <FileText className="mx-auto h-12 w-12 text-muted-foreground/50" />
              <p className="mt-2 text-sm text-muted-foreground">
                No digests created yet
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  )
}
