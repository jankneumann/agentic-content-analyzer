/**
 * SortableTableHead Component
 *
 * A clickable table header cell that supports sorting functionality.
 * Displays sort direction indicators and handles tri-state toggle:
 * unsorted → ascending → descending → unsorted
 *
 * @example
 * ```tsx
 * <SortableTableHead
 *   column="title"
 *   label="Title"
 *   currentSort={filters.sort_by}
 *   currentOrder={filters.sort_order}
 *   onSort={(column, order) => setFilters({ ...filters, sort_by: column, sort_order: order })}
 * />
 * ```
 */

import * as React from "react"
import { ArrowUp, ArrowDown, ArrowUpDown } from "lucide-react"

import { cn } from "@/lib/utils"
import type { SortOrder } from "@/types"

export interface SortableTableHeadProps
  extends Omit<React.ComponentProps<"th">, "onClick"> {
  /** Column identifier (API field name) */
  column: string
  /** Display label for the column */
  label: string
  /** Currently sorted column (if any) */
  currentSort?: string
  /** Current sort direction */
  currentOrder?: SortOrder
  /** Callback when sort changes. Pass undefined for order to clear sort. */
  onSort: (column: string, order: SortOrder | undefined) => void
}

/**
 * Get the next sort order in the tri-state cycle
 * unsorted → asc → desc → unsorted
 */
function getNextSortOrder(
  column: string,
  currentSort?: string,
  currentOrder?: SortOrder
): SortOrder | undefined {
  // If clicking a different column, start with ascending
  if (currentSort !== column) {
    return "asc"
  }

  // Tri-state toggle for same column
  if (currentOrder === "asc") {
    return "desc"
  }
  if (currentOrder === "desc") {
    return undefined // Clear sort
  }
  return "asc" // Start fresh
}

/**
 * Get aria-sort value for accessibility
 */
function getAriaSort(
  column: string,
  currentSort?: string,
  currentOrder?: SortOrder
): "ascending" | "descending" | "none" | undefined {
  if (currentSort !== column) {
    return "none"
  }
  if (currentOrder === "asc") {
    return "ascending"
  }
  if (currentOrder === "desc") {
    return "descending"
  }
  return "none"
}

export function SortableTableHead({
  column,
  label,
  currentSort,
  currentOrder,
  onSort,
  className,
  ...props
}: SortableTableHeadProps) {
  const isActive = currentSort === column
  const ariaSort = getAriaSort(column, currentSort, currentOrder)

  const handleClick = () => {
    const nextOrder = getNextSortOrder(column, currentSort, currentOrder)
    onSort(column, nextOrder)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault()
      handleClick()
    }
  }

  // Determine which icon to show
  const SortIcon = React.useMemo(() => {
    if (!isActive) {
      return ArrowUpDown // Neutral indicator for sortable but unsorted
    }
    if (currentOrder === "asc") {
      return ArrowUp
    }
    if (currentOrder === "desc") {
      return ArrowDown
    }
    return ArrowUpDown
  }, [isActive, currentOrder])

  return (
    <th
      data-slot="table-head"
      role="columnheader"
      aria-sort={ariaSort}
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={cn(
        // Base styles from TableHead
        "text-foreground h-10 px-2 text-left align-middle font-medium whitespace-nowrap",
        // Interactive styles
        "cursor-pointer select-none",
        "hover:bg-muted/50 focus:bg-muted/50 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1",
        "transition-colors",
        // Active state
        isActive && "bg-muted/30",
        className
      )}
      {...props}
    >
      <div className="flex items-center gap-1">
        <span>{label}</span>
        <SortIcon
          className={cn(
            "h-4 w-4 shrink-0",
            isActive ? "text-foreground" : "text-muted-foreground/50"
          )}
          aria-hidden="true"
        />
      </div>
    </th>
  )
}

/**
 * Hook for managing sort state in filter objects
 *
 * @example
 * ```tsx
 * const { sortBy, sortOrder, handleSort, clearSort } = useSortState(filters, setFilters)
 * ```
 */
export function useSortState<T extends { sort_by?: string; sort_order?: SortOrder }>(
  filters: T,
  setFilters: React.Dispatch<React.SetStateAction<T>>,
  options?: {
    /** Reset pagination when sort changes */
    resetPagination?: { page?: number; offset?: number }
  }
) {
  const handleSort = React.useCallback(
    (column: string, order: SortOrder | undefined) => {
      setFilters((prev) => ({
        ...prev,
        sort_by: order ? column : undefined,
        sort_order: order,
        // Reset pagination if specified
        ...(options?.resetPagination && {
          page: options.resetPagination.page,
          offset: options.resetPagination.offset,
        }),
      }))
    },
    [setFilters, options?.resetPagination]
  )

  const clearSort = React.useCallback(() => {
    setFilters((prev) => ({
      ...prev,
      sort_by: undefined,
      sort_order: undefined,
    }))
  }, [setFilters])

  return {
    sortBy: filters.sort_by,
    sortOrder: filters.sort_order,
    handleSort,
    clearSort,
  }
}

export default SortableTableHead
