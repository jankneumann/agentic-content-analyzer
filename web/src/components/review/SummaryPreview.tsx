/**
 * SummaryPreview Component
 *
 * Displays a preview of regenerated summary content.
 * Shows the same structure as SummaryPane but with preview styling.
 *
 * Features:
 * - Preview badge indicator
 * - Same section structure as SummaryPane
 * - Streaming content support (partial updates)
 * - Diff highlighting (future enhancement)
 */

import { FileQuestion, Quote, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { ReviewPaneHeader } from "./ReviewLayout"
import type { Summary } from "@/types"

interface SummaryPreviewProps {
  /** Preview content (may be partial during streaming) */
  preview: Partial<Summary> | null
  /** Whether content is still streaming */
  isStreaming?: boolean
  /** Original summary for comparison (for future diff highlighting) */
  originalSummary?: Summary
  className?: string
}

export function SummaryPreview({
  preview,
  isStreaming = false,
  originalSummary: _originalSummary,
  className,
}: SummaryPreviewProps) {
  if (!preview && !isStreaming) {
    return (
      <div className={cn("flex h-full flex-col", className)}>
        <ReviewPaneHeader
          title="Preview"
          actions={
            <Badge variant="secondary" className="text-xs">
              Preview
            </Badge>
          }
        />
        <div className="flex flex-1 items-center justify-center">
          <EmptyState />
        </div>
      </div>
    )
  }

  return (
    <div
      className={cn("flex h-full flex-col", className)}
      data-pane-id="right"
      data-pane-label="Preview"
    >
      <ReviewPaneHeader
        title="Preview"
        subtitle={preview?.model_used ? `Model: ${preview.model_used}` : undefined}
        actions={
          <div className="flex items-center gap-2">
            {isStreaming && (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" />
                Generating...
              </div>
            )}
            <Badge
              variant="secondary"
              className={cn(
                "text-xs",
                isStreaming && "animate-pulse bg-blue-500/20 text-blue-700 dark:text-blue-400"
              )}
            >
              Preview
            </Badge>
          </div>
        }
      />

      <ScrollArea className="flex-1">
        <div className="space-y-6 p-4">
          {/* Executive Summary */}
          {preview?.executive_summary && (
            <PreviewSection title="Executive Summary">
              <p className="text-sm leading-relaxed">{preview.executive_summary}</p>
            </PreviewSection>
          )}

          {/* Key Themes */}
          {preview?.key_themes && preview.key_themes.length > 0 && (
            <PreviewSection title="Key Themes">
              <div className="flex flex-wrap gap-2">
                {preview.key_themes.map((theme, index) => (
                  <Badge key={index} variant="outline" className="text-xs">
                    {theme}
                  </Badge>
                ))}
              </div>
            </PreviewSection>
          )}

          {/* Strategic Insights */}
          {preview?.strategic_insights && preview.strategic_insights.length > 0 && (
            <PreviewSection title="Strategic Insights">
              <ul className="list-inside list-disc space-y-1.5 text-sm">
                {preview.strategic_insights.map((insight, index) => (
                  <li key={index} className="leading-relaxed">
                    {insight}
                  </li>
                ))}
              </ul>
            </PreviewSection>
          )}

          {/* Technical Details */}
          {preview?.technical_details && preview.technical_details.length > 0 && (
            <PreviewSection title="Technical Details">
              <ul className="list-inside list-disc space-y-1.5 text-sm">
                {preview.technical_details.map((detail, index) => (
                  <li key={index} className="leading-relaxed">
                    {detail}
                  </li>
                ))}
              </ul>
            </PreviewSection>
          )}

          {/* Actionable Items */}
          {preview?.actionable_items && preview.actionable_items.length > 0 && (
            <PreviewSection title="Actionable Items">
              <ul className="list-inside list-disc space-y-1.5 text-sm">
                {preview.actionable_items.map((item, index) => (
                  <li key={index} className="leading-relaxed">
                    {item}
                  </li>
                ))}
              </ul>
            </PreviewSection>
          )}

          {/* Notable Quotes */}
          {preview?.notable_quotes && preview.notable_quotes.length > 0 && (
            <PreviewSection
              title="Notable Quotes"
              icon={<Quote className="h-3.5 w-3.5" />}
            >
              <ul className="space-y-3">
                {preview.notable_quotes.map((quote, index) => (
                  <li
                    key={index}
                    className="border-l-2 border-muted-foreground/30 pl-3 text-sm italic leading-relaxed"
                  >
                    "{quote}"
                  </li>
                ))}
              </ul>
            </PreviewSection>
          )}

          {/* Loading placeholder for streaming */}
          {isStreaming && !preview?.executive_summary && (
            <div className="flex items-center justify-center py-12">
              <div className="flex flex-col items-center gap-3">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                <p className="text-sm text-muted-foreground">Generating preview...</p>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

interface PreviewSectionProps {
  title: string
  icon?: React.ReactNode
  children: React.ReactNode
}

function PreviewSection({ title, icon, children }: PreviewSectionProps) {
  return (
    <section className="rounded-md border border-dashed border-blue-500/30 bg-blue-500/5 p-3">
      <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
        {icon}
        {title}
      </h3>
      {children}
    </section>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <FileQuestion className="mb-3 h-10 w-10 text-muted-foreground/50" />
      <p className="text-sm font-medium text-muted-foreground">No preview</p>
      <p className="mt-1 text-xs text-muted-foreground/70">
        Generate a preview to see changes here.
      </p>
    </div>
  )
}
