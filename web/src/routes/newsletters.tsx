/**
 * Newsletters Page
 *
 * Displays a list of ingested newsletters with filtering and search.
 * Allows triggering new ingestion from Gmail or RSS feeds.
 *
 * Route: /newsletters
 */

import { createFileRoute } from "@tanstack/react-router"
import { Newspaper, Plus, RefreshCw } from "lucide-react"

import { PageContainer } from "@/components/layout"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

/**
 * Route definition
 */
export const Route = createFileRoute("/newsletters")({
  component: NewslettersPage,
})

/**
 * Newsletters page component
 *
 * TODO (Phase 1.5): Implement full newsletter list with:
 * - DataTable with sorting and filtering
 * - Status badges
 * - Ingestion triggers
 * - Newsletter detail view
 */
function NewslettersPage() {
  return (
    <PageContainer
      title="Newsletters"
      description="Manage ingested newsletters from Gmail and RSS feeds"
      actions={
        <div className="flex gap-2">
          <Button variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Ingest New
          </Button>
        </div>
      }
    >
      {/* Placeholder content */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Newspaper className="h-5 w-5 text-muted-foreground" />
            <CardTitle>Newsletter List</CardTitle>
          </div>
          <CardDescription>
            This page will display all ingested newsletters with filtering,
            sorting, and search capabilities.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-64 items-center justify-center rounded-lg border border-dashed">
            <div className="text-center">
              <Newspaper className="mx-auto h-12 w-12 text-muted-foreground/50" />
              <p className="mt-2 text-sm text-muted-foreground">
                No newsletters ingested yet
              </p>
              <Button className="mt-4" size="sm">
                <Plus className="mr-2 h-4 w-4" />
                Ingest from Gmail
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  )
}
