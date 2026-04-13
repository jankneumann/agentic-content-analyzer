/**
 * FilterChip Component
 *
 * A small chip displaying a filter label and value, with a remove button.
 * Used to show active filters in the query builder.
 */

import { X } from "lucide-react"
import { Badge } from "@/components/ui/badge"

interface FilterChipProps {
  label: string
  value: string
  onRemove: () => void
}

export function FilterChip({ label, value, onRemove }: FilterChipProps) {
  return (
    <Badge variant="secondary" className="flex items-center gap-1 pr-1">
      <span className="text-xs text-muted-foreground">{label}:</span>
      <span className="text-xs font-medium">{value}</span>
      <button
        type="button"
        onClick={onRemove}
        className="ml-0.5 rounded-sm p-0.5 hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={`Remove ${label} filter`}
      >
        <X className="h-3 w-3" />
      </button>
    </Badge>
  )
}
