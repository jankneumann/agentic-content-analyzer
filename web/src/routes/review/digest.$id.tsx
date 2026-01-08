/**
 * Digest Review Page
 *
 * Side-by-side view for reviewing a digest against its source summaries.
 * Left pane shows collapsible list of source summaries.
 * Right pane shows the structured digest content.
 *
 * Route: /review/digest/:id
 */

import * as React from "react"
import { createRoute, useNavigate } from "@tanstack/react-router"
import { AlertCircle, Loader2 } from "lucide-react"

import { ReviewRoute } from "../review"
import {
  ReviewLayout,
  ReviewHeader,
  SummariesListPane,
  DigestPane,
  SelectionPopover,
} from "@/components/review"
import { RevisionChatPanel } from "@/components/chat"
import type { DigestSourceSummary } from "@/lib/api/digests"
import { ReviewProvider, useReviewContext } from "@/contexts/ReviewContext"
import { useDigest, useDigestSources, useDigestNavigation } from "@/hooks/use-digests"
import { useTextSelection } from "@/hooks/use-text-selection"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import type { NavigationInfo } from "@/types/review"
import type { DigestDetail, ChatMessage } from "@/types"

/**
 * Route definition for digest review page
 */
export const DigestReviewRoute = createRoute({
  getParentRoute: () => ReviewRoute,
  path: "digest/$id",
  component: DigestReviewPage,
})

/**
 * Digest Review Page Component
 */
function DigestReviewPage() {
  const { id } = DigestReviewRoute.useParams()
  const digestId = parseInt(id, 10)
  const navigate = useNavigate()

  const {
    data: digest,
    isLoading,
    isError,
    error,
  } = useDigest(digestId)

  // Fetch source summaries
  const {
    data: sources,
    isLoading: isLoadingSources,
  } = useDigestSources(digestId)

  // Fetch navigation info
  const {
    data: navInfo,
    isLoading: isNavLoading,
  } = useDigestNavigation(digestId)

  // Transform backend navigation
  const navigation: NavigationInfo | undefined = navInfo
    ? {
        prevId: navInfo.prev_id,
        nextId: navInfo.next_id,
        position: navInfo.position,
        total: navInfo.total,
      }
    : undefined

  // Navigation handlers
  const handlePrevious = React.useCallback(() => {
    if (navInfo?.prev_id) {
      navigate({ to: "/review/digest/$id", params: { id: navInfo.prev_id.toString() } })
    }
  }, [navInfo?.prev_id, navigate])

  const handleNext = React.useCallback(() => {
    if (navInfo?.next_id) {
      navigate({ to: "/review/digest/$id", params: { id: navInfo.next_id.toString() } })
    }
  }, [navInfo?.next_id, navigate])

  // Loading state
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading review...</p>
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
          <AlertTitle>Error loading digest</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : "Failed to load the digest."}
          </AlertDescription>
          <div className="mt-4">
            <Button variant="outline" size="sm" onClick={() => navigate({ to: "/digests" })}>
              Back to Digests
            </Button>
          </div>
        </Alert>
      </div>
    )
  }

  // No digest state
  if (!digest) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <Alert className="max-w-md">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Digest not found</AlertTitle>
          <AlertDescription>
            The requested digest could not be found.
          </AlertDescription>
          <div className="mt-4">
            <Button variant="outline" size="sm" onClick={() => navigate({ to: "/digests" })}>
              Back to Digests
            </Button>
          </div>
        </Alert>
      </div>
    )
  }

  return (
    <ReviewProvider>
      <DigestReviewContent
        digest={digest}
        sources={sources}
        isLoadingSources={isLoadingSources}
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
 */
interface DigestReviewContentProps {
  digest: DigestDetail
  sources: DigestSourceSummary[] | undefined
  isLoadingSources: boolean
  navigation: NavigationInfo | undefined
  isNavLoading: boolean
  onPrevious: () => void
  onNext: () => void
}

function DigestReviewContent({
  digest,
  sources,
  isLoadingSources,
  navigation,
  isNavLoading,
  onPrevious,
  onNext,
}: DigestReviewContentProps) {
  const containerRef = React.useRef<HTMLDivElement>(null)

  // Panel expansion state
  const [isPanelExpanded, setIsPanelExpanded] = React.useState(true)

  // Chat messages (local state)
  const [messages, setMessages] = React.useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = React.useState(false)
  const [isGenerating, setIsGenerating] = React.useState(false)
  const [chatError, setChatError] = React.useState<Error | null>(null)

  // Text selection hook
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
  const handleSendMessage = React.useCallback(async (
    content: string,
    options?: { enableWebSearch?: boolean }
  ) => {
    // Add user message
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMessage])

    setIsStreaming(true)
    setChatError(null)

    // TODO: Integrate with actual chat API for questions
    // For now, simulate a response about the content
    setTimeout(() => {
      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: options?.enableWebSearch
          ? "I searched the web and found relevant information. Chat integration with web search is coming soon - for now, use the 'Generate Preview' button to create revisions based on your feedback."
          : "I understand your question about the digest. Chat integration for Q&A is coming soon - for now, use the 'Generate Preview' button to create revisions based on your feedback.",
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, assistantMessage])
      setIsStreaming(false)
    }, 1000)
  }, [])

  // Handle generating a preview (explicit button click)
  const handleGeneratePreview = React.useCallback(async () => {
    setIsGenerating(true)
    setChatError(null)

    // TODO: Implement actual digest regeneration
    // For now, show placeholder response
    setTimeout(() => {
      setIsGenerating(false)

      toast.info("Digest regeneration coming soon", {
        description: "This feature is under development.",
      })
    }, 1000)
  }, [])

  return (
    <div ref={containerRef} className="flex h-full flex-col">
      {/* Main content area */}
      <div className="flex-1 overflow-hidden">
        <ReviewLayout
          header={
            <ReviewHeader
              title="Review Digest"
              backLabel="Back to Digests"
              backTo="/digests"
              navigation={navigation}
              isNavigationLoading={isNavLoading}
              onPrevious={onPrevious}
              onNext={onNext}
            />
          }
          leftPane={
            <SummariesListPane
              summaries={sources}
              isLoading={isLoadingSources}
            />
          }
          rightPane={<DigestPane digest={digest} />}
        />
      </div>

      {/* Unified AI Revision Panel */}
      <div className="shrink-0 border-t bg-background px-4 py-3">
        <RevisionChatPanel
          messages={messages}
          isLoading={false}
          isStreaming={isStreaming}
          error={chatError}
          onSendMessage={handleSendMessage}
          onGeneratePreview={handleGeneratePreview}
          isGenerating={isGenerating}
          artifactType="digest"
          isExpanded={isPanelExpanded}
          onToggle={() => setIsPanelExpanded(!isPanelExpanded)}
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
