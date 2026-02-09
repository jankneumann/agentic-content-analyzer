/**
 * IngestContentsDialog Component
 *
 * Dialog for configuring and triggering content ingestion.
 * Supports ingestion from Gmail, RSS feeds, YouTube playlists,
 * Podcasts, and direct URL submission using the unified Content model.
 */

import * as React from "react"
import { Loader2, Mail, Mic, Rss, Download, Youtube, Link } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Checkbox } from "@/components/ui/checkbox"
import type { ContentSource } from "@/types"

type SourceTab = ContentSource | "url"

interface IngestContentsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onIngest: (params: IngestContentParams) => void
  onSaveUrl?: (params: SaveUrlParams) => void
  isIngesting?: boolean
  isSavingUrl?: boolean
}

export interface IngestContentParams {
  source: ContentSource
  max_results: number
  days_back: number
  force_reprocess?: boolean
}

export interface SaveUrlParams {
  url: string
}

export function IngestContentsDialog({
  open,
  onOpenChange,
  onIngest,
  onSaveUrl,
  isIngesting = false,
  isSavingUrl = false,
}: IngestContentsDialogProps) {
  // Form state
  const [source, setSource] = React.useState<SourceTab>("gmail")
  const [maxResults, setMaxResults] = React.useState(50)
  const [daysBack, setDaysBack] = React.useState(7)
  const [forceReprocess, setForceReprocess] = React.useState(false)
  const [urlInput, setUrlInput] = React.useState("")
  const [urlError, setUrlError] = React.useState("")

  const isUrlMode = source === "url"
  const isBusy = isIngesting || isSavingUrl

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

  const handleSubmit = () => {
    if (isUrlMode) {
      if (!validateUrl(urlInput)) return
      onSaveUrl?.({ url: urlInput.trim() })
    } else {
      onIngest({
        source: source as ContentSource,
        max_results: maxResults,
        days_back: daysBack,
        force_reprocess: forceReprocess,
      })
    }
  }

  const getSourceLabel = (s: SourceTab) => {
    switch (s) {
      case "gmail":
        return "Gmail"
      case "rss":
        return "RSS"
      case "youtube":
        return "YouTube"
      case "podcast":
        return "Podcast"
      case "url":
        return "URL"
      default:
        return s
    }
  }

  const getSourceDescription = (s: SourceTab) => {
    switch (s) {
      case "gmail":
        return "Fetch newsletters from your Gmail inbox"
      case "rss":
        return "Fetch articles from configured RSS feeds"
      case "youtube":
        return "Fetch transcripts from configured YouTube playlists"
      case "podcast":
        return "Fetch transcripts from configured podcast feeds"
      case "url":
        return "Save a URL for content extraction"
      default:
        return ""
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="h-5 w-5" />
            Ingest Content
          </DialogTitle>
          <DialogDescription>
            Fetch content from Gmail, RSS feeds, YouTube, Podcasts, or a direct URL.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Source Selection */}
          <div className="space-y-2">
            <Label>Source</Label>
            <Tabs value={source} onValueChange={(v) => { setSource(v as SourceTab); setUrlError("") }}>
              <TabsList className="grid w-full grid-cols-5">
                <TabsTrigger value="gmail" className="gap-1.5">
                  <Mail className="h-4 w-4" />
                  <span className="hidden sm:inline">Gmail</span>
                </TabsTrigger>
                <TabsTrigger value="rss" className="gap-1.5">
                  <Rss className="h-4 w-4" />
                  <span className="hidden sm:inline">RSS</span>
                </TabsTrigger>
                <TabsTrigger value="youtube" className="gap-1.5">
                  <Youtube className="h-4 w-4" />
                  <span className="hidden sm:inline">YouTube</span>
                </TabsTrigger>
                <TabsTrigger value="podcast" className="gap-1.5">
                  <Mic className="h-4 w-4" />
                  <span className="hidden sm:inline">Podcast</span>
                </TabsTrigger>
                <TabsTrigger value="url" className="gap-1.5">
                  <Link className="h-4 w-4" />
                  <span className="hidden sm:inline">URL</span>
                </TabsTrigger>
              </TabsList>
            </Tabs>
            <p className="text-xs text-muted-foreground">
              {getSourceDescription(source)}
            </p>
          </div>

          {isUrlMode ? (
            /* URL Input */
            <div className="space-y-2">
              <Label htmlFor="url-input">URL</Label>
              <Input
                id="url-input"
                type="url"
                placeholder="https://example.com/article"
                value={urlInput}
                onChange={(e) => { setUrlInput(e.target.value); setUrlError("") }}
                onKeyDown={(e) => { if (e.key === "Enter") handleSubmit() }}
              />
              {urlError && (
                <p className="text-xs text-destructive">{urlError}</p>
              )}
            </div>
          ) : (
            <>
              {/* Max Results */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label>Maximum {source === "youtube" ? "Videos" : source === "podcast" ? "Episodes" : "Results"}</Label>
                  <span className="text-sm font-medium">{maxResults}</span>
                </div>
                <Slider
                  value={[maxResults]}
                  onValueChange={([v]) => setMaxResults(v)}
                  min={10}
                  max={source === "youtube" ? 100 : 200}
                  step={10}
                />
                <p className="text-xs text-muted-foreground">
                  {source === "youtube"
                    ? "Maximum videos to fetch per playlist"
                    : source === "podcast"
                      ? "Maximum episodes to fetch per feed"
                      : "Limit the number of items to fetch"}
                </p>
              </div>

              {/* Days Back */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label>Days Back</Label>
                  <span className="text-sm font-medium">{daysBack} days</span>
                </div>
                <Slider
                  value={[daysBack]}
                  onValueChange={([v]) => setDaysBack(v)}
                  min={1}
                  max={90}
                  step={1}
                />
                <p className="text-xs text-muted-foreground">
                  Only fetch content published within this time period
                </p>
              </div>

              {/* Force Reprocess */}
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="force-reprocess"
                  checked={forceReprocess}
                  onCheckedChange={(checked) => setForceReprocess(checked === true)}
                />
                <div className="grid gap-1.5 leading-none">
                  <label
                    htmlFor="force-reprocess"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                  >
                    Force reprocess
                  </label>
                  <p className="text-xs text-muted-foreground">
                    Re-ingest existing content (updates content, resets status)
                  </p>
                </div>
              </div>
            </>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isBusy}>
            {isBusy ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {isUrlMode ? "Saving..." : "Ingesting..."}
              </>
            ) : (
              <>
                {isUrlMode ? (
                  <Link className="mr-2 h-4 w-4" />
                ) : (
                  <Download className="mr-2 h-4 w-4" />
                )}
                {isUrlMode ? "Save URL" : `Ingest from ${getSourceLabel(source)}`}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
