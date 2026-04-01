/**
 * Models Settings Sub-page
 *
 * Model selection per pipeline step.
 * Route: /settings/models
 */

import { createRoute } from "@tanstack/react-router"
import { Cpu } from "lucide-react"

import { SettingsRoute } from "../settings"
import { PageSection } from "@/components/layout"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ModelConfigurator } from "@/components/settings/ModelConfigurator"

export const SettingsModelsRoute = createRoute({
  getParentRoute: () => SettingsRoute,
  path: "models",
  component: ModelsSettings,
})

function ModelsSettings() {
  return (
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
  )
}
