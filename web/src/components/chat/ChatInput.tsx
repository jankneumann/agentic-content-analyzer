/**
 * ChatInput Component
 *
 * Text input for sending chat messages with:
 * - Auto-expanding textarea
 * - Send button with loading state
 * - Optional web search toggle
 * - Keyboard shortcut (Enter to send, Shift+Enter for newline)
 */

import * as React from "react"
import { Send, Loader2, Globe } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Toggle } from "@/components/ui/toggle"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface ChatInputProps {
  /** Callback when message is submitted */
  onSubmit: (content: string, options?: { enableWebSearch?: boolean }) => void
  /** Whether a message is currently being sent/streamed */
  isLoading?: boolean
  /** Placeholder text */
  placeholder?: string
  /** Whether web search toggle is available */
  webSearchEnabled?: boolean
  /** Maximum message length */
  maxLength?: number
  /** Disable the input */
  disabled?: boolean
  /** Additional CSS classes */
  className?: string
}

export function ChatInput({
  onSubmit,
  isLoading = false,
  placeholder = "Type a message...",
  webSearchEnabled = false,
  maxLength = 2000,
  disabled = false,
  className,
}: ChatInputProps) {
  const [value, setValue] = React.useState("")
  const [enableWebSearch, setEnableWebSearch] = React.useState(false)
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  const canSubmit = value.trim().length > 0 && !isLoading && !disabled

  // Handle form submission
  const handleSubmit = React.useCallback(() => {
    if (!canSubmit) return

    onSubmit(value.trim(), { enableWebSearch })
    setValue("")
    setEnableWebSearch(false)

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }
  }, [canSubmit, value, enableWebSearch, onSubmit])

  // Handle keyboard shortcuts
  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit]
  )

  // Auto-resize textarea
  const handleChange = React.useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newValue = e.target.value
      if (newValue.length <= maxLength) {
        setValue(newValue)
      }

      // Auto-resize
      const textarea = e.target
      textarea.style.height = "auto"
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
    },
    [maxLength]
  )

  return (
    <div className={cn("space-y-2", className)}>
      {/* Input area */}
      <div className="relative flex items-end gap-2">
        <div className="relative flex-1">
          <Textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            aria-label="Chat message"
            disabled={disabled || isLoading}
            className={cn(
              "min-h-[48px] max-h-[200px] resize-none pr-12",
              "scrollbar-thin scrollbar-thumb-muted"
            )}
            rows={1}
          />

          {/* Character count */}
          <div className="absolute bottom-2 right-2 text-xs text-muted-foreground">
            {value.length}/{maxLength}
          </div>
        </div>

        {/* Send button */}
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                onClick={handleSubmit}
                disabled={!canSubmit}
                aria-label="Send message"
                className="h-10 w-10 shrink-0"
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Send message</p>
              <p className="text-xs text-muted-foreground">Press Enter</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>

      {/* Options row */}
      {webSearchEnabled && (
        <div className="flex items-center gap-4 px-1">
          <Toggle
            pressed={enableWebSearch}
            onPressedChange={setEnableWebSearch}
            disabled={disabled || isLoading}
            aria-label="Toggle web search"
            className={cn(
              "h-auto gap-1.5 px-2 py-1 text-xs",
              "data-[state=on]:bg-blue-500/10 data-[state=on]:text-blue-500",
              "text-muted-foreground hover:text-foreground"
            )}
          >
            <Globe className="h-3 w-3" />
            Web search {enableWebSearch ? "on" : "off"}
          </Toggle>
        </div>
      )}

      {/* Helper text */}
      <p className="px-1 text-xs text-muted-foreground">
        <span className="hidden sm:inline">
          Press <kbd className="rounded bg-muted px-1">Enter</kbd> to send,{" "}
          <kbd className="rounded bg-muted px-1">Shift+Enter</kbd> for new line
        </span>
      </p>
    </div>
  )
}
