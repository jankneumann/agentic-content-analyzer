/**
 * StatusFilter Component
 *
 * Multi-select picker for content processing statuses.
 * Displays checkboxes with status badges.
 */

import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import type { ContentStatus } from "@/types"

const STATUS_OPTIONS: { value: ContentStatus; label: string; variant: "default" | "secondary" | "destructive" | "outline" }[] = [
  { value: "pending", label: "Pending", variant: "outline" },
  { value: "parsing", label: "Parsing", variant: "secondary" },
  { value: "parsed", label: "Parsed", variant: "secondary" },
  { value: "processing", label: "Processing", variant: "default" },
  { value: "completed", label: "Completed", variant: "default" },
  { value: "failed", label: "Failed", variant: "destructive" },
]

interface StatusFilterProps {
  selected: ContentStatus[]
  onChange: (statuses: ContentStatus[]) => void
}

export function StatusFilter({ selected, onChange }: StatusFilterProps) {
  const toggleStatus = (status: ContentStatus) => {
    if (selected.includes(status)) {
      onChange(selected.filter((s) => s !== status))
    } else {
      onChange([...selected, status])
    }
  }

  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">Status</Label>
      <div className="flex flex-wrap gap-2">
        {STATUS_OPTIONS.map(({ value, label, variant }) => (
          <label key={value} className="flex items-center gap-1.5 cursor-pointer">
            <Checkbox
              checked={selected.includes(value)}
              onCheckedChange={() => toggleStatus(value)}
            />
            <Badge variant={variant} className="text-xs">
              {label}
            </Badge>
          </label>
        ))}
      </div>
    </div>
  )
}
