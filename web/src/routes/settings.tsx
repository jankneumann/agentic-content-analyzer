/**
 * Settings Page
 *
 * Application configuration including:
 * - Model selection per pipeline step
 * - Voice configuration for podcasts
 * - API connections
 *
 * Route: /settings
 */

import { createFileRoute } from "@tanstack/react-router"
import { Cpu, Volume2, Database } from "lucide-react"

import { PageContainer, PageSection } from "@/components/layout"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
})

function SettingsPage() {
  return (
    <PageContainer
      title="Settings"
      description="Configure application behavior and integrations"
    >
      <PageSection title="Model Configuration">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Cpu className="h-5 w-5 text-muted-foreground" />
              <CardTitle className="text-base">LLM Models</CardTitle>
            </div>
            <CardDescription>
              Select models for each pipeline step.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex h-32 items-center justify-center rounded-lg border border-dashed">
              <p className="text-sm text-muted-foreground">
                Model configuration coming in Phase 3
              </p>
            </div>
          </CardContent>
        </Card>
      </PageSection>

      <PageSection title="Voice Configuration">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Volume2 className="h-5 w-5 text-muted-foreground" />
              <CardTitle className="text-base">TTS Voices</CardTitle>
            </div>
            <CardDescription>
              Configure voices for podcast generation.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex h-32 items-center justify-center rounded-lg border border-dashed">
              <p className="text-sm text-muted-foreground">
                Voice configuration coming in Phase 3
              </p>
            </div>
          </CardContent>
        </Card>
      </PageSection>

      <PageSection title="Connections">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-muted-foreground" />
              <CardTitle className="text-base">API Connections</CardTitle>
            </div>
            <CardDescription>
              Status of backend service connections.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex h-32 items-center justify-center rounded-lg border border-dashed">
              <p className="text-sm text-muted-foreground">
                Connection status coming in Phase 3
              </p>
            </div>
          </CardContent>
        </Card>
      </PageSection>
    </PageContainer>
  )
}
