/**
 * Settings Page
 *
 * Application configuration including:
 * - LLM prompt customization
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
import { ModelConfigurator } from "@/components/settings/ModelConfigurator"
import { VoiceConfigurator } from "@/components/settings/VoiceConfigurator"
import { ConnectionDashboard } from "@/components/settings/ConnectionDashboard"

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
              Select which model to use for each pipeline step. Cost per million
              tokens shown for each option. Environment variables take precedence
              over database overrides.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ModelConfigurator />
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
              Configure text-to-speech provider, voice, and speed for audio
              digests and podcasts. Select presets for quick configuration.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <VoiceConfigurator />
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
