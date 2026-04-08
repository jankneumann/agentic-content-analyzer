/**
 * SummariesListPane Component
 *
 * Renders a collapsible list of summaries in the review layout.
 * Used in digest review to show all source summaries.
 *
 * Features:
 * - Accordion-style collapsible summaries
 * - Shows full summary content when expanded
 * - Collapsible sections within each summary
 * - Supports text selection for adding to context
 */

import * as React from "react"
import {
  ChevronDown,
  ChevronRight,
  FileText,
  Loader2,
  Lightbulb,
  Cpu,
  Target,
  Quote,
  BookOpen,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { ReviewPaneHeader } from "./ReviewLayout"
import type { DigestSourceSummary } from "@/lib/api/digests"

interface SummariesListPaneProps {
  summaries: DigestSourceSummary[] | undefined
  isLoading?: boolean
  className?: string
}

// Memoized to prevent re-renders when parent layout changes (e.g. chat streaming, resizing)
export const SummariesListPane = React.memo(function SummariesListPane({
  summaries,
  isLoading = false,
  className,
}: SummariesListPaneProps) {
  if (isLoading) {
    return (
      <div className={cn("flex h-full flex-col", className)}>
        <ReviewPaneHeader title="Source Summaries" />
        <div className="flex flex-1 items-center justify-center">
          <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
        </div>
      </div>
    )
  }

  if (!summaries || summaries.length === 0) {
    return (
      <div className={cn("flex h-full flex-col", className)}>
        <ReviewPaneHeader title="Source Summaries" />
        <div className="flex flex-1 items-center justify-center">
          <EmptyState />
        </div>
      </div>
    )
  }

  return (
    <div
      className={cn("flex h-full flex-col", className)}
      data-pane-id="left"
      data-pane-label="Source Summaries"
    >
      <ReviewPaneHeader
        title="Source Summaries"
        subtitle={`${summaries.length} content items`}
      />

      <ScrollArea className="flex-1">
        <div className="space-y-2 p-4">
          {summaries.map((summary, index) => (
            <CollapsibleSummary
              key={summary.id}
              summary={summary}
              defaultOpen={index === 0}
            />
          ))}
        </div>
      </ScrollArea>
    </div>
  )
})

interface CollapsibleSummaryProps {
  summary: DigestSourceSummary
  defaultOpen?: boolean
}

const CollapsibleSummary = React.memo(function CollapsibleSummary({
  summary,
  defaultOpen = false,
}: CollapsibleSummaryProps) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen)

  const sectionCount =
    (summary.strategic_insights.length > 0 ? 1 : 0) +
    (summary.technical_details.length > 0 ? 1 : 0) +
    (summary.actionable_items.length > 0 ? 1 : 0) +
    (summary.notable_quotes.length > 0 ? 1 : 0)

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className="bg-card rounded-lg border">
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-auto w-full justify-start gap-2 p-3"
          >
            {isOpen ? (
              <ChevronDown className="text-muted-foreground h-4 w-4 shrink-0" />
            ) : (
              <ChevronRight className="text-muted-foreground h-4 w-4 shrink-0" />
            )}
            <div className="min-w-0 flex-1 text-left">
              <div className="truncate font-medium">
                <span className="text-muted-foreground font-normal">
                  [{summary.content_id}]
                </span>{" "}
                {summary.title}
              </div>
              {summary.publication && (
                <div className="text-muted-foreground truncate text-xs">
                  {summary.publication}
                </div>
              )}
            </div>
            <div className="flex shrink-0 gap-1">
              <Badge variant="outline" className="text-xs">
                {summary.key_themes.length} themes
              </Badge>
              {sectionCount > 0 && (
                <Badge variant="secondary" className="text-xs">
                  {sectionCount} sections
                </Badge>
              )}
            </div>
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="space-y-4 border-t px-4 py-3">
            {/* Executive Summary - Always visible */}
            <SummarySection
              title="Executive Summary"
              icon={<BookOpen className="h-3.5 w-3.5" />}
            >
              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                {summary.executive_summary}
              </p>
            </SummarySection>

            {/* Key Themes */}
            {summary.key_themes.length > 0 && (
              <SummarySection title="Key Themes">
                <div className="flex flex-wrap gap-1.5">
                  {summary.key_themes.map((theme, idx) => (
                    <Badge key={idx} variant="secondary" className="text-xs">
                      {theme}
                    </Badge>
                  ))}
                </div>
              </SummarySection>
            )}

            {/* Strategic Insights - Collapsible */}
            {summary.strategic_insights.length > 0 && (
              <CollapsibleSubSection
                title="Strategic Insights"
                icon={<Lightbulb className="h-3.5 w-3.5" />}
                count={summary.strategic_insights.length}
                defaultOpen
              >
                <ul className="space-y-2">
                  {summary.strategic_insights.map((insight, idx) => (
                    <li
                      key={idx}
                      className="border-muted/50 border-l-2 pl-2 text-sm leading-relaxed"
                    >
                      {insight}
                    </li>
                  ))}
                </ul>
              </CollapsibleSubSection>
            )}

            {/* Technical Details - Collapsible */}
            {summary.technical_details.length > 0 && (
              <CollapsibleSubSection
                title="Technical Details"
                icon={<Cpu className="h-3.5 w-3.5" />}
                count={summary.technical_details.length}
              >
                <ul className="space-y-2">
                  {summary.technical_details.map((detail, idx) => (
                    <li
                      key={idx}
                      className="border-muted/50 border-l-2 pl-2 text-sm leading-relaxed"
                    >
                      {detail}
                    </li>
                  ))}
                </ul>
              </CollapsibleSubSection>
            )}

            {/* Actionable Items - Collapsible */}
            {summary.actionable_items.length > 0 && (
              <CollapsibleSubSection
                title="Actionable Items"
                icon={<Target className="h-3.5 w-3.5" />}
                count={summary.actionable_items.length}
              >
                <ul className="space-y-2">
                  {summary.actionable_items.map((item, idx) => (
                    <li
                      key={idx}
                      className="border-muted/50 border-l-2 pl-2 text-sm leading-relaxed"
                    >
                      {item}
                    </li>
                  ))}
                </ul>
              </CollapsibleSubSection>
            )}

            {/* Notable Quotes - Collapsible */}
            {summary.notable_quotes.length > 0 && (
              <CollapsibleSubSection
                title="Notable Quotes"
                icon={<Quote className="h-3.5 w-3.5" />}
                count={summary.notable_quotes.length}
              >
                <ul className="space-y-2">
                  {summary.notable_quotes.map((quote, idx) => (
                    <li
                      key={idx}
                      className="border-muted-foreground/30 border-l-2 pl-3 text-sm leading-relaxed italic"
                    >
                      "{quote}"
                    </li>
                  ))}
                </ul>
              </CollapsibleSubSection>
            )}

            {/* Metadata */}
            <div className="text-muted-foreground flex items-center gap-3 border-t pt-2 text-xs">
              <span>Model: {summary.model_used}</span>
              {summary.processing_time_seconds && (
                <span>{summary.processing_time_seconds.toFixed(1)}s</span>
              )}
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  )
})

interface SummarySectionProps {
  title: string
  icon?: React.ReactNode
  children: React.ReactNode
}

const SummarySection = React.memo(function SummarySection({
  title,
  icon,
  children,
}: SummarySectionProps) {
  return (
    <div>
      <h4 className="text-muted-foreground mb-1.5 flex items-center gap-1.5 text-xs font-medium uppercase">
        {icon}
        {title}
      </h4>
      {children}
    </div>
  )
})

interface CollapsibleSubSectionProps {
  title: string
  icon?: React.ReactNode
  count?: number
  defaultOpen?: boolean
  children: React.ReactNode
}

const CollapsibleSubSection = React.memo(function CollapsibleSubSection({
  title,
  icon,
  count,
  defaultOpen = false,
  children,
}: CollapsibleSubSectionProps) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen)
  const contentId = React.useId()

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <button
          type="button"
          aria-expanded={isOpen}
          aria-controls={contentId}
          className="hover:text-foreground/80 focus-visible:ring-ring flex w-full items-center gap-1.5 rounded-sm text-left focus-visible:ring-2 focus-visible:outline-none"
        >
          {isOpen ? (
            <ChevronDown className="text-muted-foreground h-3 w-3 shrink-0" />
          ) : (
            <ChevronRight className="text-muted-foreground h-3 w-3 shrink-0" />
          )}
          <span className="text-muted-foreground flex items-center gap-1.5 text-xs font-medium uppercase">
            {icon}
            {title}
          </span>
          {count !== undefined && (
            <Badge variant="outline" className="ml-1 text-xs">
              {count}
            </Badge>
          )}
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent id={contentId}>
        <div className="mt-2 ml-4">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  )
})

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <FileText className="text-muted-foreground/50 mb-3 h-10 w-10" />
      <p className="text-muted-foreground text-sm font-medium">
        No source summaries
      </p>
      <p className="text-muted-foreground/70 mt-1 text-xs">
        No summaries found for this digest period.
      </p>
    </div>
  )
}
