/**
 * Script Review Page
 *
 * Side-by-side view for reviewing a podcast script against its source digest.
 * Left pane shows the source digest content.
 * Right pane shows the script with dialogue sections.
 *
 * Route: /review/script/:id
 */

import * as React from "react"
import { createRoute, useNavigate } from "@tanstack/react-router"
import { AlertCircle, Loader2 } from "lucide-react"

import { ReviewRoute } from "../review"
import {
  ReviewLayout,
  ReviewHeader,
  DigestPane,
  ScriptPane,
  SelectionPopover,
} from "@/components/review"
import { RevisionChatPanel } from "@/components/chat"
import { ReviewProvider, useReviewContext } from "@/contexts/ReviewContext"
import { useScript, useScriptNavigation } from "@/hooks/use-scripts"
import { useDigest } from "@/hooks/use-digests"
import { useChatConfig } from "@/hooks/use-chat"
import { useTextSelection } from "@/hooks/use-text-selection"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import type { NavigationInfo, ScriptDetail } from "@/types/review"
import type { DigestDetail, ChatMessage } from "@/types"

/**
 * Route definition for script review page
 */
export const ScriptReviewRoute = createRoute({
  getParentRoute: () => ReviewRoute,
  path: "script/$id",
  component: ScriptReviewPage,
})

/**
 * Script Review Page Component
 */
function ScriptReviewPage() {
  const { id } = ScriptReviewRoute.useParams()
  const scriptId = parseInt(id, 10)
  const navigate = useNavigate()

  const {
    data: script,
    isLoading,
    isError,
    error,
  } = useScript(scriptId)

  // Fetch source digest
  const {
    data: digest,
    isLoading: isLoadingDigest,
  } = useDigest(script?.digest_id ?? 0, { enabled: !!script?.digest_id })

  // Fetch navigation info
  const {
    data: navInfo,
    isLoading: isNavLoading,
  } = useScriptNavigation(scriptId)

  // Transform backend navigation to match ReviewHeader props
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
      navigate({ to: "/review/script/$id", params: { id: navInfo.prev_id.toString() } })
    }
  }, [navInfo?.prev_id, navigate])

  const handleNext = React.useCallback(() => {
    if (navInfo?.next_id) {
      navigate({ to: "/review/script/$id", params: { id: navInfo.next_id.toString() } })
    }
  }, [navInfo?.next_id, navigate])

  // Loading state
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading script...</p>
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
          <AlertTitle>Error loading script</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : "Failed to load the script."}
          </AlertDescription>
          <div className="mt-4">
            <Button variant="outline" size="sm" onClick={() => navigate({ to: "/scripts" })}>
              Back to Scripts
            </Button>
          </div>
        </Alert>
      </div>
    )
  }

  // No script state
  if (!script) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <Alert className="max-w-md">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Script not found</AlertTitle>
          <AlertDescription>
            The requested script could not be found.
          </AlertDescription>
          <div className="mt-4">
            <Button variant="outline" size="sm" onClick={() => navigate({ to: "/scripts" })}>
              Back to Scripts
            </Button>
          </div>
        </Alert>
      </div>
    )
  }

  return (
    <ReviewProvider>
      <ScriptReviewContent
        script={script as ScriptDetail}
        digest={digest}
        isLoadingDigest={isLoadingDigest}
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
interface ScriptReviewContentProps {
  script: ScriptDetail
  digest: DigestDetail | undefined
  isLoadingDigest: boolean
  navigation: NavigationInfo | undefined
  isNavLoading: boolean
  onPrevious: () => void
  onNext: () => void
}

function ScriptReviewContent({
  script,
  digest,
  isLoadingDigest,
  navigation,
  isNavLoading,
  onPrevious,
  onNext,
}: ScriptReviewContentProps) {
  const containerRef = React.useRef<HTMLDivElement>(null)

  // Panel expansion state
  const [isPanelExpanded, setIsPanelExpanded] = React.useState(true)

  // Chat messages (local state)
  const [messages, setMessages] = React.useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = React.useState(false)
  const [isGenerating, setIsGenerating] = React.useState(false)
  const [chatError, setChatError] = React.useState<Error | null>(null)

  // Chat config and model selection
  const { data: chatConfig } = useChatConfig()
  const [selectedModel, setSelectedModel] = React.useState<string | undefined>()

  // Set default model when config loads
  React.useEffect(() => {
    if (chatConfig?.defaultModel && !selectedModel) {
      setSelectedModel(chatConfig.defaultModel)
    }
  }, [chatConfig?.defaultModel, selectedModel])

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
          : "I understand your question about the script. Chat integration for Q&A is coming soon - for now, use the 'Generate Preview' button to create revisions based on your feedback.",
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

    // TODO: Implement actual script regeneration
    // For now, show placeholder response
    setTimeout(() => {
      setIsGenerating(false)

      toast.info("Script regeneration coming soon", {
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
              title="Review Script"
              backLabel="Back to Scripts"
              backTo="/scripts"
              navigation={navigation}
              isNavigationLoading={isNavLoading}
              onPrevious={onPrevious}
              onNext={onNext}
            />
          }
          leftPane={
            <DigestPane
              digest={digest}
              isLoading={isLoadingDigest}
            />
          }
          rightPane={<ScriptPane script={script} />}
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
          artifactType="script"
          isExpanded={isPanelExpanded}
          onToggle={() => setIsPanelExpanded(!isPanelExpanded)}
          selectedModel={selectedModel}
          onModelChange={setSelectedModel}
          availableModels={chatConfig?.availableModels}
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
