/**
 * Ingest Configuration Page
 *
 * Full-page interface for configuring and triggering content ingestion
 * from all supported sources. Replaces the compact IngestContentsDialog
 * with a spacious layout that scales to many source types.
 *
 * Route: /ingest
 */

import { useState } from "react"
import { createRoute, useNavigate } from "@tanstack/react-router"
import {
  Download,
  Mail,
  Rss,
  Youtube,
  Mic,
  Link,
  Globe,
  Search,
  Loader2,
  ArrowLeft,
  BookOpen,
} from "lucide-react"
import { toast } from "sonner"

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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { useIngestContents, useSaveUrl } from "@/hooks/use-contents"
import { useBackgroundTasks } from "@/contexts/BackgroundTasksContext"
import type { ContentSource } from "@/types"
import type { IngestContentParams } from "@/lib/api/contents"

/**
 * Route definition
 */
export const IngestRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "ingest",
  component: IngestPage,
})

/**
 * Source configuration metadata
 */
interface SourceConfig {
  key: ContentSource
  label: string
  description: string
  icon: React.ReactNode
  maxResultsLabel: string
  maxResultsMax: number
  supportsIngest: boolean
}

const SOURCE_CONFIGS: SourceConfig[] = [
  {
    key: "gmail",
    label: "Gmail",
    description: "Fetch newsletters from your Gmail inbox. Requires Gmail API credentials.",
    icon: <Mail className="h-5 w-5" />,
    maxResultsLabel: "Maximum emails",
    maxResultsMax: 200,
    supportsIngest: true,
  },
  {
    key: "rss",
    label: "RSS Feeds",
    description: "Fetch articles from configured RSS/Atom feeds defined in sources.d/rss.yaml.",
    icon: <Rss className="h-5 w-5" />,
    maxResultsLabel: "Maximum articles",
    maxResultsMax: 200,
    supportsIngest: true,
  },
  {
    key: "substack",
    label: "Substack",
    description: "Fetch paid Substack subscriptions via browser session. Configured in sources.d/rss.yaml.",
    icon: <BookOpen className="h-5 w-5" />,
    maxResultsLabel: "Maximum articles",
    maxResultsMax: 200,
    supportsIngest: true,
  },
  {
    key: "youtube",
    label: "YouTube",
    description: "Fetch video transcripts from configured playlists and RSS feeds in sources.d/.",
    icon: <Youtube className="h-5 w-5" />,
    maxResultsLabel: "Maximum videos",
    maxResultsMax: 100,
    supportsIngest: true,
  },
  {
    key: "podcast",
    label: "Podcasts",
    description: "Fetch episode transcripts from configured podcast feeds in sources.d/podcasts.yaml.",
    icon: <Mic className="h-5 w-5" />,
    maxResultsLabel: "Maximum episodes",
    maxResultsMax: 200,
    supportsIngest: true,
  },
  {
    key: "xsearch",
    label: "X / Twitter Search",
    description: "Search X/Twitter via xAI Grok API for AI-related threads and discussions.",
    icon: <Search className="h-5 w-5" />,
    maxResultsLabel: "Maximum threads",
    maxResultsMax: 50,
    supportsIngest: true,
  },
  {
    key: "perplexity",
    label: "Perplexity Web Search",
    description: "AI-powered web search via Perplexity Sonar API with citations and source extraction.",
    icon: <Globe className="h-5 w-5" />,
    maxResultsLabel: "Maximum results",
    maxResultsMax: 50,
    supportsIngest: true,
  },
]

/**
 * Per-source form state
 */
interface SourceFormState {
  maxResults: number
  daysBack: number
  forceReprocess: boolean
}

const DEFAULT_FORM_STATE: SourceFormState = {
  maxResults: 50,
  daysBack: 7,
  forceReprocess: false,
}

/**
 * Ingest configuration page component
 */
function IngestPage() {
  const navigate = useNavigate()
  const ingestMutation = useIngestContents()
  const saveUrlMutation = useSaveUrl()
  const { addTask, updateTask, completeTask, failTask } = useBackgroundTasks()

  // Per-source form state
  const [formStates, setFormStates] = useState<Record<string, SourceFormState>>({})

  // URL input state
  const [urlInput, setUrlInput] = useState("")
  const [urlError, setUrlError] = useState("")

  // Track which sources are currently ingesting
  const [ingestingSources, setIngestingSources] = useState<Set<string>>(new Set())

  const getFormState = (sourceKey: string): SourceFormState => {
    return formStates[sourceKey] ?? DEFAULT_FORM_STATE
  }

  const updateFormState = (sourceKey: string, updates: Partial<SourceFormState>) => {
    setFormStates((prev) => ({
      ...prev,
      [sourceKey]: { ...getFormState(sourceKey), ...updates },
    }))
  }

  const validateUrl = (value: string): boolean => {
    if (!value.trim()) {
      setUrlError("URL is required")
      return false
    }
    try {
      const parsed = new URL(value.trim())
      if (!parsed.protocol.startsWith("http")) {
        setUrlError("URL must start with http:// or https://")
        return false
      }
    } catch {
      setUrlError("Please enter a valid URL")
      return false
    }
    setUrlError("")
    return true
  }

  const handleIngest = (source: ContentSource, config: SourceConfig) => {
    const state = getFormState(source)

    setIngestingSources((prev) => new Set(prev).add(source))

    const taskId = addTask({
      type: "ingest",
      title: `Ingest from ${config.label}`,
      message: "Starting ingestion...",
    })

    const params: IngestContentParams = {
      source,
      max_results: state.maxResults,
      days_back: state.daysBack,
      force_reprocess: state.forceReprocess,
    }

    ingestMutation.mutate(params, {
      onSuccess: () => {
        updateTask(taskId, { progress: 20, message: `Fetching from ${config.label}...` })

        let pollCount = 0
        const maxPolls = 60

        const pollInterval = setInterval(() => {
          pollCount++
          const progressPercent = Math.min(20 + pollCount * 1.3, 95)
          updateTask(taskId, {
            progress: Math.round(progressPercent),
            message:
              pollCount < 10
                ? `Connecting to ${config.label}...`
                : pollCount < 20
                  ? "Fetching content..."
                  : pollCount < 30
                    ? "Processing content..."
                    : "Finalizing ingestion...",
          })

          if (pollCount >= maxPolls) {
            clearInterval(pollInterval)
            setIngestingSources((prev) => {
              const next = new Set(prev)
              next.delete(source)
              return next
            })
            completeTask(taskId, "Ingestion completed")
            toast.success(`Ingestion from ${config.label} completed`)
          }
        }, 5000)

        // Clear ingesting state after a reasonable time
        setTimeout(() => {
          setIngestingSources((prev) => {
            const next = new Set(prev)
            next.delete(source)
            return next
          })
        }, 10000)
      },
      onError: (err) => {
        setIngestingSources((prev) => {
          const next = new Set(prev)
          next.delete(source)
          return next
        })
        const errorMsg = err instanceof Error ? err.message : "Unknown error"
        failTask(taskId, errorMsg)
        toast.error(`Failed to ingest from ${config.label}: ${errorMsg}`)
      },
    })

    updateTask(taskId, { progress: 10, message: "Queuing ingestion..." })
    toast.info(`Ingestion from ${config.label} started`, {
      description: "Check background tasks for progress.",
    })
  }

  const handleSaveUrl = () => {
    if (!validateUrl(urlInput)) return

    saveUrlMutation.mutate(
      { url: urlInput.trim() },
      {
        onSuccess: (data) => {
          if (data.duplicate) {
            toast.info("URL already saved", {
              description: `Content ID: ${data.content_id}`,
            })
          } else {
            toast.success("URL saved for extraction", {
              description: `Content ID: ${data.content_id}`,
            })
          }
          setUrlInput("")
        },
        onError: (err) => {
          const errorMsg = err instanceof Error ? err.message : "Unknown error"
          toast.error(`Failed to save URL: ${errorMsg}`)
        },
      }
    )
  }

  return (
    <PageContainer
      title="Ingest Content"
      description="Configure and trigger content ingestion from all available sources"
      actions={
        <Button variant="outline" onClick={() => navigate({ to: "/contents" })}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Contents
        </Button>
      }
    >
      {/* Direct URL Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Link className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">Save URL</CardTitle>
          </div>
          <CardDescription>
            Submit a URL directly for content extraction. The system will fetch, parse, and store the content.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <div className="flex-1 space-y-1">
              <Input
                type="url"
                placeholder="https://example.com/article"
                value={urlInput}
                onChange={(e) => { setUrlInput(e.target.value); setUrlError("") }}
                onKeyDown={(e) => { if (e.key === "Enter") handleSaveUrl() }}
              />
              {urlError && (
                <p className="text-xs text-destructive">{urlError}</p>
              )}
            </div>
            <Button onClick={handleSaveUrl} disabled={saveUrlMutation.isPending}>
              {saveUrlMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Download className="mr-2 h-4 w-4" />
              )}
              Save URL
            </Button>
          </div>
        </CardContent>
      </Card>

      <Separator />

      {/* Source Cards Grid */}
      <div className="grid gap-6 md:grid-cols-2">
        {SOURCE_CONFIGS.map((config) => {
          const state = getFormState(config.key)
          const isIngesting = ingestingSources.has(config.key)

          return (
            <Card key={config.key}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="text-muted-foreground">{config.icon}</div>
                    <CardTitle className="text-base">{config.label}</CardTitle>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    Source
                  </Badge>
                </div>
                <CardDescription>{config.description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                {/* Max Results */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-sm">{config.maxResultsLabel}</Label>
                    <span className="text-sm font-medium tabular-nums">{state.maxResults}</span>
                  </div>
                  <Slider
                    value={[state.maxResults]}
                    onValueChange={([v]) => updateFormState(config.key, { maxResults: v })}
                    min={10}
                    max={config.maxResultsMax}
                    step={10}
                  />
                </div>

                {/* Days Back */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-sm">Days back</Label>
                    <span className="text-sm font-medium tabular-nums">{state.daysBack} days</span>
                  </div>
                  <Slider
                    value={[state.daysBack]}
                    onValueChange={([v]) => updateFormState(config.key, { daysBack: v })}
                    min={1}
                    max={90}
                    step={1}
                  />
                </div>

                {/* Force Reprocess */}
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id={`force-reprocess-${config.key}`}
                    checked={state.forceReprocess}
                    onCheckedChange={(checked) =>
                      updateFormState(config.key, { forceReprocess: checked === true })
                    }
                  />
                  <label
                    htmlFor={`force-reprocess-${config.key}`}
                    className="text-sm leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                  >
                    Force reprocess existing content
                  </label>
                </div>

                {/* Ingest Button */}
                <Button
                  className="w-full"
                  onClick={() => handleIngest(config.key, config)}
                  disabled={isIngesting}
                >
                  {isIngesting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Ingesting...
                    </>
                  ) : (
                    <>
                      <Download className="mr-2 h-4 w-4" />
                      Ingest from {config.label}
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </PageContainer>
  )
}
