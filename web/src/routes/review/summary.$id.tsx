/**
 * Summary Review Page
 *
 * Side-by-side view for reviewing a summary against its source newsletter.
 * Supports text selection for context and feedback submission.
 *
 * Route: /review/summary/:id (where id is the newsletter ID)
 */

import * as React from "react"
import { createRoute, useNavigate } from "@tanstack/react-router"
import { useQueryClient } from "@tanstack/react-query"
import { AlertCircle, Loader2 } from "lucide-react"

import { ReviewRoute } from "../review"
import {
  ReviewLayout,
  ReviewHeader,
  NewsletterPane,
  SummaryPane,
  SummaryPreview,
  SelectionPopover,
  FeedbackPanel,
} from "@/components/review"
import { ReviewProvider, useReviewContext } from "@/contexts/ReviewContext"
import { useNewsletterWithSummary } from "@/hooks/use-newsletters"
import { useSummaryNavigation } from "@/hooks/use-summaries"
import { useTextSelection } from "@/hooks/use-text-selection"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import {
  regenerateSummaryWithFeedback,
  commitSummaryPreview,
  type SummaryPreviewData,
} from "@/lib/api/summaries"
import type { NavigationInfo } from "@/types/review"
import type { Newsletter, NewsletterSummary } from "@/types"

/**
 * Route definition for summary review page
 */
export const SummaryReviewRoute = createRoute({
  getParentRoute: () => ReviewRoute,
  path: "summary/$id",
  component: SummaryReviewPage,
})

/**
 * Summary Review Page Component
 */
function SummaryReviewPage() {
  const { id } = SummaryReviewRoute.useParams()
  const navigate = useNavigate()

  const {
    data: newsletterWithSummary,
    isLoading,
    isError,
    error,
  } = useNewsletterWithSummary(id)

  // Get summary ID for navigation (once summary is loaded)
  const summaryId = newsletterWithSummary?.summary?.id?.toString()

  // Fetch navigation info using the summary ID
  const {
    data: navInfo,
    isLoading: isNavLoading,
  } = useSummaryNavigation(summaryId || "", {
    // No filters for now - could pass from URL search params later
  })

  // Transform backend navigation to match ReviewHeader props
  const navigation: NavigationInfo | undefined = navInfo
    ? {
        prevId: navInfo.prev_id,
        nextId: navInfo.next_id,
        position: navInfo.position,
        total: navInfo.total,
      }
    : undefined

  // Navigation handlers - use newsletter IDs since route is based on newsletter ID
  const handlePrevious = React.useCallback(() => {
    if (navInfo?.prev_newsletter_id) {
      navigate({ to: "/review/summary/$id", params: { id: navInfo.prev_newsletter_id.toString() } })
    }
  }, [navInfo?.prev_newsletter_id, navigate])

  const handleNext = React.useCallback(() => {
    if (navInfo?.next_newsletter_id) {
      navigate({ to: "/review/summary/$id", params: { id: navInfo.next_newsletter_id.toString() } })
    }
  }, [navInfo?.next_newsletter_id, navigate])

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
          <AlertTitle>Error loading content</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : "Failed to load the newsletter and summary."}
          </AlertDescription>
          <div className="mt-4">
            <Button variant="outline" size="sm" onClick={() => navigate({ to: "/summaries" })}>
              Back to Summaries
            </Button>
          </div>
        </Alert>
      </div>
    )
  }

  const newsletter = newsletterWithSummary
  const summary = newsletterWithSummary?.summary

  // No summary state
  if (!summary) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <Alert className="max-w-md">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>No summary available</AlertTitle>
          <AlertDescription>
            This newsletter hasn't been summarized yet. Generate a summary first to review it.
          </AlertDescription>
          <div className="mt-4 flex gap-2">
            <Button variant="outline" size="sm" onClick={() => navigate({ to: "/summaries" })}>
              Back to Summaries
            </Button>
            <Button size="sm" onClick={() => navigate({ to: "/newsletters" })}>
              Go to Newsletters
            </Button>
          </div>
        </Alert>
      </div>
    )
  }

  return (
    <ReviewProvider>
      <ReviewContent
        newsletter={newsletter}
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
  newsletter: Newsletter | undefined
  summary: NewsletterSummary
  navigation: NavigationInfo | undefined
  isNavLoading: boolean
  onPrevious: () => void
  onNext: () => void
}

function ReviewContent({
  newsletter,
  summary,
  navigation,
  isNavLoading,
  onPrevious,
  onNext,
}: ReviewContentProps) {
  const containerRef = React.useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  // Preview state
  const [previewData, setPreviewData] = React.useState<SummaryPreviewData | null>(null)
  const [isGenerating, setIsGenerating] = React.useState(false)
  const [isAccepting, setIsAccepting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const isPreviewMode = previewData !== null

  // Text selection hook - disabled in preview mode
  const { selection, clearSelection } = useTextSelection({
    containerRef,
    minLength: 3,
    enabled: !isPreviewMode,
  })

  // Review context for managing selections
  const {
    contextItems,
    feedback,
    addContextItem,
    clearAllContext,
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

  // Handle generate preview
  const handleGeneratePreview = React.useCallback(async () => {
    setIsGenerating(true)
    setError(null)

    try {
      const contextSelections = contextItems.map((item) => ({
        text: item.text,
        source: item.source === "left" ? "newsletter" as const : "summary" as const,
      }))

      const preview = await regenerateSummaryWithFeedback(
        summary.id.toString(),
        {
          feedback: feedback || undefined,
          contextSelections: contextSelections.length > 0 ? contextSelections : undefined,
          previewOnly: true,
        },
        (event) => {
          // Could show progress here if desired
          console.log("Progress:", event)
        }
      )

      if (preview) {
        setPreviewData(preview)
        toast.success("Preview generated", {
          description: "Review the changes and accept or reject.",
        })
      } else {
        setError("Failed to generate preview")
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to generate preview"
      setError(message)
      toast.error("Generation failed", {
        description: message,
      })
    } finally {
      setIsGenerating(false)
    }
  }, [summary.id, contextItems, feedback])

  // Handle accept preview
  const handleAcceptPreview = React.useCallback(async () => {
    if (!previewData) return

    setIsAccepting(true)
    setError(null)

    try {
      await commitSummaryPreview(summary.id.toString(), {
        executive_summary: previewData.executive_summary,
        key_themes: previewData.key_themes,
        strategic_insights: previewData.strategic_insights,
        technical_details: previewData.technical_details,
        actionable_items: previewData.actionable_items,
        notable_quotes: previewData.notable_quotes,
      })

      // Invalidate queries to refresh data
      await queryClient.invalidateQueries({ queryKey: ["summaries"] })
      await queryClient.invalidateQueries({ queryKey: ["newsletter", newsletter?.id?.toString()] })

      // Reset state
      setPreviewData(null)
      clearAllContext()

      toast.success("Summary updated", {
        description: "The changes have been saved.",
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save changes"
      setError(message)
      toast.error("Save failed", {
        description: message,
      })
    } finally {
      setIsAccepting(false)
    }
  }, [summary.id, previewData, newsletter?.id, queryClient, clearAllContext])

  // Handle reject preview
  const handleRejectPreview = React.useCallback(() => {
    setPreviewData(null)
    setError(null)
    toast.info("Preview rejected", {
      description: "No changes were made.",
    })
  }, [])

  return (
    <div ref={containerRef} className="h-full">
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
        leftPane={<NewsletterPane newsletter={newsletter} />}
        rightPane={
          isPreviewMode ? (
            <SummaryPreview
              preview={previewData}
              isStreaming={isGenerating}
              originalSummary={summary}
            />
          ) : (
            <SummaryPane summary={summary} />
          )
        }
        feedbackPanel={
          <FeedbackPanel
            isPreviewMode={isPreviewMode}
            onGeneratePreview={handleGeneratePreview}
            onAcceptPreview={handleAcceptPreview}
            onRejectPreview={handleRejectPreview}
            isGenerating={isGenerating}
            isAccepting={isAccepting}
            error={error}
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
