/**
 * CleanupButton Component
 *
 * Triggers LLM-based cleanup of voice transcript text.
 * Shows a sparkle/wand icon with loading spinner state.
 */

import { Sparkles, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface CleanupButtonProps {
  /** Whether a cleanup request is in progress */
  isLoading: boolean
  /** Whether there is text to clean up */
  hasText: boolean
  /** Whether the button is disabled */
  disabled?: boolean
  /** Trigger cleanup */
  onClick: () => void
  /** Additional CSS classes */
  className?: string
}

export function CleanupButton({
  isLoading,
  hasText,
  disabled = false,
  onClick,
  className,
}: CleanupButtonProps) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onClick}
            disabled={disabled || !hasText || isLoading}
            aria-label="Clean up text with AI"
            className={cn("h-9 w-9 shrink-0", className)}
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">Clean up text with AI</p>
          <p className="text-xs text-muted-foreground">Ctrl+Shift+C</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
