/**
 * Global Shortcut Settings
 *
 * Shows the current global shortcut binding and allows customization.
 * Only renders when running in a Tauri desktop context.
 */

import { isTauri } from "@/lib/platform"

export function ShortcutSettings() {
  if (!isTauri()) return null

  const isMac =
    typeof navigator !== "undefined" && navigator.platform.startsWith("Mac")
  const defaultShortcut = isMac ? "\u2318+\u21e7+Space" : "Ctrl+Shift+Space"

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-foreground">
        Global Voice Shortcut
      </h3>
      <p className="text-sm text-muted-foreground">
        Press this shortcut from any app to activate voice input.
      </p>
      <div className="flex items-center gap-2">
        <kbd className="rounded border border-border bg-muted px-2 py-1 font-mono text-xs text-foreground">
          {defaultShortcut}
        </kbd>
        <span className="text-xs text-muted-foreground">
          (Shortcut customization coming soon)
        </span>
      </div>
    </div>
  )
}
