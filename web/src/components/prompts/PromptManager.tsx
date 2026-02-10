/**
 * Prompt Manager Component
 *
 * Displays all LLM prompts grouped by category with collapsible sections.
 * Clicking a prompt opens the PromptEditor dialog.
 *
 * Features:
 * - Prompts grouped by category (pipeline, chat, etc.)
 * - Override indicator badges
 * - Search/filter by key or category
 * - Collapsible category groups
 */

import { useState, useMemo } from "react"
import {
  ChevronRight,
  Search,
  FileText,
  AlertCircle,
  RefreshCw,
  Pencil,
} from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { PromptEditor } from "./PromptEditor"
import { usePrompts } from "@/hooks/use-prompts"
import type { PromptInfo } from "@/types/prompt"

/** Group prompts by their category (first segment of the key) */
function groupByCategory(prompts: PromptInfo[]): Record<string, PromptInfo[]> {
  const groups: Record<string, PromptInfo[]> = {}
  for (const p of prompts) {
    const category = p.category
    if (!groups[category]) {
      groups[category] = []
    }
    groups[category].push(p)
  }
  // Sort each group by key
  for (const key of Object.keys(groups)) {
    groups[key].sort((a, b) => a.key.localeCompare(b.key))
  }
  return groups
}

/** Format a category name for display (e.g., "pipeline" -> "Pipeline") */
function formatCategory(category: string): string {
  return category.charAt(0).toUpperCase() + category.slice(1)
}

/** Format a prompt name for display (e.g., "user_template" -> "User Template") */
function formatName(name: string): string {
  return name
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")
}

export function PromptManager() {
  const { data, isLoading, isError, error, refetch } = usePrompts()
  const [search, setSearch] = useState("")
  const [selectedPrompt, setSelectedPrompt] = useState<PromptInfo | null>(null)
  const [openCategories, setOpenCategories] = useState<Set<string>>(new Set())

  // Filter prompts by search term
  const filteredPrompts = useMemo(() => {
    if (!data?.prompts) return []
    if (!search.trim()) return data.prompts
    const term = search.toLowerCase()
    return data.prompts.filter(
      (p) =>
        p.key.toLowerCase().includes(term) ||
        p.name.toLowerCase().includes(term) ||
        p.category.toLowerCase().includes(term)
    )
  }, [data?.prompts, search])

  // Group filtered prompts by category
  const grouped = useMemo(() => groupByCategory(filteredPrompts), [filteredPrompts])
  const categories = useMemo(
    () => Object.keys(grouped).sort(),
    [grouped]
  )

  // Count overrides
  const overrideCount = useMemo(
    () => data?.prompts?.filter((p) => p.has_override).length ?? 0,
    [data?.prompts]
  )

  const toggleCategory = (category: string) => {
    setOpenCategories((prev) => {
      const next = new Set(prev)
      if (next.has(category)) {
        next.delete(category)
      } else {
        next.add(category)
      }
      return next
    })
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    )
  }

  // Error state
  if (isError) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-dashed">
        <div className="text-center">
          <AlertCircle className="mx-auto h-10 w-10 text-destructive/50" />
          <p className="mt-2 text-sm text-muted-foreground">
            Failed to load prompts: {error?.message}
          </p>
          <Button className="mt-3" size="sm" variant="outline" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-3.5 w-3.5" />
            Retry
          </Button>
        </div>
      </div>
    )
  }

  // Empty state
  if (!data?.prompts?.length) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-dashed">
        <div className="text-center">
          <FileText className="mx-auto h-10 w-10 text-muted-foreground/50" />
          <p className="mt-2 text-sm text-muted-foreground">
            No prompts configured
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Search and summary bar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search prompts..."
            className="h-8 pl-8 text-sm"
          />
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground shrink-0">
          <span>{filteredPrompts.length} {filteredPrompts.length === 1 ? "prompt" : "prompts"}</span>
          {overrideCount > 0 && (
            <Badge variant="secondary" className="text-[10px]">
              {overrideCount} override{overrideCount !== 1 ? "s" : ""}
            </Badge>
          )}
        </div>
      </div>

      {/* Category groups */}
      <div className="space-y-2">
        {categories.map((category) => {
          const prompts = grouped[category]
          const categoryOverrides = prompts.filter((p) => p.has_override).length
          const isOpen = openCategories.has(category)

          return (
            <Collapsible
              key={category}
              open={isOpen}
              onOpenChange={() => toggleCategory(category)}
            >
              <CollapsibleTrigger asChild>
                <button
                  type="button"
                  className="flex w-full items-center gap-2 rounded-md border bg-card px-3 py-2.5 text-left hover:bg-accent/50 transition-colors"
                >
                  <ChevronRight
                    className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${
                      isOpen ? "rotate-90" : ""
                    }`}
                  />
                  <span className="text-sm font-medium">
                    {formatCategory(category)}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    ({prompts.length})
                  </span>
                  {categoryOverrides > 0 && (
                    <Badge variant="default" className="ml-auto text-[10px] px-1.5 py-0">
                      {categoryOverrides} override{categoryOverrides !== 1 ? "s" : ""}
                    </Badge>
                  )}
                </button>
              </CollapsibleTrigger>

              <CollapsibleContent>
                <div className="ml-6 mt-1 space-y-1">
                  {prompts.map((prompt) => (
                    <button
                      key={prompt.key}
                      type="button"
                      onClick={() => setSelectedPrompt(prompt)}
                      className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left hover:bg-accent/50 transition-colors group"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium truncate">
                            {formatName(prompt.name)}
                          </span>
                          {prompt.has_override && (
                            <Badge
                              variant="default"
                              className="text-[10px] px-1.5 py-0 shrink-0"
                            >
                              Override
                            </Badge>
                          )}
                          {prompt.version != null && (
                            <Badge
                              variant="outline"
                              className="text-[10px] px-1.5 py-0 shrink-0"
                            >
                              v{prompt.version}
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground font-mono truncate">
                          {prompt.key}
                        </p>
                      </div>
                      <Pencil className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                    </button>
                  ))}
                </div>
              </CollapsibleContent>
            </Collapsible>
          )
        })}
      </div>

      {/* No results from search */}
      {filteredPrompts.length === 0 && search && (
        <div className="flex h-32 items-center justify-center rounded-lg border border-dashed">
          <p className="text-sm text-muted-foreground">
            No prompts matching &ldquo;{search}&rdquo;
          </p>
        </div>
      )}

      {/* Editor dialog */}
      <PromptEditor
        promptKey={selectedPrompt?.key ?? null}
        promptInfo={selectedPrompt ?? undefined}
        onClose={() => setSelectedPrompt(null)}
      />
    </div>
  )
}
