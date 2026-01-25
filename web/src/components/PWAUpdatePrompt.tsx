/**
 * PWA Update Prompt Component
 *
 * Displays a toast notification when a new version of the app
 * is available. Uses the vite-plugin-pwa's useRegisterSW hook
 * to detect service worker updates.
 *
 * The registerType: 'autoUpdate' in vite.config.ts means:
 * - New service worker installs automatically in background
 * - This component shows notification when update is ready
 * - User clicks "Refresh" to activate the new version
 */

import { useRegisterSW } from "virtual:pwa-register/react"

export function PWAUpdatePrompt() {
  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(swUrl, registration) {
      // Check for updates every hour
      if (registration) {
        setInterval(
          () => {
            registration.update()
          },
          60 * 60 * 1000
        )
      }
      console.log("[PWA] Service worker registered:", swUrl)
    },
    onRegisterError(error) {
      console.error("[PWA] Service worker registration error:", error)
    },
  })

  // Don't render anything if no update available
  if (!needRefresh) return null

  return (
    <div
      role="alert"
      aria-live="polite"
      className="fixed bottom-4 left-4 right-4 z-50 mx-auto max-w-md rounded-lg bg-primary p-4 text-primary-foreground shadow-lg md:bottom-6 md:left-auto md:right-6"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1">
          <p className="font-medium">Update available</p>
          <p className="text-sm opacity-90">
            A new version is ready to install.
          </p>
        </div>
        <button
          onClick={() => updateServiceWorker(true)}
          className="shrink-0 rounded-md bg-primary-foreground px-4 py-2 text-sm font-medium text-primary transition-colors hover:opacity-90"
        >
          Refresh
        </button>
      </div>
    </div>
  )
}
