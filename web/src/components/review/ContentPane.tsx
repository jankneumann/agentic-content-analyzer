/**
 * ContentPane Component
 *
 * Base component for content panes in the review layout.
 * Provides scroll handling and prepares for text selection support.
 *
 * Features:
 * - Scrollable container
 * - Pane identification for selection context
 * - Consistent styling
 */

import * as React from "react"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { ContentPaneProps } from "@/types/review"

export function ContentPane({
  paneId,
  paneLabel,
  children,
  className,
  selectionEnabled = true,
}: ContentPaneProps) {
  const paneRef = React.useRef<HTMLDivElement>(null)

  return (
    <div
      ref={paneRef}
      data-pane-id={paneId}
      data-pane-label={paneLabel}
      data-selection-enabled={selectionEnabled}
      className={cn("flex h-full flex-col overflow-hidden", className)}
    >
      <ScrollArea className="flex-1">
        <div className="p-4">{children}</div>
      </ScrollArea>
    </div>
  )
}
