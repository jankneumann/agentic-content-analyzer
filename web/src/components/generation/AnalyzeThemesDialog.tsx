/**
 * AnalyzeThemesDialog Component
 *
 * Dialog for configuring and triggering theme analysis.
 * Allows selecting date range and analysis parameters.
 */

import * as React from "react"
import { format, subDays, startOfDay, endOfDay } from "date-fns"
import { Calendar, Loader2, BarChart3, Network, Settings2 } from "lucide-react"

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
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

interface AnalyzeThemesDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAnalyze: (params: ThemeAnalysisParams) => void
  isAnalyzing?: boolean
}

export interface ThemeAnalysisParams {
  start_date?: string
  end_date?: string
  max_themes: number
  min_newsletters: number
  relevance_threshold: number
  include_historical_context: boolean
}

export function AnalyzeThemesDialog({
  open,
  onOpenChange,
  onAnalyze,
  isAnalyzing = false,
}: AnalyzeThemesDialogProps) {
  // Form state
  const [dateRange, setDateRange] = React.useState<"week" | "month" | "custom">("week")
  const [periodStart, setPeriodStart] = React.useState("")
  const [periodEnd, setPeriodEnd] = React.useState("")
  const [maxThemes, setMaxThemes] = React.useState(15)
  const [minNewsletters, setMinNewsletters] = React.useState(2)
  const [relevanceThreshold, setRelevanceThreshold] = React.useState(0.3)
  const [includeHistorical, setIncludeHistorical] = React.useState(true)

  // Set default dates based on date range
  React.useEffect(() => {
    const now = new Date()
    const yesterday = subDays(now, 1)

    if (dateRange === "week") {
      const weekAgo = subDays(now, 7)
      setPeriodStart(format(startOfDay(weekAgo), "yyyy-MM-dd"))
      setPeriodEnd(format(endOfDay(yesterday), "yyyy-MM-dd"))
    } else if (dateRange === "month") {
      const monthAgo = subDays(now, 30)
      setPeriodStart(format(startOfDay(monthAgo), "yyyy-MM-dd"))
      setPeriodEnd(format(endOfDay(yesterday), "yyyy-MM-dd"))
    }
  }, [dateRange])

  const handleAnalyze = () => {
    const params: ThemeAnalysisParams = {
      max_themes: maxThemes,
      min_newsletters: minNewsletters,
      relevance_threshold: relevanceThreshold,
      include_historical_context: includeHistorical,
    }

    if (periodStart && periodEnd) {
      params.start_date = new Date(periodStart).toISOString()
      params.end_date = new Date(periodEnd + "T23:59:59").toISOString()
    }

    onAnalyze(params)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Analyze Themes
          </DialogTitle>
          <DialogDescription>
            Analyze themes and patterns across newsletters using AI and knowledge graph.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Date Range */}
          <div className="space-y-2">
            <Label>Analysis Period</Label>
            <Tabs value={dateRange} onValueChange={(v) => setDateRange(v as "week" | "month" | "custom")}>
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="week">Last Week</TabsTrigger>
                <TabsTrigger value="month">Last Month</TabsTrigger>
                <TabsTrigger value="custom">Custom</TabsTrigger>
              </TabsList>
            </Tabs>
            {dateRange === "custom" ? (
              <div className="grid grid-cols-2 gap-3 pt-2">
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

          {/* Analysis Parameters */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Settings2 className="h-4 w-4 text-muted-foreground" />
              <Label>Analysis Parameters</Label>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Max Themes</Label>
                <Select
                  value={String(maxThemes)}
                  onValueChange={(v) => setMaxThemes(Number(v))}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[5, 10, 15, 20, 30].map((n) => (
                      <SelectItem key={n} value={String(n)}>
                        {n} themes
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Min Newsletters</Label>
                <Select
                  value={String(minNewsletters)}
                  onValueChange={(v) => setMinNewsletters(Number(v))}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[1, 2, 3, 5, 10].map((n) => (
                      <SelectItem key={n} value={String(n)}>
                        {n} min
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Relevance Threshold</Label>
              <Select
                value={String(relevanceThreshold)}
                onValueChange={(v) => setRelevanceThreshold(Number(v))}
              >
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="0.1">Low (0.1) - More themes</SelectItem>
                  <SelectItem value="0.3">Medium (0.3) - Balanced</SelectItem>
                  <SelectItem value="0.5">High (0.5) - Key themes only</SelectItem>
                  <SelectItem value="0.7">Very High (0.7) - Critical themes</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Historical Context */}
          <div className="flex items-center justify-between rounded-md border p-3">
            <div className="flex items-center gap-2">
              <Network className="h-4 w-4 text-muted-foreground" />
              <div>
                <Label className="text-sm">Include Historical Context</Label>
                <p className="text-xs text-muted-foreground">
                  Enrich themes with knowledge graph history
                </p>
              </div>
            </div>
            <Switch
              checked={includeHistorical}
              onCheckedChange={setIncludeHistorical}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleAnalyze} disabled={isAnalyzing}>
            {isAnalyzing ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <BarChart3 className="mr-2 h-4 w-4" />
                Analyze Themes
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
