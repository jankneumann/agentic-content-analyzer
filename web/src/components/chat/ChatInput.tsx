/**
 * ChatInput Component
 *
 * Text input for sending chat messages with:
 * - Auto-expanding textarea
 * - Send button with loading state
 * - Optional web search toggle
 * - Voice input with microphone button
 * - LLM-based transcript cleanup
 * - Keyboard shortcut (Enter to send, Shift+Enter for newline)
 */

import * as React from "react"
import { Send, Loader2, Globe } from "lucide-react"
import { toast } from "sonner"
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
import { VoiceInputButton } from "@/components/voice/VoiceInputButton"
import { CleanupButton } from "@/components/voice/CleanupButton"
import { useVoiceInput } from "@/hooks/use-voice-input"
import { useVoiceSettings } from "@/hooks/use-settings"
import { cleanupTranscript } from "@/lib/api/voice"

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
  const [isCleaningUp, setIsCleaningUp] = React.useState(false)
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  // Voice settings from backend
  const { data: voiceSettings } = useVoiceSettings()
  const lang = voiceSettings?.input_language?.value ?? "en-US"
  const continuous = voiceSettings?.input_continuous?.value === "true"
  const autoSubmit = voiceSettings?.input_auto_submit?.value === "true"

  const canSubmit = value.trim().length > 0 && !isLoading && !disabled

  // Auto-resize helper
  const resizeTextarea = React.useCallback(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`
    }
  }, [])

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

  // Cleanup handler
  const handleCleanup = React.useCallback(async () => {
    const text = value.trim()
    if (!text) return

    setIsCleaningUp(true)
    try {
      const cleaned = await cleanupTranscript(text)
      setValue(cleaned)
      // Focus and resize after content change
      setTimeout(() => {
        textareaRef.current?.focus()
        resizeTextarea()
      }, 0)
    } catch {
      toast.error("Failed to clean up text. Please try again.")
    } finally {
      setIsCleaningUp(false)
    }
  }, [value, resizeTextarea])

  // Voice input hook
  const voiceInput = useVoiceInput({
    lang,
    continuous,
    onResult: React.useCallback(
      (transcript: string) => {
        // Check for cleanup key phrase in continuous mode
        const lower = transcript.toLowerCase().trim()
        if (continuous && (lower === "clean up" || lower === "cleanup")) {
          // Defer cleanup to next tick so state is settled
          setTimeout(() => handleCleanup(), 0)
          return
        }

        setValue((prev) => {
          const updated = prev ? `${prev} ${transcript}` : transcript
          // Auto-submit in single-utterance mode
          if (autoSubmit && !continuous && updated.trim().length > 0) {
            setTimeout(() => {
              onSubmit(updated.trim(), { enableWebSearch })
              setValue("")
              if (textareaRef.current) {
                textareaRef.current.style.height = "auto"
              }
            }, 0)
          }
          return updated
        })

        // Auto-resize after transcript insertion
        setTimeout(resizeTextarea, 0)

        // Return focus to textarea and position cursor at end
        setTimeout(() => {
          if (textareaRef.current) {
            textareaRef.current.focus()
            const len = textareaRef.current.value.length
            textareaRef.current.setSelectionRange(len, len)
          }
        }, 0)
      },
      [continuous, autoSubmit, enableWebSearch, onSubmit, resizeTextarea, handleCleanup]
    ),
    onError: React.useCallback((error: string) => {
      toast.error(error)
    }, []),
  })

  // Handle keyboard shortcuts
  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
      // Ctrl+Shift+C / Cmd+Shift+C for cleanup
      if (e.key === "C" && e.shiftKey && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        handleCleanup()
      }
    },
    [handleSubmit, handleCleanup]
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

  // Compose display value: show interim transcript with visual hint
  const displayValue = voiceInput.interimTranscript
    ? value + (value ? " " : "") + voiceInput.interimTranscript
    : value

  return (
    <div className={cn("space-y-2", className)}>
      {/* ARIA live region for voice input state */}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {voiceInput.isListening ? "Recording started" : ""}
      </div>

      {/* Input area */}
      <div className="relative flex items-end gap-2">
        <div className="relative flex-1">
          <Textarea
            ref={textareaRef}
            value={displayValue}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={
              voiceInput.isListening
                ? "Listening..."
                : placeholder
            }
            aria-label="Chat message"
            disabled={disabled || isLoading}
            className={cn(
              "min-h-[48px] max-h-[200px] resize-none pr-12",
              "scrollbar-thin scrollbar-thumb-muted",
              voiceInput.interimTranscript && "text-muted-foreground italic"
            )}
            rows={1}
          />

          {/* Character count */}
          <div className="absolute bottom-2 right-2 text-xs text-muted-foreground">
            {value.length}/{maxLength}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-col gap-1">
          {/* Voice input button */}
          <VoiceInputButton
            isListening={voiceInput.isListening}
            isSupported={voiceInput.isSupported}
            error={voiceInput.error}
            disabled={disabled || isLoading}
            onToggle={voiceInput.toggleListening}
          />

          {/* Cleanup button */}
          <CleanupButton
            isLoading={isCleaningUp}
            hasText={value.trim().length > 0}
            disabled={disabled || isLoading}
            onClick={handleCleanup}
          />

          {/* Send button */}
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="icon"
                  onClick={handleSubmit}
                  disabled={!canSubmit}
                  aria-label="Send message"
                  className="h-9 w-9 shrink-0"
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
          {voiceInput.isSupported && (
            <>
              ,{" "}
              <kbd className="rounded bg-muted px-1">
                {navigator.platform.includes("Mac") ? "⌘" : "Ctrl"}+Shift+C
              </kbd>{" "}
              to clean up
            </>
          )}
        </span>
      </p>
    </div>
  )
}
