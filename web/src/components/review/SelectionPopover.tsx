/**
 * SelectionPopover Component
 *
 * Floating popover that appears near text selection with
 * "Add to context" button. Uses portal to render outside
 * the scrollable container.
 *
 * Features:
 * - Positions near selection
 * - "Add to context" action
 * - Shows remaining context capacity
 * - Keyboard accessible
 */

import * as React from "react"
import { createPortal } from "react-dom"
import { Plus, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { useReviewContext } from "@/contexts/ReviewContext"
import { REVIEW_LIMITS } from "@/types/review"
import type { TextSelection } from "@/hooks/use-text-selection"

interface SelectionPopoverProps {
  selection: TextSelection
  onAdd: () => void
  onDismiss: () => void
}

export function SelectionPopover({
  selection,
  onAdd,
  onDismiss,
}: SelectionPopoverProps) {
  const { canAddContext, remainingContextChars, contextItems } = useReviewContext()
  const popoverRef = React.useRef<HTMLDivElement>(null)

  // Calculate if this selection would fit
  const selectionLength = Math.min(selection.text.length, REVIEW_LIMITS.MAX_CHARS_PER_SELECTION)
  const wouldFit = selectionLength <= remainingContextChars
  const atItemLimit = contextItems.length >= REVIEW_LIMITS.MAX_CONTEXT_ITEMS

  // Determine if we can add
  const canAdd = canAddContext && wouldFit && !atItemLimit

  // Position the popover
  const [position, setPosition] = React.useState({ top: 0, left: 0 })

  React.useEffect(() => {
    if (!popoverRef.current) return

    const popoverRect = popoverRef.current.getBoundingClientRect()
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    // Start position: above the selection, centered
    let top = selection.position.y - popoverRect.height - 8
    let left = selection.position.x - popoverRect.width / 2

    // Keep within viewport bounds
    if (left < 8) left = 8
    if (left + popoverRect.width > viewportWidth - 8) {
      left = viewportWidth - popoverRect.width - 8
    }

    // If would go above viewport, show below selection instead
    if (top < 8) {
      top = selection.position.y + 24 // Below selection
    }

    // If would go below viewport, clamp
    if (top + popoverRect.height > viewportHeight - 8) {
      top = viewportHeight - popoverRect.height - 8
    }

    setPosition({ top, left })
  }, [selection.position])

  // Handle keyboard
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onDismiss()
      } else if (e.key === "Enter" && canAdd) {
        onAdd()
      }
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [onDismiss, onAdd, canAdd])

  // Truncate preview text
  const previewText =
    selection.text.length > 50 ? selection.text.slice(0, 50) + "..." : selection.text

  const content = (
    <div
      ref={popoverRef}
      data-selection-popover
      className={cn(
        "fixed z-50 rounded-lg border bg-popover p-2 shadow-lg",
        "animate-in fade-in-0 zoom-in-95 duration-100"
      )}
      style={{
        top: position.top,
        left: position.left,
      }}
    >
      <div className="flex items-center gap-2">
        {canAdd ? (
          <Button
            size="sm"
            variant="default"
            className="h-7 gap-1.5 px-2 text-xs"
            onClick={onAdd}
          >
            <Plus className="h-3.5 w-3.5" />
            Add to context
          </Button>
        ) : (
          <div className="flex items-center gap-1.5 px-2 text-xs text-muted-foreground">
            <AlertCircle className="h-3.5 w-3.5" />
            {atItemLimit
              ? "Max selections reached"
              : !wouldFit
                ? "Selection too long"
                : "Cannot add context"}
          </div>
        )}

        <span className="text-xs text-muted-foreground">
          from {selection.paneLabel}
        </span>
      </div>

      {/* Preview */}
      <div className="mt-1.5 max-w-[250px] truncate text-xs text-muted-foreground">
        "{previewText}"
      </div>

      {/* Character count hint */}
      {canAdd && (
        <div className="mt-1 text-[10px] text-muted-foreground/70">
          {selectionLength} chars • {remainingContextChars - selectionLength} remaining
        </div>
      )}
    </div>
  )

  // Render via portal to escape scroll containers
  return createPortal(content, document.body)
}
