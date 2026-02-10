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

import { createRoute } from "@tanstack/react-router"
import { Cpu, Volume2, Database, MessageSquareCode } from "lucide-react"

import { Route as rootRoute } from "./__root"
import { PageContainer, PageSection } from "@/components/layout"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { PromptManager } from "@/components/prompts/PromptManager"

export const SettingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "settings",
  component: SettingsPage,
})

function SettingsPage() {
  return (
    <PageContainer
      title="Settings"
      description="Configure application behavior and integrations"
    >
      <PageSection
        title="LLM Prompts"
        description="View and customize prompts used across all pipeline steps. Overrides are stored in the database and persist across deploys."
      >
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <MessageSquareCode className="h-5 w-5 text-muted-foreground" />
              <CardTitle className="text-base">Prompt Configuration</CardTitle>
            </div>
            <CardDescription>
              Edit prompt templates, test with sample variables, and reset to
              defaults. Changes take effect on the next pipeline run.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <PromptManager />
          </CardContent>
        </Card>
      </PageSection>

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
