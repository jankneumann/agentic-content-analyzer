/**
 * SourceFilter Component
 *
 * Multi-select picker for content source types.
 * Displays checkboxes with source labels and icons.
 */

import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import type { ContentSource } from "@/types"

const SOURCE_OPTIONS: { value: ContentSource; label: string }[] = [
  { value: "gmail", label: "Gmail" },
  { value: "rss", label: "RSS" },
  { value: "youtube", label: "YouTube" },
  { value: "podcast", label: "Podcast" },
  { value: "file_upload", label: "File Upload" },
  { value: "webpage", label: "Webpage" },
  { value: "manual", label: "Manual" },
  { value: "other", label: "Other" },
]

interface SourceFilterProps {
  selected: ContentSource[]
  onChange: (sources: ContentSource[]) => void
}

export function SourceFilter({ selected, onChange }: SourceFilterProps) {
  const toggleSource = (source: ContentSource) => {
    if (selected.includes(source)) {
      onChange(selected.filter((s) => s !== source))
    } else {
      onChange([...selected, source])
    }
  }

  const selectAll = () => onChange(SOURCE_OPTIONS.map((o) => o.value))
  const clearAll = () => onChange([])

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-medium">Source Types</Label>
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={selectAll}>
            All
          </Button>
          <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={clearAll}>
            Clear
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {SOURCE_OPTIONS.map(({ value, label }) => (
          <label
            key={value}
            className="flex items-center gap-2 rounded-md border p-2 cursor-pointer hover:bg-muted/50"
          >
            <Checkbox
              checked={selected.includes(value)}
              onCheckedChange={() => toggleSource(value)}
            />
            <span className="text-sm">{label}</span>
          </label>
        ))}
      </div>
    </div>
  )
}
