/**
 * GenerateSummaryDialog Component
 *
 * Dialog for configuring and triggering content summarization.
 * Allows selecting:
 * - All content without summaries or specific IDs
 * - Force re-summarization toggle
 */

import * as React from "react"
import { Loader2, FileText, RefreshCw, ListChecks } from "lucide-react"

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
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

interface GenerateSummaryDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onGenerate: (params: SummaryGenerationParams) => void
  isGenerating?: boolean
  pendingCount?: number
  failedCount?: number
}

export interface SummaryGenerationParams {
  /** Content IDs to summarize (uses newsletter_ids for backward compatibility) */
  newsletter_ids: number[]
  force: boolean
  retry_failed: boolean
}

export function GenerateSummaryDialog({
  open,
  onOpenChange,
  onGenerate,
  isGenerating = false,
  pendingCount = 0,
  failedCount = 0,
}: GenerateSummaryDialogProps) {
  // Form state
  const [mode, setMode] = React.useState<"pending" | "specific">("pending")
  const [contentIds, setContentIds] = React.useState("")
  const [force, setForce] = React.useState(false)
  const [retryFailed, setRetryFailed] = React.useState(false)

  const parsedIds = React.useMemo(() => {
    if (!contentIds.trim()) return []
    return contentIds
      .split(/[,\s]+/)
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n))
  }, [contentIds])

  const handleGenerate = () => {
    onGenerate({
      newsletter_ids: mode === "specific" ? parsedIds : [],
      force,
      retry_failed: retryFailed,
    })
  }

  // Calculate total items to process
  const totalPending = pendingCount + (retryFailed ? failedCount : 0)
  const canGenerate =
    mode === "pending" ? totalPending > 0 : parsedIds.length > 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Generate Summaries
          </DialogTitle>
          <DialogDescription>
            Summarize content using AI to extract key insights.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Mode Selection */}
          <div className="space-y-2">
            <Label>Content to Summarize</Label>
            <Tabs value={mode} onValueChange={(v) => setMode(v as typeof mode)}>
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="pending" className="gap-1.5">
                  <ListChecks className="h-4 w-4" />
                  All Pending
                </TabsTrigger>
                <TabsTrigger value="specific">Specific IDs</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {mode === "pending" ? (
            <div className="space-y-3">
              <div className="rounded-lg border p-4 bg-muted/30">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{pendingCount} content items pending</p>
                    <p className="text-xs text-muted-foreground">
                      Content without summaries will be processed
                    </p>
                  </div>
                  {pendingCount > 0 && (
                    <Badge variant="secondary">{pendingCount}</Badge>
                  )}
                </div>
              </div>

              {/* Retry Failed Toggle */}
              {failedCount > 0 && (
                <div className="flex items-center justify-between rounded-lg border p-3 border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950">
                  <div className="space-y-0.5">
                    <Label
                      htmlFor="retry-failed-switch"
                      className="flex items-center gap-2 text-amber-800 dark:text-amber-200"
                    >
                      <RefreshCw className="h-4 w-4" />
                      Retry {failedCount} Failed Items
                    </Label>
                    <p
                      id="retry-failed-desc"
                      className="text-xs text-amber-600 dark:text-amber-400"
                    >
                      Reset failed content and attempt summarization again
                    </p>
                  </div>
                  <Switch
                    id="retry-failed-switch"
                    aria-describedby="retry-failed-desc"
                    checked={retryFailed}
                    onCheckedChange={setRetryFailed}
                  />
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">
                Content IDs (comma or space separated)
              </Label>
              <Input
                placeholder="e.g., 123, 456, 789"
                value={contentIds}
                onChange={(e) => setContentIds(e.target.value)}
              />
              {parsedIds.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {parsedIds.map((id) => (
                    <Badge key={id} variant="outline">
                      [{id}]
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Force Toggle */}
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="space-y-0.5">
              <Label
                htmlFor="force-summarize-switch"
                className="flex items-center gap-2"
              >
                <RefreshCw className="h-4 w-4" />
                Force Re-summarize
              </Label>
              <p
                id="force-summarize-desc"
                className="text-xs text-muted-foreground"
              >
                Regenerate even if summary already exists
              </p>
            </div>
            <Switch
              id="force-summarize-switch"
              aria-describedby="force-summarize-desc"
              checked={force}
              onCheckedChange={setForce}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleGenerate} disabled={isGenerating || !canGenerate}>
            {isGenerating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Summarizing...
              </>
            ) : (
              <>
                <FileText className="mr-2 h-4 w-4" />
                Summarize {mode === "pending" ? `${totalPending} Items` : `${parsedIds.length} Items`}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
