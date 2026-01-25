/**
 * DigestPane Component
 *
 * Renders structured digest content in the review layout.
 * Displays all digest sections with collapsible subsections.
 *
 * Features:
 * - Executive overview
 * - Strategic insights (collapsible)
 * - Technical developments (collapsible)
 * - Emerging trends (collapsible)
 * - Actionable recommendations (by audience)
 * - Sources list
 */

import * as React from "react"
import { ChevronDown, ChevronRight, FileQuestion, Users, Lightbulb, Cpu, TrendingUp, Target, BookOpen, Loader2 } from "lucide-react"
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
import type { DigestDetail, DigestSection } from "@/types"

interface DigestPaneProps {
  digest: DigestDetail | null | undefined
  isPreview?: boolean
  isLoading?: boolean
  className?: string
}

export function DigestPane({ digest, isPreview = false, isLoading = false, className }: DigestPaneProps) {
  if (isLoading) {
    return (
      <div className={cn("flex h-full flex-col", className)}>
        <ReviewPaneHeader title="Digest" />
        <div className="flex flex-1 items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Loading digest...</p>
          </div>
        </div>
      </div>
    )
  }

  if (!digest) {
    return (
      <div className={cn("flex h-full flex-col", className)}>
        <ReviewPaneHeader title="Digest" />
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
      data-pane-label="Digest"
    >
      <ReviewPaneHeader
        title={isPreview ? "Preview" : "Digest"}
        subtitle={`${digest.digest_type} | ${digest.content_count} content items`}
        actions={
          isPreview ? (
            <Badge variant="secondary" className="text-xs">
              Preview
            </Badge>
          ) : null
        }
      />

      <ScrollArea className="flex-1">
        <div className="space-y-6 p-4">
          {/* Digest Title */}
          <div>
            <h2 className="text-lg font-semibold leading-tight">{digest.title}</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              {new Date(digest.period_start).toLocaleDateString()} - {new Date(digest.period_end).toLocaleDateString()}
            </p>
          </div>

          {/* Executive Overview */}
          <DigestSectionWrapper title="Executive Overview" icon={<BookOpen className="h-3.5 w-3.5" />}>
            <p className="text-sm leading-relaxed">{digest.executive_overview}</p>
          </DigestSectionWrapper>

          {/* Strategic Insights */}
          {digest.strategic_insights.length > 0 && (
            <DigestSectionWrapper
              title="Strategic Insights"
              icon={<Lightbulb className="h-3.5 w-3.5" />}
              count={digest.strategic_insights.length}
            >
              <CollapsibleSectionList sections={digest.strategic_insights} />
            </DigestSectionWrapper>
          )}

          {/* Technical Developments */}
          {digest.technical_developments.length > 0 && (
            <DigestSectionWrapper
              title="Technical Developments"
              icon={<Cpu className="h-3.5 w-3.5" />}
              count={digest.technical_developments.length}
            >
              <CollapsibleSectionList sections={digest.technical_developments} />
            </DigestSectionWrapper>
          )}

          {/* Emerging Trends */}
          {digest.emerging_trends.length > 0 && (
            <DigestSectionWrapper
              title="Emerging Trends"
              icon={<TrendingUp className="h-3.5 w-3.5" />}
              count={digest.emerging_trends.length}
            >
              <CollapsibleSectionList sections={digest.emerging_trends} />
            </DigestSectionWrapper>
          )}

          {/* Actionable Recommendations */}
          {digest.actionable_recommendations && Object.keys(digest.actionable_recommendations).length > 0 && (
            <DigestSectionWrapper
              title="Actionable Recommendations"
              icon={<Target className="h-3.5 w-3.5" />}
            >
              <RecommendationsList recommendations={digest.actionable_recommendations} />
            </DigestSectionWrapper>
          )}

          {/* Sources */}
          {digest.sources.length > 0 && (
            <DigestSectionWrapper
              title="Sources"
              icon={<BookOpen className="h-3.5 w-3.5" />}
              count={digest.sources.length}
            >
              <SourcesList sources={digest.sources} />
            </DigestSectionWrapper>
          )}

          {/* Metadata */}
          <div className="border-t pt-4 text-xs text-muted-foreground">
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              <span>Model: {digest.model_used}</span>
              <span>Status: {digest.status}</span>
              {digest.revision_count > 0 && <span>Revisions: {digest.revision_count}</span>}
              {digest.reviewed_by && <span>Reviewed by: {digest.reviewed_by}</span>}
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  )
}

interface DigestSectionWrapperProps {
  title: string
  icon?: React.ReactNode
  count?: number
  children: React.ReactNode
}

function DigestSectionWrapper({ title, icon, count, children }: DigestSectionWrapperProps) {
  return (
    <section>
      <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
        {icon}
        {title}
        {count !== undefined && (
          <Badge variant="outline" className="ml-1 text-xs">
            {count}
          </Badge>
        )}
      </h3>
      {children}
    </section>
  )
}

interface CollapsibleSectionListProps {
  sections: DigestSection[]
}

function CollapsibleSectionList({ sections }: CollapsibleSectionListProps) {
  return (
    <div className="space-y-2">
      {sections.map((section, index) => (
        <CollapsibleSection key={index} section={section} defaultOpen={index === 0} />
      ))}
    </div>
  )
}

interface CollapsibleSectionProps {
  section: DigestSection
  defaultOpen?: boolean
}

function CollapsibleSection({ section, defaultOpen = false }: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen)

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2 font-medium"
        >
          {isOpen ? (
            <ChevronDown className="h-4 w-4 shrink-0" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0" />
          )}
          <span className="truncate text-left">{section.title}</span>
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="ml-6 space-y-3 border-l pl-4 pt-2">
          {/* Summary */}
          <p className="text-sm leading-relaxed">{section.summary}</p>

          {/* Details */}
          {section.details.length > 0 && (
            <ul className="list-inside list-disc space-y-1 text-sm">
              {section.details.map((detail, idx) => (
                <li key={idx} className="leading-relaxed">
                  {detail}
                </li>
              ))}
            </ul>
          )}

          {/* Themes */}
          {section.themes.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {section.themes.map((theme, idx) => (
                <Badge key={idx} variant="secondary" className="text-xs">
                  {theme}
                </Badge>
              ))}
            </div>
          )}

          {/* Continuity */}
          {section.continuity && (
            <div className="rounded-md bg-muted/50 p-2 text-xs italic">
              <span className="font-medium">Historical Context: </span>
              {section.continuity}
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

interface RecommendationsListProps {
  recommendations: Record<string, string[] | undefined>
}

function RecommendationsList({ recommendations }: RecommendationsListProps) {
  const audienceLabels: Record<string, { label: string; icon: React.ReactNode }> = {
    for_leadership: { label: "For Leadership", icon: <Users className="h-3 w-3" /> },
    for_teams: { label: "For Teams", icon: <Users className="h-3 w-3" /> },
    for_individuals: { label: "For Individuals", icon: <Users className="h-3 w-3" /> },
  }

  return (
    <div className="space-y-3">
      {Object.entries(recommendations).map(([audience, items]) => {
        if (!items || items.length === 0) return null
        const config = audienceLabels[audience] || { label: audience.replace(/_/g, " "), icon: <Users className="h-3 w-3" /> }

        return (
          <div key={audience}>
            <h4 className="mb-1.5 flex items-center gap-1.5 text-xs font-medium uppercase text-muted-foreground">
              {config.icon}
              {config.label}
            </h4>
            <ul className="list-inside list-disc space-y-1 text-sm">
              {items.map((item, idx) => (
                <li key={idx} className="leading-relaxed">
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )
      })}
    </div>
  )
}

interface SourcesListProps {
  sources: Array<{
    title: string
    publication: string | null
    date: string
    url?: string | null
  }>
}

function SourcesList({ sources }: SourcesListProps) {
  return (
    <ul className="space-y-2 text-sm">
      {sources.map((source, idx) => (
        <li key={idx} className="flex items-start gap-2">
          <span className="text-muted-foreground">{idx + 1}.</span>
          <div>
            <span className="font-medium">{source.title}</span>
            {source.publication && (
              <span className="text-muted-foreground"> — {source.publication}</span>
            )}
            <span className="ml-1 text-xs text-muted-foreground">
              ({new Date(source.date).toLocaleDateString()})
            </span>
          </div>
        </li>
      ))}
    </ul>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <FileQuestion className="mb-3 h-10 w-10 text-muted-foreground/50" />
      <p className="text-sm font-medium text-muted-foreground">No digest available</p>
      <p className="mt-1 text-xs text-muted-foreground/70">
        Generate a digest to see it here.
      </p>
    </div>
  )
}
