/**
 * VoiceInputButton Component
 *
 * Microphone toggle button for voice input with visual state indicators:
 * - Idle: mic icon
 * - Recording: pulsing red ring animation
 * - Processing: spinning Loader2 icon (on-device transcription in progress)
 * - Disabled: grayed out with tooltip (unsupported browsers)
 * - Error: brief error indicator
 */

import { Mic, MicOff, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface VoiceInputButtonProps {
  /** Whether voice input is currently active */
  isListening: boolean
  /** Whether on-device transcription is running after recording stops */
  isProcessing?: boolean
  /** Whether the Web Speech API is supported */
  isSupported: boolean
  /** Current error message */
  error?: string | null
  /** Whether the parent input is disabled */
  disabled?: boolean
  /** Toggle listening on/off */
  onToggle: () => void
  /** Additional CSS classes */
  className?: string
}

export function VoiceInputButton({
  isListening,
  isProcessing = false,
  isSupported,
  error,
  disabled = false,
  onToggle,
  className,
}: VoiceInputButtonProps) {
  const isDisabled = !isSupported || disabled || isProcessing

  const tooltipText = !isSupported
    ? "Voice input is not supported in this browser. Try Chrome, Edge, or Safari."
    : error
      ? error
      : isProcessing
        ? "Transcribing audio..."
        : isListening
          ? "Stop voice input"
          : "Start voice input"

  const handleClick = (e: React.MouseEvent) => {
    if (isDisabled) {
      e.preventDefault()
      return
    }
    onToggle()
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={handleClick}
            aria-disabled={isDisabled}
            aria-label={
              isProcessing
                ? "Transcribing audio"
                : isListening
                  ? "Stop voice input"
                  : "Start voice input"
            }
            aria-pressed={isListening}
            aria-busy={isProcessing}
            className={cn(
              "relative h-9 w-9 shrink-0",
              isListening && "text-red-500 hover:text-red-600",
              isProcessing && "text-amber-500",
              error && !isListening && !isProcessing && "text-destructive",
              isDisabled &&
                "cursor-not-allowed opacity-50 hover:bg-transparent hover:text-inherit",
              className
            )}
          >
            {/* Pulsing ring animation during recording */}
            {isListening && !isProcessing && (
              <span
                className="animate-pulse-ring absolute inset-0 rounded-md"
                aria-hidden="true"
              />
            )}
            {!isSupported ? (
              <MicOff className="h-4 w-4" />
            ) : isProcessing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Mic className={cn("h-4 w-4", isListening && "relative z-10")} />
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <p className="max-w-[200px] text-xs">{tooltipText}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
