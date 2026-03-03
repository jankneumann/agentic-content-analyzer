/**
 * GenerateDigestDialog Component
 *
 * Dialog for configuring and triggering digest generation.
 * Allows selecting all generation parameters:
 * - Digest type (daily/weekly)
 * - Date range
 * - Section limits
 */

import * as React from "react"
import { format, subDays, startOfDay, endOfDay } from "date-fns"
import { Calendar, Loader2, FileText, Lightbulb, Cpu, TrendingUp, Filter } from "lucide-react"

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ContentQueryBuilder } from "@/components/query"
import type { ContentQuery } from "@/types/query"

interface GenerateDigestDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onGenerate: (params: DigestGenerationParams) => void
  isGenerating?: boolean
}

export interface DigestGenerationParams {
  digest_type: "daily" | "weekly"
  period_start?: string
  period_end?: string
  max_strategic_insights?: number
  max_technical_developments?: number
  max_emerging_trends?: number
  content_query?: ContentQuery
}

export function GenerateDigestDialog({
  open,
  onOpenChange,
  onGenerate,
  isGenerating = false,
}: GenerateDigestDialogProps) {
  // Form state
  const [digestType, setDigestType] = React.useState<"daily" | "weekly">("daily")
  const [useCustomDates, setUseCustomDates] = React.useState(false)
  const [periodStart, setPeriodStart] = React.useState("")
  const [periodEnd, setPeriodEnd] = React.useState("")
  const [maxStrategic, setMaxStrategic] = React.useState(5)
  const [maxTechnical, setMaxTechnical] = React.useState(5)
  const [maxTrends, setMaxTrends] = React.useState(3)
  const [filtersOpen, setFiltersOpen] = React.useState(false)
  const [contentQuery, setContentQuery] = React.useState<ContentQuery | undefined>(undefined)

  // Set default dates based on digest type
  React.useEffect(() => {
    const now = new Date()
    if (digestType === "daily") {
      const yesterday = subDays(now, 1)
      setPeriodStart(format(startOfDay(yesterday), "yyyy-MM-dd"))
      setPeriodEnd(format(endOfDay(yesterday), "yyyy-MM-dd"))
    } else {
      const weekAgo = subDays(now, 7)
      setPeriodStart(format(startOfDay(weekAgo), "yyyy-MM-dd"))
      setPeriodEnd(format(endOfDay(subDays(now, 1)), "yyyy-MM-dd"))
    }
  }, [digestType])

  const handleGenerate = () => {
    const params: DigestGenerationParams = {
      digest_type: digestType,
      max_strategic_insights: maxStrategic,
      max_technical_developments: maxTechnical,
      max_emerging_trends: maxTrends,
    }

    if (useCustomDates && periodStart && periodEnd) {
      params.period_start = new Date(periodStart).toISOString()
      params.period_end = new Date(periodEnd + "T23:59:59").toISOString()
    }

    // Include content query if filters are active
    if (contentQuery && Object.keys(contentQuery).length > 0) {
      params.content_query = contentQuery
    }

    onGenerate(params)
  }

  const handleQueryChange = React.useCallback((query: ContentQuery) => {
    setContentQuery(Object.keys(query).length > 0 ? query : undefined)
  }, [])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Generate Digest
          </DialogTitle>
          <DialogDescription>
            Configure and generate a new AI newsletter digest.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Digest Type */}
          <div className="space-y-2">
            <Label>Digest Type</Label>
            <Tabs value={digestType} onValueChange={(v) => setDigestType(v as "daily" | "weekly")}>
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="daily">Daily</TabsTrigger>
                <TabsTrigger value="weekly">Weekly</TabsTrigger>
              </TabsList>
            </Tabs>
            <p className="text-xs text-muted-foreground">
              {digestType === "daily"
                ? "Covers newsletters from a single day"
                : "Covers newsletters from the past week"}
            </p>
          </div>

          {/* Date Range */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Date Range</Label>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setUseCustomDates(!useCustomDates)}
                className="h-7 text-xs"
              >
                {useCustomDates ? "Use defaults" : "Customize"}
              </Button>
            </div>
            {useCustomDates ? (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Start Date</Label>
                  <Input
                    type="date"
                    value={periodStart}
                    onChange={(e) => setPeriodStart(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">End Date</Label>
                  <Input
                    type="date"
                    value={periodEnd}
                    onChange={(e) => setPeriodEnd(e.target.value)}
                  />
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2 rounded-md border p-3 bg-muted/30">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">
                  {periodStart && periodEnd
                    ? `${format(new Date(periodStart), "MMM d")} - ${format(new Date(periodEnd), "MMM d, yyyy")}`
                    : "Default range"}
                </span>
              </div>
            )}
          </div>

          {/* Section Limits */}
          <div className="space-y-3">
            <Label>Section Limits</Label>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground flex items-center gap-1">
                  <Lightbulb className="h-3 w-3" />
                  Strategic
                </Label>
                <Select
                  value={String(maxStrategic)}
                  onValueChange={(v) => setMaxStrategic(Number(v))}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[3, 4, 5, 6, 7, 8].map((n) => (
                      <SelectItem key={n} value={String(n)}>
                        {n} max
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground flex items-center gap-1">
                  <Cpu className="h-3 w-3" />
                  Technical
                </Label>
                <Select
                  value={String(maxTechnical)}
                  onValueChange={(v) => setMaxTechnical(Number(v))}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[3, 4, 5, 6, 7, 8].map((n) => (
                      <SelectItem key={n} value={String(n)}>
                        {n} max
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground flex items-center gap-1">
                  <TrendingUp className="h-3 w-3" />
                  Trends
                </Label>
                <Select
                  value={String(maxTrends)}
                  onValueChange={(v) => setMaxTrends(Number(v))}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[2, 3, 4, 5].map((n) => (
                      <SelectItem key={n} value={String(n)}>
                        {n} max
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </div>

        {/* Advanced Filters */}
        <Collapsible open={filtersOpen} onOpenChange={setFiltersOpen}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="w-full justify-start text-sm">
              <Filter className="h-4 w-4 mr-2" />
              Advanced Filters
              {contentQuery && Object.keys(contentQuery).length > 0 && (
                <span className="ml-auto text-xs text-muted-foreground">Active</span>
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-2 pb-4">
            <ContentQueryBuilder
              onChange={handleQueryChange}
              showPreview
            />
          </CollapsibleContent>
        </Collapsible>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleGenerate} disabled={isGenerating}>
            {isGenerating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <FileText className="mr-2 h-4 w-4" />
                Generate {digestType === "daily" ? "Daily" : "Weekly"} Digest
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
