/**
 * ScriptPane Component
 *
 * Renders a podcast script with collapsible sections and dialogue turns.
 * Used in script review to display the generated script content.
 *
 * Features:
 * - Script metadata (title, duration, word count)
 * - Collapsible sections by type (intro, strategic, technical, trend, outro)
 * - Dialogue turns with speaker styling (ALEX/SAM)
 * - Emphasis indicators
 * - Sources cited per section
 */

import * as React from "react"
import {
  ChevronDown,
  ChevronRight,
  FileQuestion,
  Mic,
  Clock,
  FileText,
  Lightbulb,
  Cpu,
  TrendingUp,
  PlayCircle,
  StopCircle,
  User,
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
import type { ScriptDetail, ScriptSection, ScriptDialogueTurn } from "@/types/review"

interface ScriptPaneProps {
  script: ScriptDetail | null | undefined
  isPreview?: boolean
  className?: string
}

export function ScriptPane({ script, isPreview = false, className }: ScriptPaneProps) {
  if (!script) {
    return (
      <div className={cn("flex h-full flex-col", className)}>
        <ReviewPaneHeader title="Script" />
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
      data-pane-label="Script"
    >
      <ReviewPaneHeader
        title={isPreview ? "Preview" : "Podcast Script"}
        subtitle={script.title || "Untitled Script"}
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
          {/* Script Metadata */}
          <ScriptMetadata script={script} />

          {/* Sections */}
          {script.sections.map((section, index) => (
            <CollapsibleSection
              key={section.index}
              section={section}
              defaultOpen={index < 2}
            />
          ))}

          {/* Sources Summary */}
          {script.sources_summary && script.sources_summary.length > 0 && (
            <SourcesSummary sources={script.sources_summary} />
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

interface ScriptMetadataProps {
  script: ScriptDetail
}

function ScriptMetadata({ script }: ScriptMetadataProps) {
  return (
    <div className="rounded-lg border bg-card p-4 space-y-2">
      <div className="flex flex-wrap gap-3 text-sm">
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <Clock className="h-4 w-4" />
          <span>{script.estimated_duration}</span>
        </div>
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <FileText className="h-4 w-4" />
          <span>{script.word_count?.toLocaleString() || 0} words</span>
        </div>
        <Badge variant="outline" className="text-xs">
          {script.length}
        </Badge>
        <Badge
          variant={script.status === "script_approved" ? "default" : "secondary"}
          className="text-xs"
        >
          {script.status.replace(/_/g, " ")}
        </Badge>
      </div>
      {script.revision_count > 0 && (
        <div className="text-xs text-muted-foreground">
          {script.revision_count} revision{script.revision_count > 1 ? "s" : ""}
        </div>
      )}
    </div>
  )
}

interface CollapsibleSectionProps {
  section: ScriptSection
  defaultOpen?: boolean
}

function CollapsibleSection({ section, defaultOpen = false }: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen)

  const sectionIcon = getSectionIcon(section.type)
  const sectionColor = getSectionColor(section.type)

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className="rounded-lg border bg-card">
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-2 p-3 h-auto"
          >
            {isOpen ? (
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
            )}
            <div className={cn("p-1 rounded", sectionColor)}>
              {sectionIcon}
            </div>
            <div className="flex-1 text-left min-w-0">
              <div className="font-medium">{section.title}</div>
              <div className="text-xs text-muted-foreground">
                {section.type.charAt(0).toUpperCase() + section.type.slice(1)} •{" "}
                {section.word_count} words
              </div>
            </div>
            <Badge variant="outline" className="text-xs shrink-0">
              {section.dialogue.length} turns
            </Badge>
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="border-t px-4 py-3 space-y-3">
            {section.dialogue.map((turn, turnIdx) => (
              <DialogueTurnItem key={turnIdx} turn={turn} />
            ))}
            {section.sources_cited && section.sources_cited.length > 0 && (
              <div className="pt-2 border-t mt-3">
                <div className="text-xs text-muted-foreground">
                  Sources: {section.sources_cited.join(", ")}
                </div>
              </div>
            )}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  )
}

interface DialogueTurnItemProps {
  turn: ScriptDialogueTurn
}

function DialogueTurnItem({ turn }: DialogueTurnItemProps) {
  const isAlex = turn.speaker.toUpperCase() === "ALEX"

  return (
    <div
      className={cn(
        "rounded-lg p-3",
        isAlex
          ? "bg-blue-50 dark:bg-blue-950/30 border-l-2 border-blue-500"
          : "bg-purple-50 dark:bg-purple-950/30 border-l-2 border-purple-500"
      )}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <User className={cn("h-3.5 w-3.5", isAlex ? "text-blue-600" : "text-purple-600")} />
        <span
          className={cn(
            "font-semibold text-sm",
            isAlex ? "text-blue-700 dark:text-blue-400" : "text-purple-700 dark:text-purple-400"
          )}
        >
          {turn.speaker}
        </span>
        {turn.emphasis && (
          <Badge
            variant="outline"
            className={cn(
              "text-xs",
              turn.emphasis === "excited" && "border-orange-300 text-orange-700",
              turn.emphasis === "thoughtful" && "border-blue-300 text-blue-700",
              turn.emphasis === "concerned" && "border-red-300 text-red-700",
              turn.emphasis === "amused" && "border-green-300 text-green-700"
            )}
          >
            {turn.emphasis}
          </Badge>
        )}
        {turn.pause_after && turn.pause_after > 0 && (
          <span className="text-xs text-muted-foreground ml-auto">
            ⏸ {turn.pause_after}s
          </span>
        )}
      </div>
      <p className="text-sm leading-relaxed whitespace-pre-wrap">{turn.text}</p>
    </div>
  )
}

interface SourcesSummaryProps {
  sources: ScriptDetail["sources_summary"]
}

function SourcesSummary({ sources }: SourcesSummaryProps) {
  const [isOpen, setIsOpen] = React.useState(false)

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className="rounded-lg border bg-muted/30">
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-2 p-3 h-auto"
          >
            {isOpen ? (
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
            )}
            <span className="text-sm font-medium text-muted-foreground">
              Sources ({sources.length})
            </span>
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="border-t px-4 py-2 space-y-1">
            {sources.map((source, idx) => (
              <div key={idx} className="text-sm">
                <span className="font-medium">{source.title}</span>
                {source.publication && (
                  <span className="text-muted-foreground"> — {source.publication}</span>
                )}
              </div>
            ))}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  )
}

function getSectionIcon(type: ScriptSection["type"]) {
  switch (type) {
    case "intro":
      return <PlayCircle className="h-3.5 w-3.5" />
    case "strategic":
      return <Lightbulb className="h-3.5 w-3.5" />
    case "technical":
      return <Cpu className="h-3.5 w-3.5" />
    case "trend":
      return <TrendingUp className="h-3.5 w-3.5" />
    case "outro":
      return <StopCircle className="h-3.5 w-3.5" />
    default:
      return <Mic className="h-3.5 w-3.5" />
  }
}

function getSectionColor(type: ScriptSection["type"]) {
  switch (type) {
    case "intro":
      return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
    case "strategic":
      return "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
    case "technical":
      return "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400"
    case "trend":
      return "bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400"
    case "outro":
      return "bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-400"
    default:
      return "bg-muted"
  }
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <FileQuestion className="mb-3 h-10 w-10 text-muted-foreground/50" />
      <p className="text-sm font-medium text-muted-foreground">No script available</p>
      <p className="mt-1 text-xs text-muted-foreground/70">
        Generate a script to see it here.
      </p>
    </div>
  )
}
