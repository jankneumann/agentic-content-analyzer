/**
 * ThemeTableView Component
 *
 * A sortable, filterable table view for theme analysis results.
 * Supports category/trend filtering via badge chips, column sorting,
 * and expandable rows for detailed theme information.
 *
 * @example
 * ```tsx
 * <ThemeTableView themes={analysisResult.themes} />
 * ```
 */

import { useState, useMemo, useCallback } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"

import { cn } from "@/lib/utils"
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
  SortableTableHead,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import type { SortOrder } from "@/types"
import type { ThemeData, ThemeCategory, ThemeTrend } from "@/types/theme"

interface ThemeTableViewProps {
  themes: ThemeData[]
}

/** Human-readable labels for theme categories */
const CATEGORY_LABELS: Record<ThemeCategory, string> = {
  ml_ai: "ML/AI",
  devops_infra: "DevOps/Infra",
  data_engineering: "Data Engineering",
  business_strategy: "Business Strategy",
  tools_products: "Tools/Products",
  research_academia: "Research",
  security: "Security",
  other: "Other",
}

/** Human-readable labels for trend values */
const TREND_LABELS: Record<ThemeTrend, string> = {
  emerging: "Emerging",
  growing: "Growing",
  established: "Established",
  declining: "Declining",
  one_off: "One-off",
}

/** Badge variant mapping for trends */
const TREND_VARIANTS: Record<ThemeTrend, "default" | "secondary" | "destructive" | "outline"> = {
  emerging: "default",
  growing: "default",
  established: "secondary",
  declining: "destructive",
  one_off: "outline",
}

type SortColumn =
  | "name"
  | "category"
  | "trend"
  | "relevance_score"
  | "strategic_relevance"
  | "tactical_relevance"
  | "mention_count"

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

function compareValues(a: ThemeData, b: ThemeData, column: SortColumn, order: SortOrder): number {
  let aVal: string | number
  let bVal: string | number

  switch (column) {
    case "name":
      aVal = a.name.toLowerCase()
      bVal = b.name.toLowerCase()
      break
    case "category":
      aVal = a.category
      bVal = b.category
      break
    case "trend":
      aVal = a.trend
      bVal = b.trend
      break
    case "relevance_score":
      aVal = a.relevance_score
      bVal = b.relevance_score
      break
    case "strategic_relevance":
      aVal = a.strategic_relevance
      bVal = b.strategic_relevance
      break
    case "tactical_relevance":
      aVal = a.tactical_relevance
      bVal = b.tactical_relevance
      break
    case "mention_count":
      aVal = a.mention_count
      bVal = b.mention_count
      break
  }

  if (aVal < bVal) return order === "asc" ? -1 : 1
  if (aVal > bVal) return order === "asc" ? 1 : -1
  return 0
}

export function ThemeTableView({ themes }: ThemeTableViewProps) {
  const [sortColumn, setSortColumn] = useState<SortColumn>("relevance_score")
  const [sortOrder, setSortOrder] = useState<SortOrder | undefined>("desc")
  const [categoryFilters, setCategoryFilters] = useState<Set<ThemeCategory>>(new Set())
  const [trendFilters, setTrendFilters] = useState<Set<ThemeTrend>>(new Set())
  const [expandedRow, setExpandedRow] = useState<number | null>(null)

  // Distinct categories and trends from the data
  const distinctCategories = useMemo(
    () => [...new Set(themes.map((t) => t.category))].sort(),
    [themes]
  )

  const distinctTrends = useMemo(
    () => [...new Set(themes.map((t) => t.trend))].sort(),
    [themes]
  )

  // Filter themes
  const filteredThemes = useMemo(() => {
    let result = themes
    if (categoryFilters.size > 0) {
      result = result.filter((t) => categoryFilters.has(t.category))
    }
    if (trendFilters.size > 0) {
      result = result.filter((t) => trendFilters.has(t.trend))
    }
    return result
  }, [themes, categoryFilters, trendFilters])

  // Sort filtered themes
  const sortedThemes = useMemo(() => {
    if (!sortOrder || !sortColumn) return filteredThemes
    return [...filteredThemes].sort((a, b) => compareValues(a, b, sortColumn, sortOrder))
  }, [filteredThemes, sortColumn, sortOrder])

  const handleSort = useCallback((column: string, order: SortOrder | undefined) => {
    setSortColumn(column as SortColumn)
    setSortOrder(order)
  }, [])

  const toggleCategoryFilter = useCallback((category: ThemeCategory) => {
    setCategoryFilters((prev) => {
      const next = new Set(prev)
      if (next.has(category)) {
        next.delete(category)
      } else {
        next.add(category)
      }
      return next
    })
    setExpandedRow(null)
  }, [])

  const toggleTrendFilter = useCallback((trend: ThemeTrend) => {
    setTrendFilters((prev) => {
      const next = new Set(prev)
      if (next.has(trend)) {
        next.delete(trend)
      } else {
        next.add(trend)
      }
      return next
    })
    setExpandedRow(null)
  }, [])

  const toggleExpanded = useCallback((index: number) => {
    setExpandedRow((prev) => (prev === index ? null : index))
  }, [])

  if (themes.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        No themes to display
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Filter chips */}
      <div className="space-y-2">
        {/* Category filters */}
        {distinctCategories.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-muted-foreground">Category:</span>
            {distinctCategories.map((category) => (
              <Badge
                key={category}
                variant={categoryFilters.has(category) ? "default" : "outline"}
                className="cursor-pointer"
                onClick={() => toggleCategoryFilter(category)}
              >
                {CATEGORY_LABELS[category]}
              </Badge>
            ))}
          </div>
        )}

        {/* Trend filters */}
        {distinctTrends.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-muted-foreground">Trend:</span>
            {distinctTrends.map((trend) => (
              <Badge
                key={trend}
                variant={trendFilters.has(trend) ? "default" : "outline"}
                className="cursor-pointer"
                onClick={() => toggleTrendFilter(trend)}
              >
                {TREND_LABELS[trend]}
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <th className="w-8" />
            <SortableTableHead
              column="name"
              label="Name"
              currentSort={sortColumn}
              currentOrder={sortOrder}
              onSort={handleSort}
            />
            <SortableTableHead
              column="category"
              label="Category"
              currentSort={sortColumn}
              currentOrder={sortOrder}
              onSort={handleSort}
            />
            <SortableTableHead
              column="trend"
              label="Trend"
              currentSort={sortColumn}
              currentOrder={sortOrder}
              onSort={handleSort}
            />
            <SortableTableHead
              column="relevance_score"
              label="Relevance"
              currentSort={sortColumn}
              currentOrder={sortOrder}
              onSort={handleSort}
            />
            <SortableTableHead
              column="strategic_relevance"
              label="Strategic"
              currentSort={sortColumn}
              currentOrder={sortOrder}
              onSort={handleSort}
            />
            <SortableTableHead
              column="tactical_relevance"
              label="Tactical"
              currentSort={sortColumn}
              currentOrder={sortOrder}
              onSort={handleSort}
            />
            <SortableTableHead
              column="mention_count"
              label="Mentions"
              currentSort={sortColumn}
              currentOrder={sortOrder}
              onSort={handleSort}
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedThemes.length === 0 ? (
            <TableRow>
              <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                No themes match the selected filters
              </TableCell>
            </TableRow>
          ) : (
            sortedThemes.map((theme, index) => {
              const isExpanded = expandedRow === index
              return (
                <ThemeRow
                  key={`${theme.name}-${index}`}
                  theme={theme}
                  isExpanded={isExpanded}
                  onToggle={() => toggleExpanded(index)}
                />
              )
            })
          )}
        </TableBody>
      </Table>
    </div>
  )
}

/**
 * Individual theme row with expand/collapse support.
 * Extracted for readability; renders the main row and optional detail row.
 */
function ThemeRow({
  theme,
  isExpanded,
  onToggle,
}: {
  theme: ThemeData
  isExpanded: boolean
  onToggle: () => void
}) {
  return (
    <>
      <TableRow
        className={cn("cursor-pointer", isExpanded && "bg-muted/30")}
        onClick={onToggle}
      >
        <TableCell className="w-8 px-2">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </TableCell>
        <TableCell className="font-medium">{theme.name}</TableCell>
        <TableCell>
          <Badge variant="secondary">{CATEGORY_LABELS[theme.category]}</Badge>
        </TableCell>
        <TableCell>
          <Badge variant={TREND_VARIANTS[theme.trend]}>{TREND_LABELS[theme.trend]}</Badge>
        </TableCell>
        <TableCell className="text-right">{formatPercent(theme.relevance_score)}</TableCell>
        <TableCell className="text-right">{formatPercent(theme.strategic_relevance)}</TableCell>
        <TableCell className="text-right">{formatPercent(theme.tactical_relevance)}</TableCell>
        <TableCell className="text-right">{theme.mention_count}</TableCell>
      </TableRow>

      {isExpanded && (
        <TableRow className="bg-muted/20 hover:bg-muted/20">
          <TableCell colSpan={8} className="p-4">
            <ThemeDetails theme={theme} />
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

/**
 * Expanded detail view for a single theme.
 * Shows description, key points, historical context, and related themes.
 */
function ThemeDetails({ theme }: { theme: ThemeData }) {
  return (
    <div className="space-y-4 text-sm">
      {/* Description */}
      <div>
        <h4 className="font-medium mb-1">Description</h4>
        <p className="text-muted-foreground">{theme.description}</p>
      </div>

      {/* Key Points */}
      {theme.key_points.length > 0 && (
        <div>
          <h4 className="font-medium mb-1">Key Points</h4>
          <ul className="list-disc list-inside space-y-1 text-muted-foreground">
            {theme.key_points.map((point, i) => (
              <li key={i}>{point}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Historical Context */}
      {theme.historical_context?.evolution_summary && (
        <div>
          <h4 className="font-medium mb-1">Evolution</h4>
          <p className="text-muted-foreground">{theme.historical_context.evolution_summary}</p>
        </div>
      )}

      {/* Related Themes */}
      {theme.related_themes.length > 0 && (
        <div>
          <h4 className="font-medium mb-1">Related Themes</h4>
          <div className="flex flex-wrap gap-1">
            {theme.related_themes.map((related) => (
              <Badge key={related} variant="outline">
                {related}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default ThemeTableView
