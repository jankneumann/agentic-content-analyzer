/**
 * IngestNewslettersDialog Component
 *
 * Dialog for configuring and triggering newsletter ingestion.
 * Allows selecting:
 * - Source (Gmail/RSS)
 * - Max results
 * - Days back to search
 */

import * as React from "react"
import { Loader2, Mail, Rss, Download } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

interface IngestNewslettersDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onIngest: (params: IngestParams) => void
  isIngesting?: boolean
}

export interface IngestParams {
  source: "gmail" | "rss"
  max_results: number
  days_back: number
}

export function IngestNewslettersDialog({
  open,
  onOpenChange,
  onIngest,
  isIngesting = false,
}: IngestNewslettersDialogProps) {
  // Form state
  const [source, setSource] = React.useState<"gmail" | "rss">("gmail")
  const [maxResults, setMaxResults] = React.useState(50)
  const [daysBack, setDaysBack] = React.useState(7)

  const handleIngest = () => {
    onIngest({
      source,
      max_results: maxResults,
      days_back: daysBack,
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="h-5 w-5" />
            Ingest Newsletters
          </DialogTitle>
          <DialogDescription>
            Fetch newsletters from Gmail or RSS feeds.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Source Selection */}
          <div className="space-y-2">
            <Label>Source</Label>
            <Tabs value={source} onValueChange={(v) => setSource(v as typeof source)}>
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="gmail" className="gap-1.5">
                  <Mail className="h-4 w-4" />
                  Gmail
                </TabsTrigger>
                <TabsTrigger value="rss" className="gap-1.5">
                  <Rss className="h-4 w-4" />
                  RSS Feeds
                </TabsTrigger>
              </TabsList>
            </Tabs>
            <p className="text-xs text-muted-foreground">
              {source === "gmail"
                ? "Fetch newsletters from your Gmail inbox"
                : "Fetch from configured Substack RSS feeds"}
            </p>
          </div>

          {/* Max Results */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Maximum Results</Label>
              <span className="text-sm font-medium">{maxResults}</span>
            </div>
            <Slider
              value={[maxResults]}
              onValueChange={([v]) => setMaxResults(v)}
              min={10}
              max={200}
              step={10}
            />
            <p className="text-xs text-muted-foreground">
              Limit the number of newsletters to fetch
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
              max={30}
              step={1}
            />
            <p className="text-xs text-muted-foreground">
              How far back to search for newsletters
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleIngest} disabled={isIngesting}>
            {isIngesting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Ingesting...
              </>
            ) : (
              <>
                <Download className="mr-2 h-4 w-4" />
                Ingest from {source === "gmail" ? "Gmail" : "RSS"}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
