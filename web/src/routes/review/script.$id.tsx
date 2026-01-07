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
  FeedbackPanel,
} from "@/components/review"
import { ReviewProvider, useReviewContext } from "@/contexts/ReviewContext"
import { useScript, useScriptNavigation } from "@/hooks/use-scripts"
import { useDigest } from "@/hooks/use-digests"
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

  // Preview state (for future regeneration support)
  const [_isGenerating, _setIsGenerating] = React.useState(false)
  const [_isAccepting, _setIsAccepting] = React.useState(false)
  const [_error, _setError] = React.useState<string | null>(null)

  // Text selection hook
  const { selection, clearSelection } = useTextSelection({
    containerRef,
    minLength: 3,
    enabled: true,
  })

  // Review context for managing selections
  const {
    contextItems: _contextItems,
    feedback: _feedback,
    addContextItem,
    clearAllContext: _clearAllContext,
  } = useReviewContext()

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

  // Placeholder handlers for future regeneration support
  const handleGeneratePreview = React.useCallback(async () => {
    toast.info("Script regeneration coming soon", {
      description: "This feature is under development.",
    })
  }, [])

  const handleAcceptPreview = React.useCallback(async () => {
    // Will be implemented when regeneration is added
  }, [])

  const handleRejectPreview = React.useCallback(() => {
    // Will be implemented when regeneration is added
  }, [])

  return (
    <div ref={containerRef} className="h-full">
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
        feedbackPanel={
          <FeedbackPanel
            isPreviewMode={false}
            onGeneratePreview={handleGeneratePreview}
            onAcceptPreview={handleAcceptPreview}
            onRejectPreview={handleRejectPreview}
            isGenerating={_isGenerating}
            isAccepting={_isAccepting}
            error={_error}
          />
        }
      />

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
