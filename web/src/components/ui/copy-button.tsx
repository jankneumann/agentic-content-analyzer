/**
 * Copy Button Component
 *
 * A reusable button for copying text content to the clipboard.
 * Features:
 * - Visual feedback (check icon) on success
 * - Tooltip explanation
 * - Accessible button attributes
 */

import { useState, useCallback } from "react"
import { Copy, Check } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/ui/tooltip"

interface CopyButtonProps {
  /** Text content to copy to clipboard */
  content: string
  /** Additional CSS classes */
  className?: string
  /** Size of the button (default: h-6 w-6) */
  size?: "sm" | "default" | "icon"
}

export function CopyButton({ content, className, size = "default" }: CopyButtonProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error("Failed to copy:", err)
    }
  }, [content])

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            onClick={handleCopy}
            className={cn(
              "inline-flex items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              size === "default" && "h-6 w-6",
              size === "sm" && "h-5 w-5",
              size === "icon" && "h-8 w-8",
              className
            )}
            aria-label={copied ? "Copied" : "Copy to clipboard"}
          >
            {copied ? (
              <Check className={cn("text-green-500", size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3")} />
            ) : (
              <Copy className={cn(size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3")} />
            )}
          </button>
        </TooltipTrigger>
        <TooltipContent side="top">
          {copied ? "Copied!" : "Copy to clipboard"}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
