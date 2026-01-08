/**
 * Themes Page
 *
 * Displays theme analysis with knowledge graph visualization.
 * Shows entities, relationships, and theme evolution over time.
 *
 * Route: /themes
 */

import { useState } from "react"
import { createRoute } from "@tanstack/react-router"
import { BarChart3, Network, Table2, RefreshCw, Loader2, CheckCircle } from "lucide-react"
import { toast } from "sonner"
import { formatDistanceToNow } from "date-fns"

import { Route as rootRoute } from "./__root"
import { PageContainer } from "@/components/layout"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useBackgroundTasks } from "@/contexts/BackgroundTasksContext"
import { useAnalyzeThemes, useAnalysisStatus, useLatestAnalysis } from "@/hooks"
import {
  AnalyzeThemesDialog,
  type ThemeAnalysisParams,
} from "@/components/generation"

export const ThemesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "themes",
  component: ThemesPage,
})

function ThemesPage() {
  const [showAnalyzeDialog, setShowAnalyzeDialog] = useState(false)
  const [currentAnalysisId, setCurrentAnalysisId] = useState<number | null>(null)

  const { addTask, updateTask, completeTask, failTask } = useBackgroundTasks()
  const analyzeMutation = useAnalyzeThemes()
  const { data: analysisStatus } = useAnalysisStatus(currentAnalysisId)
  const { data: latestAnalysis, refetch: refetchLatest } = useLatestAnalysis()

  // Check if we have a valid analysis result
  const hasAnalysis = latestAnalysis && "themes" in latestAnalysis

  const handleAnalyze = (params: ThemeAnalysisParams) => {
    setShowAnalyzeDialog(false)

    const taskId = addTask({
      type: "themes",
      title: "Analyze Themes",
      message: "Starting theme analysis...",
    })

    analyzeMutation.mutate(
      {
        start_date: params.start_date,
        end_date: params.end_date,
        max_themes: params.max_themes,
        min_newsletters: params.min_newsletters,
        relevance_threshold: params.relevance_threshold,
        include_historical_context: params.include_historical_context,
      },
      {
        onSuccess: (response) => {
          if (response.analysis_id) {
            setCurrentAnalysisId(response.analysis_id)
            updateTask(taskId, { progress: 20, message: "Analyzing newsletters..." })

            // Poll for completion
            let pollCount = 0
            const maxPolls = 120 // 10 minutes max (5s intervals)

            const pollInterval = setInterval(async () => {
              pollCount++
              const progressPercent = Math.min(20 + pollCount * 0.6, 95)
              updateTask(taskId, {
                progress: Math.round(progressPercent),
                message:
                  pollCount < 15
                    ? "Fetching newsletter summaries..."
                    : pollCount < 30
                      ? "Querying knowledge graph..."
                      : pollCount < 60
                        ? "Extracting themes with AI..."
                        : pollCount < 90
                          ? "Adding historical context..."
                          : "Finalizing analysis...",
              })

              // Check analysis status
              const result = await refetchLatest()
              const completed = result.data && "themes" in result.data

              if (completed || pollCount >= maxPolls) {
                clearInterval(pollInterval)
                setCurrentAnalysisId(null)

                if (completed && "themes" in result.data) {
                  completeTask(taskId, `Found ${result.data.total_themes} themes`)
                  toast.success(`Theme analysis complete: ${result.data.total_themes} themes identified`)
                } else {
                  updateTask(taskId, { progress: 95, message: "Analysis may still be running..." })
                }
              }
            }, 5000)
          }
        },
        onError: (err) => {
          const errorMsg = err instanceof Error ? err.message : "Unknown error"
          failTask(taskId, errorMsg)
          toast.error(`Failed to analyze themes: ${errorMsg}`)
        },
      }
    )

    updateTask(taskId, { progress: 10, message: "Queuing analysis..." })
  }

  return (
    <PageContainer
      title="Themes"
      description="Knowledge graph analysis showing themes, entities, and relationships"
      actions={
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetchLatest()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline">
            <Table2 className="mr-2 h-4 w-4" />
            Table View
          </Button>
          <Button variant="outline">
            <Network className="mr-2 h-4 w-4" />
            Graph View
          </Button>
          <Button onClick={() => setShowAnalyzeDialog(true)}>
            <BarChart3 className="mr-2 h-4 w-4" />
            Analyze Themes
          </Button>
        </div>
      }
    >
      {/* Stats cards - show when we have analysis */}
      {hasAnalysis && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Total Themes</CardDescription>
              <CardTitle className="text-2xl">{latestAnalysis.total_themes}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Emerging</CardDescription>
              <CardTitle className="text-2xl">{latestAnalysis.emerging_themes_count}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Newsletters Analyzed</CardDescription>
              <CardTitle className="text-2xl">{latestAnalysis.newsletter_count}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Top Theme</CardDescription>
              <CardTitle className="text-lg truncate">{latestAnalysis.top_theme ?? "N/A"}</CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-muted-foreground" />
              <CardTitle>Theme Analysis</CardTitle>
            </div>
            {hasAnalysis && (
              <Badge variant="outline" className="gap-1">
                <CheckCircle className="h-3 w-3" />
                Last analyzed {formatDistanceToNow(new Date(latestAnalysis.analysis_date), { addSuffix: true })}
              </Badge>
            )}
          </div>
          <CardDescription>
            Explore patterns and connections across your newsletter content.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {currentAnalysisId && analysisStatus?.status === "running" ? (
            <div className="flex h-96 items-center justify-center rounded-lg border border-dashed">
              <div className="text-center">
                <Loader2 className="mx-auto h-12 w-12 animate-spin text-muted-foreground/50" />
                <p className="mt-4 text-sm text-muted-foreground">
                  Analyzing themes...
                </p>
                <p className="text-xs text-muted-foreground">
                  This may take a few minutes
                </p>
              </div>
            </div>
          ) : hasAnalysis && latestAnalysis.themes.length > 0 ? (
            <div className="space-y-4">
              {latestAnalysis.themes.slice(0, 10).map((theme, idx) => (
                <div key={idx} className="flex items-start gap-4 p-4 rounded-lg border">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-medium">{theme.name}</h3>
                      <Badge variant="outline" className="text-xs capitalize">
                        {theme.category.replace("_", " ")}
                      </Badge>
                      <Badge
                        variant={
                          theme.trend === "emerging"
                            ? "default"
                            : theme.trend === "growing"
                              ? "secondary"
                              : "outline"
                        }
                        className="text-xs capitalize"
                      >
                        {theme.trend}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{theme.description}</p>
                    {theme.key_points.length > 0 && (
                      <ul className="mt-2 text-sm text-muted-foreground list-disc list-inside">
                        {theme.key_points.slice(0, 2).map((point, i) => (
                          <li key={i}>{point}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold">{Math.round(theme.relevance_score * 100)}%</div>
                    <div className="text-xs text-muted-foreground">relevance</div>
                  </div>
                </div>
              ))}
              {latestAnalysis.themes.length > 10 && (
                <p className="text-center text-sm text-muted-foreground">
                  + {latestAnalysis.themes.length - 10} more themes
                </p>
              )}
            </div>
          ) : (
            <div className="flex h-96 items-center justify-center rounded-lg border border-dashed">
              <div className="text-center">
                <Network className="mx-auto h-12 w-12 text-muted-foreground/50" />
                <p className="mt-2 text-sm text-muted-foreground">
                  No theme analysis yet
                </p>
                <p className="text-xs text-muted-foreground">
                  Click "Analyze Themes" to get started
                </p>
                <Button
                  className="mt-4"
                  size="sm"
                  onClick={() => setShowAnalyzeDialog(true)}
                >
                  <BarChart3 className="mr-2 h-4 w-4" />
                  Analyze Themes
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Analyze themes dialog */}
      <AnalyzeThemesDialog
        open={showAnalyzeDialog}
        onOpenChange={setShowAnalyzeDialog}
        onAnalyze={handleAnalyze}
        isAnalyzing={analyzeMutation.isPending}
      />
    </PageContainer>
  )
}
