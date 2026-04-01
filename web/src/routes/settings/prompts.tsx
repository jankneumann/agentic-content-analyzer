/**
 * Prompts Settings Sub-page
 *
 * LLM prompt template management.
 * Route: /settings/prompts
 */

import { createRoute } from "@tanstack/react-router"
import { MessageSquareCode } from "lucide-react"

import { SettingsRoute } from "../settings"
import { PageSection } from "@/components/layout"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { PromptManager } from "@/components/prompts/PromptManager"

export const SettingsPromptsRoute = createRoute({
  getParentRoute: () => SettingsRoute,
  path: "prompts",
  component: PromptsSettings,
})

function PromptsSettings() {
  return (
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
  )
}
