/**
 * FeedbackPanel Component
 *
 * Panel at the bottom of the review layout for:
 * - Displaying context selections (chips)
 * - Feedback text input
 * - Generate preview / accept / reject buttons
 *
 * Features:
 * - Character count for feedback
 * - Context chips with limits
 * - Loading state during generation
 * - Preview mode with accept/reject
 */

import * as React from "react"
import { Loader2, Sparkles, Check, X, RotateCcw } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { ContextChipList } from "./ContextChip"
import { useReviewContext } from "@/contexts/ReviewContext"
import { REVIEW_LIMITS } from "@/types/review"

interface FeedbackPanelProps {
  /** Whether we're in preview mode */
  isPreviewMode?: boolean
  /** Handler for generating preview */
  onGeneratePreview?: () => void
  /** Handler for accepting preview */
  onAcceptPreview?: () => void
  /** Handler for rejecting preview */
  onRejectPreview?: () => void
  /** Whether generation is in progress */
  isGenerating?: boolean
  /** Whether accept is in progress */
  isAccepting?: boolean
  /** Error message to display */
  error?: string | null
}

export function FeedbackPanel({
  isPreviewMode = false,
  onGeneratePreview,
  onAcceptPreview,
  onRejectPreview,
  isGenerating = false,
  isAccepting = false,
  error,
}: FeedbackPanelProps) {
  const {
    contextItems,
    feedback,
    setFeedback,
    removeContextItem,
    clearAllContext,
    totalContextChars,
  } = useReviewContext()

  const feedbackLength = feedback.length
  const maxFeedbackLength = REVIEW_LIMITS.MAX_FEEDBACK_LENGTH
  const hasContent = contextItems.length > 0 || feedback.trim().length > 0

  // Handle keyboard shortcut (Cmd/Ctrl + Enter to generate)
  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent) => {
      if (
        (e.metaKey || e.ctrlKey) &&
        e.key === "Enter" &&
        hasContent &&
        !isGenerating
      ) {
        e.preventDefault()
        onGeneratePreview?.()
      }
    },
    [hasContent, isGenerating, onGeneratePreview]
  )

  return (
    <div className="space-y-3 px-4 py-3">
      {/* Error message */}
      {error && (
        <div className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm">
          {error}
        </div>
      )}

      {/* Context chips */}
      {contextItems.length > 0 && (
        <ContextChipList
          items={contextItems}
          onRemove={removeContextItem}
          onClearAll={clearAllContext}
          maxChars={REVIEW_LIMITS.MAX_TOTAL_CONTEXT_CHARS}
          usedChars={totalContextChars}
        />
      )}

      {/* Feedback input */}
      <div className="space-y-2">
        <div className="relative">
          <Textarea
            placeholder={
              isPreviewMode
                ? "Preview generated. Review changes above."
                : "What should be improved in this summary? (optional)"
            }
            value={feedback}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
              setFeedback(e.target.value)
            }
            onKeyDown={handleKeyDown}
            disabled={isGenerating || isPreviewMode}
            className={cn(
              "min-h-[80px] resize-none pr-20",
              isPreviewMode && "bg-muted/50"
            )}
            maxLength={maxFeedbackLength}
            aria-describedby="feedback-char-count"
          />
          <div
            id="feedback-char-count"
            className={cn(
              "absolute right-2 bottom-2 text-xs transition-colors",
              feedbackLength > maxFeedbackLength * 0.9
                ? "font-medium text-amber-500"
                : "text-muted-foreground",
              feedbackLength >= maxFeedbackLength && "text-destructive"
            )}
            aria-label={`${feedbackLength} of ${maxFeedbackLength} characters`}
            aria-live="polite"
          >
            {feedbackLength} / {maxFeedbackLength}
          </div>
        </div>

        {/* Hint text */}
        {!isPreviewMode &&
          contextItems.length === 0 &&
          feedback.length === 0 && (
            <p className="text-muted-foreground text-xs">
              Select text from either pane to add context, or type feedback
              directly.
            </p>
          )}
      </div>

      {/* Action buttons */}
      <div className="flex items-center justify-between">
        <div className="text-muted-foreground text-xs">
          {!isPreviewMode && hasContent && (
            <span className="hidden sm:inline">
              Press <kbd className="bg-muted rounded px-1">⌘</kbd>+
              <kbd className="bg-muted rounded px-1">Enter</kbd> to generate
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {isPreviewMode ? (
            // Preview mode: Accept/Reject buttons
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={onRejectPreview}
                disabled={isAccepting}
                className="gap-1.5"
              >
                <X className="h-4 w-4" />
                Reject
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  // Reset and try again
                  onRejectPreview?.()
                }}
                disabled={isAccepting}
                className="gap-1.5"
              >
                <RotateCcw className="h-4 w-4" />
                Regenerate
              </Button>
              <Button
                size="sm"
                onClick={onAcceptPreview}
                disabled={isAccepting}
                className="gap-1.5"
              >
                {isAccepting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Check className="h-4 w-4" />
                )}
                Accept & Save
              </Button>
            </>
          ) : (
            // Normal mode: Generate button
            <Button
              size="sm"
              onClick={onGeneratePreview}
              disabled={!hasContent || isGenerating}
              className="gap-1.5"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Generate Preview
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
