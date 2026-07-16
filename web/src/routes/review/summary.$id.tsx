/**
 * Summary Review Page
 *
 * Side-by-side view for reviewing a summary against its source content.
 * Supports text selection for context and AI-powered revision through chat.
 *
 * Route: /review/summary/:id (where id is the content ID)
 */

import * as React from "react"
import { createRoute, useNavigate } from "@tanstack/react-router"
import { AlertCircle, Loader2 } from "lucide-react"
import ReactMarkdown from "react-markdown"

import { ReviewRoute } from "../review"
import {
  ReviewLayout,
  ReviewHeader,
  SummaryPane,
  SelectionPopover,
  ReviewPaneHeader,
} from "@/components/review"
import { RevisionChatPanel } from "@/components/chat"
import { ReviewProvider, useReviewContext } from "@/contexts/ReviewContext"
import { useContentWithSummary } from "@/hooks/use-contents"
import { useSummaryNavigation } from "@/hooks/use-summaries"
import { useChatConfig, useChatSession } from "@/hooks/use-chat"
import { useTextSelection } from "@/hooks/use-text-selection"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { toast } from "sonner"
import type { NavigationInfo } from "@/types/review"
import type { Summary, Content } from "@/types"

/**
 * Route definition for summary review page
 */
export const SummaryReviewRoute = createRoute({
  getParentRoute: () => ReviewRoute,
  path: "summary/$id",
  component: SummaryReviewPage,
})

/**
 * SourceContentPane - Renders unified Content model with markdown
 */
function SourceContentPane({
  content,
}: {
  content: Content | null | undefined
}) {
  const hasContent = Boolean(content?.markdown_content)

  return (
    <div
      className="flex h-full flex-col"
      data-pane-id="left"
      data-pane-label="Content"
    >
      <ReviewPaneHeader
        title="Source Content"
        subtitle={content?.publication || content?.author || undefined}
        actions={
          content?.source_type && (
            <Badge variant="outline" className="text-xs">
              {content.source_type}
            </Badge>
          )
        }
      />

      <ScrollArea className="flex-1">
        <div className="p-4">
          {content?.title && (
            <h2 className="mb-4 text-lg font-semibold">
              <span className="text-muted-foreground font-normal">
                [{content.id}]
              </span>{" "}
              {content.title}
            </h2>
          )}

          {hasContent ? (
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown>{content?.markdown_content || ""}</ReactMarkdown>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <AlertCircle className="text-muted-foreground/50 mb-3 h-10 w-10" />
              <p className="text-muted-foreground text-sm font-medium">
                No content available
              </p>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

/**
 * Summary Review Page Component
 */
function SummaryReviewPage() {
  const { id } = SummaryReviewRoute.useParams()
  const navigate = useNavigate()

  // Fetch Content with its summary
  const {
    data: contentWithSummary,
    isLoading,
    isError,
    error,
  } = useContentWithSummary(id)

  const summary = contentWithSummary?.summary

  // Get summary ID for navigation (once summary is loaded)
  const summaryId = summary?.id?.toString()

  // Fetch navigation info using the summary ID
  const { data: navInfo, isLoading: isNavLoading } = useSummaryNavigation(
    summaryId || "",
    {
      // No filters for now - could pass from URL search params later
    }
  )

  // Transform backend navigation to match ReviewHeader props
  const navigation: NavigationInfo | undefined = navInfo
    ? {
        prevId: navInfo.prev_id,
        nextId: navInfo.next_id,
        position: navInfo.position,
        total: navInfo.total,
      }
    : undefined

  // Navigation handlers - use content IDs since route is based on content ID
  const handlePrevious = React.useCallback(() => {
    if (navInfo?.prev_content_id) {
      navigate({
        to: "/review/summary/$id",
        params: { id: navInfo.prev_content_id.toString() },
      })
    }
  }, [navInfo, navigate])

  const handleNext = React.useCallback(() => {
    if (navInfo?.next_content_id) {
      navigate({
        to: "/review/summary/$id",
        params: { id: navInfo.next_content_id.toString() },
      })
    }
  }, [navInfo, navigate])

  // Loading state
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
          <p className="text-muted-foreground text-sm">Loading review...</p>
        </div>
      </div>
    )
  }

  // Error state
  if (isError) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <Alert variant="destructive" className="max-w-md">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error loading content</AlertTitle>
          <AlertDescription>
            {error instanceof Error
              ? error.message
              : "Failed to load the content and summary."}
          </AlertDescription>
          <div className="mt-4">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate({ to: "/summaries" })}
            >
              Back to Summaries
            </Button>
          </div>
        </Alert>
      </div>
    )
  }

  // No summary state
  if (!summary) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <Alert className="max-w-md">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>No summary available</AlertTitle>
          <AlertDescription>
            This content hasn't been summarized yet. Generate a summary first to
            review it.
          </AlertDescription>
          <div className="mt-4 flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate({ to: "/summaries" })}
            >
              Back to Summaries
            </Button>
            <Button size="sm" onClick={() => navigate({ to: "/contents" })}>
              Go to Contents
            </Button>
          </div>
        </Alert>
      </div>
    )
  }

  return (
    <ReviewProvider>
      <ReviewContent
        key={summary.id}
        content={contentWithSummary}
        summary={summary}
        navigation={navigation}
        isNavLoading={isNavLoading}
        onPrevious={handlePrevious}
        onNext={handleNext}
      />
    </ReviewProvider>
  )
}

/**
 * Review content with selection handling
 * Separated to use ReviewContext hooks within the provider
 */
interface ReviewContentProps {
  content: (Content & { summary: Summary | null }) | null | undefined
  summary: Summary
  navigation: NavigationInfo | undefined
  isNavLoading: boolean
  onPrevious: () => void
  onNext: () => void
}

function ReviewContent({
  content,
  summary,
  navigation,
  isNavLoading,
  onPrevious,
  onNext,
}: ReviewContentProps) {
  const containerRef = React.useRef<HTMLDivElement>(null)

  // Panel expansion state - start collapsed for cleaner initial view
  const [isPanelExpanded, setIsPanelExpanded] = React.useState(false)

  // Chat session hook - handles persistence and messaging
  const chat = useChatSession("summary", summary.id.toString())
  const { conversationId, hasConversation, startOrContinue } = chat

  // Chat config and model selection
  const { data: chatConfig } = useChatConfig()
  const [selectedModel, setSelectedModel] = React.useState<string | undefined>()
  const effectiveSelectedModel = selectedModel ?? chatConfig?.defaultModel

  // Load existing conversation on mount
  React.useEffect(() => {
    if (hasConversation && !conversationId) {
      startOrContinue()
    }
  }, [hasConversation, conversationId, startOrContinue])

  // Text selection remains available for revision chat context.
  const { selection, clearSelection } = useTextSelection({
    containerRef,
    minLength: 3,
    enabled: true,
  })

  // Review context for managing selections
  const { addContextItem } = useReviewContext()

  // Handle adding selection to context
  const handleAddToContext = React.useCallback(() => {
    if (!selection) return

    const added = addContextItem({
      text: selection.text,
      source: selection.paneId,
      paneLabel: selection.paneLabel,
    })

    if (added) {
      clearSelection()
    }
  }, [selection, addContextItem, clearSelection])

  // Handle sending a chat message (for questions, NOT regeneration)
  const handleSendMessage = React.useCallback(
    async (content: string, options?: { enableWebSearch?: boolean }) => {
      try {
        await chat.send(content, {
          enableWebSearch: options?.enableWebSearch,
          model: effectiveSelectedModel,
        })
      } catch (err) {
        const error =
          err instanceof Error ? err : new Error("Failed to send message")
        toast.error("Message failed", { description: error.message })
      }
    },
    [chat, effectiveSelectedModel]
  )

  return (
    <div ref={containerRef} className="flex h-full flex-col">
      {/* Main content area */}
      <div className="flex-1 overflow-hidden">
        <ReviewLayout
          header={
            <ReviewHeader
              title="Review Summary"
              backLabel="Back to Summaries"
              backTo="/summaries"
              navigation={navigation}
              isNavigationLoading={isNavLoading}
              onPrevious={onPrevious}
              onNext={onNext}
            />
          }
          leftPane={<SourceContentPane content={content} />}
          rightPane={<SummaryPane summary={summary} />}
        />
      </div>

      {/* Unified AI Revision Panel */}
      <div className="bg-background shrink-0 border-t px-4 py-3">
        <RevisionChatPanel
          messages={chat.messages}
          isLoading={chat.isLoading}
          isStreaming={chat.isStreaming}
          streamingContent={chat.streamingContent}
          error={chat.error}
          onSendMessage={handleSendMessage}
          artifactType="summary"
          isExpanded={isPanelExpanded}
          onToggle={() => setIsPanelExpanded(!isPanelExpanded)}
          selectedModel={effectiveSelectedModel}
          onModelChange={setSelectedModel}
          availableModels={chatConfig?.availableModels}
          conversationId={conversationId}
        />
      </div>

      {/* Selection popover */}
      {selection && (
        <SelectionPopover
          selection={selection}
          onAdd={handleAddToContext}
          onDismiss={clearSelection}
        />
      )}
    </div>
  )
}
