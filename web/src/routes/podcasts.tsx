/**
 * Podcasts Page
 *
 * Displays generated audio podcasts with playback controls.
 * Allows triggering new audio generation from approved scripts.
 *
 * Route: /podcasts
 */

import { createRoute } from "@tanstack/react-router"
import { Radio, Play } from "lucide-react"

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

export const PodcastsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "podcasts",
  component: PodcastsPage,
})

function PodcastsPage() {
  return (
    <PageContainer
      title="Podcasts"
      description="Generated audio podcasts with playback and download"
      actions={
        <Button>
          <Play className="mr-2 h-4 w-4" />
          Generate Audio
        </Button>
      }
    >
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Radio className="h-5 w-5 text-muted-foreground" />
            <CardTitle>Podcast List</CardTitle>
          </div>
          <CardDescription>
            Listen to and manage your generated podcasts.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-64 items-center justify-center rounded-lg border border-dashed">
            <div className="text-center">
              <Radio className="mx-auto h-12 w-12 text-muted-foreground/50" />
              <p className="mt-2 text-sm text-muted-foreground">
                No podcasts generated yet
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  )
}
