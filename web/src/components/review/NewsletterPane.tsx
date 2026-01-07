/**
 * NewsletterPane Component
 *
 * Renders newsletter content in the review layout.
 * Supports both plain text (default) and HTML view modes.
 *
 * Features:
 * - Plain text default for consistent selection behavior
 * - HTML toggle for users who want formatting
 * - Header with newsletter metadata
 * - Empty state handling
 */

import * as React from "react"
import { FileText, Code } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { ReviewPaneHeader } from "./ReviewLayout"
import type { Newsletter } from "@/types"

interface NewsletterPaneProps {
  newsletter: Newsletter | null | undefined
  className?: string
}

type ViewMode = "text" | "html"

export function NewsletterPane({ newsletter, className }: NewsletterPaneProps) {
  const [viewMode, setViewMode] = React.useState<ViewMode>("text")

  // Check if HTML content is available
  const hasHtml = Boolean(newsletter?.raw_html)
  const hasText = Boolean(newsletter?.raw_text)

  // Toggle view mode
  const toggleViewMode = React.useCallback(() => {
    setViewMode((prev) => (prev === "text" ? "html" : "text"))
  }, [])

  // Determine what content to show
  const showHtml = viewMode === "html" && hasHtml
  const content = showHtml ? newsletter?.raw_html : newsletter?.raw_text

  return (
    <div
      className={cn("flex h-full flex-col", className)}
      data-pane-id="left"
      data-pane-label="Newsletter"
    >
      <ReviewPaneHeader
        title="Newsletter"
        subtitle={newsletter?.publication || newsletter?.sender || undefined}
        actions={
          hasHtml && hasText ? (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={toggleViewMode}
                    className="h-7 gap-1.5 px-2 text-xs"
                  >
                    {viewMode === "text" ? (
                      <>
                        <Code className="h-3.5 w-3.5" />
                        <span className="hidden sm:inline">HTML</span>
                      </>
                    ) : (
                      <>
                        <FileText className="h-3.5 w-3.5" />
                        <span className="hidden sm:inline">Text</span>
                      </>
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  {viewMode === "text" ? "Switch to HTML view" : "Switch to plain text"}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          ) : null
        }
      />

      <ScrollArea className="flex-1">
        <div className="p-4">
          {/* Newsletter title */}
          {newsletter?.title && (
            <h2 className="mb-4 text-lg font-semibold">
              <span className="text-muted-foreground font-normal">[{newsletter.id}]</span>{" "}
              {newsletter.title}
            </h2>
          )}

          {/* Content area */}
          {content ? (
            showHtml ? (
              <div
                className="prose prose-sm max-w-none dark:prose-invert"
                dangerouslySetInnerHTML={{ __html: content }}
              />
            ) : (
              <div className="whitespace-pre-wrap text-sm leading-relaxed">
                {content}
              </div>
            )
          ) : (
            <EmptyState />
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <FileText className="mb-3 h-10 w-10 text-muted-foreground/50" />
      <p className="text-sm font-medium text-muted-foreground">
        No content available
      </p>
      <p className="mt-1 text-xs text-muted-foreground/70">
        This newsletter doesn't have text content to display.
      </p>
    </div>
  )
}
