/**
 * Sources Settings Sub-page
 *
 * View, add, enable/disable, and delete ingestion sources.
 * Route: /settings/sources
 */

import { createRoute } from "@tanstack/react-router"
import { Rss } from "lucide-react"

import { SettingsRoute } from "../settings"
import { PageSection } from "@/components/layout"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { SourcesConfigurator } from "@/components/settings/SourcesConfigurator"

export const SettingsSourcesRoute = createRoute({
  getParentRoute: () => SettingsRoute,
  path: "sources",
  component: SourcesSettings,
})

function SourcesSettings() {
  return (
    <PageSection title="Source Configuration">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Rss className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">Ingestion Sources</CardTitle>
          </div>
          <CardDescription>
            Manage the sources content is ingested from. Sources defined in YAML
            can be enabled or disabled here; sources added in the app can also be
            deleted. Disabling a YAML source creates a database override.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SourcesConfigurator />
        </CardContent>
      </Card>
    </PageSection>
  )
}
