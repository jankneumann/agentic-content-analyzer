/**
 * Dashboard Page (Index Route)
 *
 * The home page of the application showing:
 * - Pipeline status overview
 * - Recent activity
 * - Quick actions
 *
 * Route: /
 */

import { createRoute, Link } from "@tanstack/react-router"
import {
  Newspaper,
  Sparkles,
  FileText,
  Radio,
  ArrowRight,
  BarChart3,
  Mic,
  Loader2,
} from "lucide-react"

import { Route as rootRoute } from "./__root"
import { PageContainer, PageSection } from "@/components/layout"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { useContentStats, useSummaryStats, useScriptStats, useDigestStats } from "@/hooks"

/**
 * Route definition for the index page
 */
export const IndexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",  // Root path must have leading slash
  component: DashboardPage,
})

/**
 * Status badge component
 */
function StatusBadge({ status }: { status: "idle" | "processing" | "error" }) {
  const variants = {
    idle: { label: "Ready", variant: "secondary" as const },
    processing: { label: "Processing", variant: "default" as const },
    error: { label: "Error", variant: "destructive" as const },
  }

  const { label, variant } = variants[status]
  return <Badge variant={variant}>{label}</Badge>
}

/**
 * Pipeline step card component
 */
function PipelineCard({
  name,
  description,
  icon: Icon,
  count,
  status,
  href,
  isLoading,
}: {
  name: string
  description: string
  icon: React.ElementType
  count: number
  status: "idle" | "processing" | "error"
  href: string
  isLoading?: boolean
}) {
  return (
    <Card className="relative overflow-hidden">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <Icon className="h-5 w-5 text-muted-foreground" />
          <StatusBadge status={status} />
        </div>
        <CardTitle className="text-base">{name}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          {isLoading ? (
            <Skeleton className="h-8 w-12" />
          ) : (
            <span className="text-2xl font-bold">{count}</span>
          )}
          <Button variant="ghost" size="sm" asChild>
            <Link to={href}>
              View
              <ArrowRight className="ml-1 h-4 w-4" />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * Dashboard page component
 */
function DashboardPage() {
  const { data: contentStats, isLoading: isLoadingContent } = useContentStats()
  const { data: summaryStats, isLoading: isLoadingSummaries } = useSummaryStats()
  const { data: scriptStats, isLoading: isLoadingScripts } = useScriptStats()
  const { data: digestStats, isLoading: isLoadingDigests } = useDigestStats()

  const isLoading = isLoadingContent || isLoadingSummaries || isLoadingScripts || isLoadingDigests

  // Calculate pending counts from content stats
  const pendingContent = contentStats?.needs_summarization_count ?? 0
  const processingContent = contentStats?.by_status?.processing ?? 0

  return (
    <PageContainer
      title="Dashboard"
      description="Overview of your newsletter aggregation pipeline"
      actions={
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link to="/contents">
              <Newspaper className="mr-2 h-4 w-4" />
              Ingest
            </Link>
          </Button>
          <Button asChild>
            <Link to="/digests">
              <Sparkles className="mr-2 h-4 w-4" />
              Generate Digest
            </Link>
          </Button>
        </div>
      }
    >
      {/* Pipeline Status */}
      <PageSection
        title="Pipeline Status"
        description="Current state of each processing step"
      >
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <PipelineCard
            name="Content"
            description="Ingested from Gmail, RSS, and YouTube"
            icon={Newspaper}
            count={contentStats?.total ?? 0}
            status={processingContent > 0 ? "processing" : "idle"}
            href="/contents"
            isLoading={isLoadingContent}
          />
          <PipelineCard
            name="Summaries"
            description="AI-generated extractions"
            icon={Sparkles}
            count={summaryStats?.total ?? 0}
            status="idle"
            href="/summaries"
            isLoading={isLoadingSummaries}
          />
          <PipelineCard
            name="Themes"
            description="Knowledge graph analysis"
            icon={BarChart3}
            count={0}
            status="idle"
            href="/themes"
          />
          <PipelineCard
            name="Digests"
            description="Aggregated reports"
            icon={FileText}
            count={digestStats?.total ?? 0}
            status={digestStats?.pending_review && digestStats.pending_review > 0 ? "processing" : "idle"}
            href="/digests"
            isLoading={isLoadingDigests}
          />
          <PipelineCard
            name="Scripts"
            description="Podcast dialogue"
            icon={Mic}
            count={scriptStats?.total ?? 0}
            status={scriptStats?.pending_review && scriptStats.pending_review > 0 ? "processing" : "idle"}
            href="/scripts"
            isLoading={isLoadingScripts}
          />
          <PipelineCard
            name="Podcasts"
            description="Generated audio"
            icon={Radio}
            count={scriptStats?.completed_with_audio ?? 0}
            status="idle"
            href="/podcasts"
            isLoading={isLoadingScripts}
          />
        </div>
      </PageSection>

      {/* Summary Stats */}
      {!isLoading && (contentStats || summaryStats || scriptStats || digestStats) && (
        <PageSection
          title="Pipeline Summary"
          description="Key metrics across your pipeline"
        >
          <div className="grid gap-4 md:grid-cols-5">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Pending Summarization</CardDescription>
                <CardTitle className="text-2xl">{pendingContent}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Summaries Generated</CardDescription>
                <CardTitle className="text-2xl">{summaryStats?.total ?? 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Digests Pending Review</CardDescription>
                <CardTitle className="text-2xl">{digestStats?.pending_review ?? 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Scripts Pending Review</CardDescription>
                <CardTitle className="text-2xl">{scriptStats?.pending_review ?? 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Podcasts Generated</CardDescription>
                <CardTitle className="text-2xl">{scriptStats?.completed_with_audio ?? 0}</CardTitle>
              </CardHeader>
            </Card>
          </div>
        </PageSection>
      )}

      {/* Quick Actions */}
      <PageSection
        title="Quick Actions"
        description="Common tasks you might want to perform"
      >
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Button variant="outline" className="h-auto flex-col gap-2 p-4" asChild>
            <Link to="/contents">
              <Newspaper className="h-6 w-6" />
              <span>Ingest Content</span>
            </Link>
          </Button>
          <Button variant="outline" className="h-auto flex-col gap-2 p-4" asChild>
            <Link to="/summaries">
              <Sparkles className="h-6 w-6" />
              <span>Generate Summaries</span>
            </Link>
          </Button>
          <Button variant="outline" className="h-auto flex-col gap-2 p-4" asChild>
            <Link to="/digests">
              <FileText className="h-6 w-6" />
              <span>Create Digest</span>
            </Link>
          </Button>
          <Button variant="outline" className="h-auto flex-col gap-2 p-4" asChild>
            <Link to="/scripts">
              <Mic className="h-6 w-6" />
              <span>Review Scripts</span>
            </Link>
          </Button>
        </div>
      </PageSection>

      {/* Recent Activity */}
      <PageSection
        title="Recent Activity"
        description="Latest updates in your pipeline"
      >
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            {isLoading ? (
              <div className="flex items-center justify-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Loading activity...</span>
              </div>
            ) : (contentStats?.total ?? 0) > 0 ? (
              <>
                <p>
                  {contentStats?.total} content items ingested, {summaryStats?.total ?? 0} summaries generated.
                </p>
                <p className="mt-1 text-sm">
                  {pendingContent > 0
                    ? `${pendingContent} items pending summarization.`
                    : "All content has been processed."}
                </p>
              </>
            ) : (
              <>
                <p>No recent activity to display.</p>
                <p className="mt-1 text-sm">
                  Start by ingesting content from Gmail, RSS, or YouTube.
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </PageSection>
    </PageContainer>
  )
}
