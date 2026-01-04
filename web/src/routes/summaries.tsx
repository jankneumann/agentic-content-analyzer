/**
 * Summaries Page
 *
 * Displays AI-generated summaries of newsletters.
 * Allows viewing summary details and triggering summarization.
 *
 * Route: /summaries
 */

import { createFileRoute } from "@tanstack/react-router"
import { Sparkles, Play } from "lucide-react"

import { PageContainer } from "@/components/layout"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export const Route = createFileRoute("/summaries")({
  component: SummariesPage,
})

function SummariesPage() {
  return (
    <PageContainer
      title="Summaries"
      description="AI-generated newsletter summaries with key themes and insights"
      actions={
        <Button>
          <Play className="mr-2 h-4 w-4" />
          Summarize Pending
        </Button>
      }
    >
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-muted-foreground" />
            <CardTitle>Summary List</CardTitle>
          </div>
          <CardDescription>
            View and manage AI-generated summaries of your newsletters.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-64 items-center justify-center rounded-lg border border-dashed">
            <div className="text-center">
              <Sparkles className="mx-auto h-12 w-12 text-muted-foreground/50" />
              <p className="mt-2 text-sm text-muted-foreground">
                No summaries generated yet
              </p>
              <p className="text-xs text-muted-foreground">
                Ingest newsletters first, then generate summaries
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  )
}
