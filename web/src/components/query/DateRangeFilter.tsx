/**
 * DateRangeFilter Component
 *
 * Date range picker with preset options and custom date inputs.
 * Presets: Today, Last 3 days, Last week, Last month.
 */

import * as React from "react"
import { format, subDays, subMonths, startOfDay } from "date-fns"
import { Calendar } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface DateRangeFilterProps {
  startDate: string
  endDate: string
  onStartDateChange: (date: string) => void
  onEndDateChange: (date: string) => void
}

const PRESETS = [
  { label: "Today", days: 0 },
  { label: "3 days", days: 3 },
  { label: "1 week", days: 7 },
  { label: "1 month", months: 1 },
] as const

export function DateRangeFilter({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
}: DateRangeFilterProps) {
  const applyPreset = (preset: (typeof PRESETS)[number]) => {
    const now = new Date()
    const end = format(now, "yyyy-MM-dd")
    let start: string
    if ("months" in preset) {
      start = format(startOfDay(subMonths(now, preset.months)), "yyyy-MM-dd")
    } else {
      start = format(startOfDay(subDays(now, preset.days)), "yyyy-MM-dd")
    }
    onStartDateChange(start)
    onEndDateChange(end)
  }

  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium flex items-center gap-1.5">
        <Calendar className="h-3.5 w-3.5" />
        Date Range
      </Label>
      <div className="flex flex-wrap gap-1">
        {PRESETS.map((preset) => (
          <Button
            key={preset.label}
            variant="outline"
            size="sm"
            className="h-7 text-xs"
            onClick={() => applyPreset(preset)}
          >
            {preset.label}
          </Button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">After</Label>
          <Input
            type="date"
            value={startDate}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => onStartDateChange(e.target.value)}
            className="h-8 text-sm"
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">Before</Label>
          <Input
            type="date"
            value={endDate}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => onEndDateChange(e.target.value)}
            className="h-8 text-sm"
          />
        </div>
      </div>
    </div>
  )
}
