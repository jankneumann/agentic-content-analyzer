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
  FeedbackPanel,
} from "@/components/review"
import type { DigestSourceSummary } from "@/lib/api/digests"
import { ReviewProvider, useReviewContext } from "@/contexts/ReviewContext"
import { useDigest, useDigestSources, useDigestNavigation } from "@/hooks/use-digests"
import { useTextSelection } from "@/hooks/use-text-selection"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import type { NavigationInfo } from "@/types/review"
import type { DigestDetail } from "@/types"

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
  } = useDigestSources(digestId, { enabled: !!digest })

  // Fetch navigation info
  const {
    data: navInfo,
    isLoading: isNavLoading,
  } = useDigestNavigation(digestId)

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
          <p className="text-sm text-muted-foreground">Loading digest...</p>
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
    toast.info("Digest regeneration coming soon", {
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
