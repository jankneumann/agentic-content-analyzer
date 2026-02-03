/**
 * ContextChip Component
 *
 * Displays a selected text snippet as a chip in the feedback panel.
 * Shows truncated text with source label and remove button.
 *
 * Features:
 * - Truncated text preview
 * - Source label (Newsletter/Summary)
 * - Remove button
 * - Hover to see full text
 */

import { X } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { ContextItem } from "@/types/review"

interface ContextChipProps {
  item: ContextItem
  onRemove: () => void
}

export function ContextChip({ item, onRemove }: ContextChipProps) {
  // Truncate text for display
  const displayText = item.text.length > 60 ? item.text.slice(0, 60) + "..." : item.text

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            tabIndex={0}
            className={cn(
              "group flex items-center gap-1.5 rounded-md border px-2 py-1 outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
              "bg-muted/50 text-xs transition-colors hover:bg-muted",
              item.source === "left"
                ? "border-blue-500/30"
                : "border-green-500/30"
            )}
          >
            {/* Source indicator */}
            <span
              className={cn(
                "shrink-0 rounded px-1 py-0.5 text-[10px] font-medium",
                item.source === "left"
                  ? "bg-blue-500/20 text-blue-700 dark:text-blue-400"
                  : "bg-green-500/20 text-green-700 dark:text-green-400"
              )}
            >
              {item.source === "left" ? "NL" : "SUM"}
            </span>

            {/* Text preview */}
            <span className="max-w-[200px] truncate text-muted-foreground">
              "{displayText}"
            </span>

            {/* Remove button */}
            <Button
              variant="ghost"
              size="icon"
              className="h-4 w-4 shrink-0 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 focus:opacity-100"
              onClick={(e) => {
                e.stopPropagation()
                onRemove()
              }}
              aria-label="Remove selection"
            >
              <X className="h-3 w-3" />
            </Button>
          </div>
        </TooltipTrigger>
        <TooltipContent
          side="top"
          className="max-w-[300px] whitespace-pre-wrap text-xs"
        >
          <p className="mb-1 font-medium">{item.paneLabel}</p>
          <p className="text-muted-foreground">"{item.text}"</p>
          <p className="mt-1 text-[10px] text-muted-foreground/70">
            {item.text.length} characters
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

interface ContextChipListProps {
  items: ContextItem[]
  onRemove: (id: string) => void
  onClearAll?: () => void
  maxChars: number
  usedChars: number
}

/**
 * List of context chips with clear all and character count
 */
export function ContextChipList({
  items,
  onRemove,
  onClearAll,
  maxChars,
  usedChars,
}: ContextChipListProps) {
  if (items.length === 0) {
    return null
  }

  return (
    <div className="space-y-2">
      {/* Header with count and clear */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          Context: {items.length} selection{items.length !== 1 ? "s" : ""}
        </span>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground/70">
            {usedChars} / {maxChars} chars
          </span>
          {onClearAll && items.length > 1 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-5 px-1.5 text-[10px]"
              onClick={onClearAll}
            >
              Clear all
            </Button>
          )}
        </div>
      </div>

      {/* Chips */}
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <ContextChip
            key={item.id}
            item={item}
            onRemove={() => onRemove(item.id)}
          />
        ))}
      </div>
    </div>
  )
}
