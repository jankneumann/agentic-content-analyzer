/**
 * SummaryPane Component
 *
 * Renders structured summary content in the review layout.
 * Displays all summary sections with collapsible formatting.
 *
 * Features:
 * - Executive summary (always visible)
 * - Collapsible sections for insights, details, items, quotes
 * - Key themes as badges
 * - Model info in header
 * - Empty state handling
 */

import * as React from "react"
import { ChevronDown, ChevronRight, FileQuestion, Quote, Lightbulb, Cpu, Target, BookOpen } from "lucide-react"
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
import type { NewsletterSummary } from "@/types"

interface SummaryPaneProps {
  summary: NewsletterSummary | null | undefined
  isPreview?: boolean
  className?: string
}

export function SummaryPane({ summary, isPreview = false, className }: SummaryPaneProps) {
  if (!summary) {
    return (
      <div className={cn("flex h-full flex-col", className)}>
        <ReviewPaneHeader title="Summary" />
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
      data-pane-label="Summary"
    >
      <ReviewPaneHeader
        title={isPreview ? "Preview" : `Summary [${summary.id}]`}
        subtitle={`Content [${summary.content_id}] • Model: ${summary.model_used}`}
        actions={
          isPreview ? (
            <Badge variant="secondary" className="text-xs">
              Preview
            </Badge>
          ) : null
        }
      />

      <ScrollArea className="flex-1">
        <div className="space-y-4 p-4">
          {/* Executive Summary - Always visible */}
          <SectionWrapper
            title="Executive Summary"
            icon={<BookOpen className="h-3.5 w-3.5" />}
          >
            <p className="text-sm leading-relaxed">{summary.executive_summary}</p>
          </SectionWrapper>

          {/* Key Themes - Always visible */}
          {summary.key_themes.length > 0 && (
            <SectionWrapper title="Key Themes">
              <div className="flex flex-wrap gap-2">
                {summary.key_themes.map((theme, index) => (
                  <Badge key={index} variant="outline" className="text-xs">
                    {theme}
                  </Badge>
                ))}
              </div>
            </SectionWrapper>
          )}

          {/* Strategic Insights - Collapsible */}
          {summary.strategic_insights.length > 0 && (
            <CollapsibleSection
              title="Strategic Insights"
              icon={<Lightbulb className="h-3.5 w-3.5" />}
              count={summary.strategic_insights.length}
              defaultOpen
            >
              <ul className="space-y-2">
                {summary.strategic_insights.map((insight, index) => (
                  <CollapsibleListItem key={index} content={insight} index={index} />
                ))}
              </ul>
            </CollapsibleSection>
          )}

          {/* Technical Details - Collapsible */}
          {summary.technical_details.length > 0 && (
            <CollapsibleSection
              title="Technical Details"
              icon={<Cpu className="h-3.5 w-3.5" />}
              count={summary.technical_details.length}
              defaultOpen
            >
              <ul className="space-y-2">
                {summary.technical_details.map((detail, index) => (
                  <CollapsibleListItem key={index} content={detail} index={index} />
                ))}
              </ul>
            </CollapsibleSection>
          )}

          {/* Actionable Items - Collapsible */}
          {summary.actionable_items.length > 0 && (
            <CollapsibleSection
              title="Actionable Items"
              icon={<Target className="h-3.5 w-3.5" />}
              count={summary.actionable_items.length}
              defaultOpen
            >
              <ul className="space-y-2">
                {summary.actionable_items.map((item, index) => (
                  <CollapsibleListItem key={index} content={item} index={index} />
                ))}
              </ul>
            </CollapsibleSection>
          )}

          {/* Notable Quotes - Collapsible */}
          {summary.notable_quotes.length > 0 && (
            <CollapsibleSection
              title="Notable Quotes"
              icon={<Quote className="h-3.5 w-3.5" />}
              count={summary.notable_quotes.length}
            >
              <ul className="space-y-3">
                {summary.notable_quotes.map((quote, index) => (
                  <li
                    key={index}
                    className="border-l-2 border-muted-foreground/30 pl-3 text-sm italic leading-relaxed"
                  >
                    "{quote}"
                  </li>
                ))}
              </ul>
            </CollapsibleSection>
          )}

          {/* Relevance Scores */}
          {summary.relevance_scores && (
            <SectionWrapper title="Relevance">
              <div className="flex flex-wrap gap-3 text-xs">
                <RelevanceScore
                  label="Leadership"
                  score={summary.relevance_scores.cto_leadership}
                />
                <RelevanceScore
                  label="Technical Teams"
                  score={summary.relevance_scores.technical_teams}
                />
                <RelevanceScore
                  label="Developers"
                  score={summary.relevance_scores.individual_developers}
                />
              </div>
            </SectionWrapper>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

interface SectionWrapperProps {
  title: string
  icon?: React.ReactNode
  children: React.ReactNode
}

function SectionWrapper({ title, icon, children }: SectionWrapperProps) {
  return (
    <section>
      <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
        {icon}
        {title}
      </h3>
      {children}
    </section>
  )
}

interface CollapsibleSectionProps {
  title: string
  icon?: React.ReactNode
  count?: number
  defaultOpen?: boolean
  children: React.ReactNode
}

function CollapsibleSection({
  title,
  icon,
  count,
  defaultOpen = false,
  children,
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen)

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2 px-0 hover:bg-transparent"
        >
          {isOpen ? (
            <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
          )}
          <span className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
            {icon}
            {title}
          </span>
          {count !== undefined && (
            <Badge variant="outline" className="ml-1 text-xs">
              {count}
            </Badge>
          )}
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="ml-6 pt-2">
          {children}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

interface CollapsibleListItemProps {
  content: string
  index: number
}

function CollapsibleListItem({ content, index: _index }: CollapsibleListItemProps) {
  const [isOpen, setIsOpen] = React.useState(false)

  // Truncate content for preview (first 100 chars)
  const isLong = content.length > 100
  const preview = isLong ? content.slice(0, 100) + "..." : content

  if (!isLong) {
    return (
      <li className="text-sm leading-relaxed pl-2 border-l-2 border-muted/50">
        {content}
      </li>
    )
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <li className="border-l-2 border-muted/50 pl-2">
        <CollapsibleTrigger asChild>
          <button className="w-full text-left text-sm leading-relaxed hover:text-foreground/80">
            <span>{isOpen ? content : preview}</span>
            <span className="ml-1 text-xs text-muted-foreground">
              {isOpen ? "(less)" : "(more)"}
            </span>
          </button>
        </CollapsibleTrigger>
      </li>
    </Collapsible>
  )
}

interface RelevanceScoreProps {
  label: string
  score: number
}

function RelevanceScore({ label, score }: RelevanceScoreProps) {
  // Convert 0-1 score to percentage
  const percentage = Math.round(score * 100)

  // Color based on score
  const colorClass =
    score >= 0.7
      ? "bg-green-500/20 text-green-700 dark:text-green-400"
      : score >= 0.4
        ? "bg-yellow-500/20 text-yellow-700 dark:text-yellow-400"
        : "bg-muted text-muted-foreground"

  return (
    <div className={cn("rounded-md px-2 py-1", colorClass)}>
      <span className="font-medium">{label}:</span> {percentage}%
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <FileQuestion className="mb-3 h-10 w-10 text-muted-foreground/50" />
      <p className="text-sm font-medium text-muted-foreground">No summary available</p>
      <p className="mt-1 text-xs text-muted-foreground/70">
        Generate a summary to see it here.
      </p>
    </div>
  )
}
