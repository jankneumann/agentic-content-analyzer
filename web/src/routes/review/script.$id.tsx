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
import { useScript, useScriptNavigation, useRegenerateScript } from "@/hooks/use-scripts"
import { useDigest } from "@/hooks/use-digests"
import { useChatConfig, useChatSession } from "@/hooks/use-chat"
import { useTextSelection } from "@/hooks/use-text-selection"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import type { NavigationInfo, ScriptDetail } from "@/types/review"
import type { DigestDetail } from "@/types"

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
        key={script.id}
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
  script: initialScript,
  digest,
  isLoadingDigest,
  navigation,
  isNavLoading,
  onPrevious,
  onNext,
}: ScriptReviewContentProps) {
  const navigate = useNavigate()
  const containerRef = React.useRef<HTMLDivElement>(null)

  // Panel expansion state - start collapsed for cleaner initial view
  const [isPanelExpanded, setIsPanelExpanded] = React.useState(false)

  // Chat session hook - handles persistence and messaging
  const chat = useChatSession("script", initialScript.id.toString())

  // Preview state
  const [previewScriptId, setPreviewScriptId] = React.useState<number | null>(null)

  // Fetch preview script if available
  // We poll if we have a preview ID and it's in a generating/pending state
  const { data: previewScript } = useScript(previewScriptId ?? 0, {
    enabled: !!previewScriptId,
    refetchInterval: (query: { state: { data: unknown } }) => {
      const data = query.state.data as ScriptDetail | undefined
      // Poll every 2s if generating or pending
      if (
        data &&
        (data.status === "script_generating" || data.status === "pending")
      ) {
        return 2000
      }
      // Also poll if we have an ID but no data yet (initial load of preview)
      if (!data && previewScriptId) {
        return 1000
      }
      return false
    },
  })

  // Determine active script (preview or initial)
  const activeScript = (previewScript as ScriptDetail) || initialScript
  const isPreviewMode = !!previewScriptId

  // Regeneration hook
  const { mutate: regenerate, isPending: isStartingRegeneration } = useRegenerateScript()

  // Poll for preview status
  const isGenerating = isStartingRegeneration || (
    !!previewScript &&
    (previewScript.status === 'script_generating' || previewScript.status === 'pending')
  )

  // Poll handled by useScript refetchInterval

  // Chat config and model selection
  const { data: chatConfig } = useChatConfig()
  const [selectedModel, setSelectedModel] = React.useState<string | undefined>()

  // Set default model when config loads
  React.useEffect(() => {
    if (chatConfig?.defaultModel && !selectedModel) {
      setSelectedModel(chatConfig.defaultModel)
    }
  }, [chatConfig?.defaultModel, selectedModel])

  // Load existing conversation on mount
  React.useEffect(() => {
    if (chat.hasConversation && !chat.conversationId) {
      chat.startOrContinue()
    }
  }, [chat.hasConversation, chat.conversationId, chat.startOrContinue])

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
    try {
      await chat.send(content, {
        enableWebSearch: options?.enableWebSearch,
        model: selectedModel,
      })
    } catch (err) {
      const error = err instanceof Error ? err : new Error("Failed to send message")
      toast.error("Message failed", { description: error.message })
    }
  }, [chat, selectedModel])

  // Handle generating a preview (explicit button click)
  const handleGeneratePreview = React.useCallback(() => {
    if (!chat.conversationId) {
      toast.error("No conversation started", {
        description: "Please start a conversation before regenerating."
      })
      return
    }

    regenerate({
      scriptId: initialScript.id,
      conversationId: chat.conversationId,
    }, {
      onSuccess: (data) => {
        setPreviewScriptId(data.script_id)
        toast.info("Regeneration started", {
          description: "Creating a preview based on your conversation..."
        })
      },
      onError: (err) => {
        toast.error("Regeneration failed", {
          description: err instanceof Error ? err.message : "Unknown error"
        })
      }
    })
  }, [chat.conversationId, initialScript.id, regenerate])

  const handleAcceptPreview = React.useCallback(() => {
    if (previewScriptId) {
      navigate({ to: "/review/script/$id", params: { id: previewScriptId.toString() } })
      setPreviewScriptId(null)
      toast.success("Script updated", {
        description: "You are now viewing the new version."
      })
    }
  }, [previewScriptId, navigate])

  const handleRejectPreview = React.useCallback(() => {
    setPreviewScriptId(null)
    toast.info("Preview discarded", {
      description: "Returned to original script."
    })
  }, [])

  return (
    <div ref={containerRef} className="flex h-full flex-col">
      {/* Main content area */}
      <div className="flex-1 overflow-hidden">
        <ReviewLayout
          header={
            <ReviewHeader
              title={isPreviewMode ? "Review Script (Preview)" : "Review Script"}
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
          rightPane={<ScriptPane script={activeScript} />}
        />
      </div>

      {/* Unified AI Revision Panel */}
      <div className="shrink-0 border-t bg-background px-4 py-3">
        <RevisionChatPanel
          messages={chat.messages}
          isLoading={chat.isLoading}
          isStreaming={chat.isStreaming}
          streamingContent={chat.streamingContent}
          error={chat.error}
          onSendMessage={handleSendMessage}
          onGeneratePreview={handleGeneratePreview}
          isGenerating={isGenerating}
          artifactType="script"
          isExpanded={isPanelExpanded}
          onToggle={() => setIsPanelExpanded(!isPanelExpanded)}
          selectedModel={selectedModel}
          onModelChange={setSelectedModel}
          availableModels={chatConfig?.availableModels}
          conversationId={chat.conversationId}
          isPreviewMode={isPreviewMode}
          onAcceptPreview={handleAcceptPreview}
          onRejectPreview={handleRejectPreview}
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
