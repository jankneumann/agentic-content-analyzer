/**
 * Voice Settings Sub-page
 *
 * TTS/STT configuration for audio digests and podcasts.
 * Route: /settings/voice
 */

import { createRoute } from "@tanstack/react-router"
import { Volume2 } from "lucide-react"

import { SettingsRoute } from "../settings"
import { PageSection } from "@/components/layout"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { VoiceConfigurator } from "@/components/settings/VoiceConfigurator"

export const SettingsVoiceRoute = createRoute({
  getParentRoute: () => SettingsRoute,
  path: "voice",
  component: VoiceSettings,
})

function VoiceSettings() {
  return (
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
  )
}
