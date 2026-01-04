/**
 * Themes Page
 *
 * Displays theme analysis with knowledge graph visualization.
 * Shows entities, relationships, and theme evolution over time.
 *
 * Route: /themes
 */

import { createFileRoute } from "@tanstack/react-router"
import { BarChart3, Network, Table2 } from "lucide-react"

import { PageContainer } from "@/components/layout"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export const Route = createFileRoute("/themes")({
  component: ThemesPage,
})

function ThemesPage() {
  return (
    <PageContainer
      title="Themes"
      description="Knowledge graph analysis showing themes, entities, and relationships"
      actions={
        <div className="flex gap-2">
          <Button variant="outline">
            <Table2 className="mr-2 h-4 w-4" />
            Table View
          </Button>
          <Button variant="outline">
            <Network className="mr-2 h-4 w-4" />
            Graph View
          </Button>
          <Button>Analyze Themes</Button>
        </div>
      }
    >
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-muted-foreground" />
            <CardTitle>Theme Analysis</CardTitle>
          </div>
          <CardDescription>
            Explore patterns and connections across your newsletter content.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-96 items-center justify-center rounded-lg border border-dashed">
            <div className="text-center">
              <Network className="mx-auto h-12 w-12 text-muted-foreground/50" />
              <p className="mt-2 text-sm text-muted-foreground">
                Knowledge graph visualization will appear here
              </p>
              <p className="text-xs text-muted-foreground">
                Requires summaries to be generated first
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  )
}
