/**
 * Review Queue Page
 *
 * Displays items pending review across the pipeline.
 * Central hub for approval workflows.
 *
 * Route: /review
 */

import { createRoute } from "@tanstack/react-router"
import { FileText, Mic } from "lucide-react"

import { Route as rootRoute } from "./__root"
import { PageContainer, PageSection } from "@/components/layout"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export const ReviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "review",
  component: ReviewPage,
})

function ReviewPage() {
  return (
    <PageContainer
      title="Review Queue"
      description="Items pending review and approval across the pipeline"
    >
      <PageSection title="Pending Digests" description="Digests awaiting review">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-muted-foreground" />
              <CardTitle className="text-base">Digests</CardTitle>
            </div>
            <CardDescription>
              Review and approve digest content before delivery.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex h-32 items-center justify-center rounded-lg border border-dashed">
              <p className="text-sm text-muted-foreground">
                No digests pending review
              </p>
            </div>
          </CardContent>
        </Card>
      </PageSection>

      <PageSection title="Pending Scripts" description="Scripts awaiting review">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Mic className="h-5 w-5 text-muted-foreground" />
              <CardTitle className="text-base">Scripts</CardTitle>
            </div>
            <CardDescription>
              Review podcast scripts before audio generation.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex h-32 items-center justify-center rounded-lg border border-dashed">
              <p className="text-sm text-muted-foreground">
                No scripts pending review
              </p>
            </div>
          </CardContent>
        </Card>
      </PageSection>
    </PageContainer>
  )
}
