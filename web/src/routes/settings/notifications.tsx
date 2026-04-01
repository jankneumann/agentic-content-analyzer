/**
 * Notifications Settings Sub-page
 *
 * Per-event notification toggles.
 * Route: /settings/notifications
 */

import { createRoute } from "@tanstack/react-router"
import { Bell } from "lucide-react"

import { SettingsRoute } from "../settings"
import { PageSection } from "@/components/layout"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { NotificationConfigurator } from "@/components/settings/NotificationConfigurator"
import { PushNotificationToggle } from "@/components/settings/PushNotificationToggle"

export const SettingsNotificationsRoute = createRoute({
  getParentRoute: () => SettingsRoute,
  path: "notifications",
  component: NotificationsSettings,
})

function NotificationsSettings() {
  return (
    <PageSection title="Notifications">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Bell className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">Notification Preferences</CardTitle>
          </div>
          <CardDescription>
            Enable or disable notifications for each pipeline event type.
            Disabled event types are still stored but not delivered to clients.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PushNotificationToggle />
          <NotificationConfigurator />
        </CardContent>
      </Card>
    </PageSection>
  )
}
