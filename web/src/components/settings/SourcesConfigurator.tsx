/**
 * Sources Configurator Component
 *
 * Lets users view, add, enable/disable, and delete ingestion sources.
 * Sources are grouped by type. Each row shows its name/url, an origin badge
 * (yaml vs db) and an enable/disable toggle. DB-origin sources can be deleted;
 * YAML-origin sources can only be disabled (which creates a server-side shadow).
 *
 * Mirrors ModelConfigurator: react-query fetch, loading skeleton, error state
 * with retry, empty state, source/origin badges, per-row controls, mutations
 * with cache invalidation, and sonner toasts.
 */

import { useMemo, useState } from "react"
import {
  AlertCircle,
  RefreshCw,
  Plus,
  Trash2,
  Loader2,
} from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  useSources,
  useUpsertSource,
  useDeleteSource,
  useSetSourceEnabled,
} from "@/hooks/use-settings"
import { isApiError } from "@/lib/api/client"
import type { SourceInfo, SourceType } from "@/types/settings"

// ── Per-type field definitions ──

interface FieldDef {
  /** Config key sent to the backend */
  key: string
  label: string
  placeholder?: string
  required?: boolean
  /** "list" inputs accept a comma-separated string split into string[] */
  kind?: "text" | "number" | "list"
}

/** Field forms per source type, exposing the full field set for each. */
const SOURCE_FIELDS: Record<SourceType, FieldDef[]> = {
  blog: [
    { key: "url", label: "URL", placeholder: "https://example.com/blog", required: true },
    { key: "name", label: "Name", placeholder: "Example Blog" },
    { key: "tags", label: "Tags", placeholder: "ai, research", kind: "list" },
    { key: "max_entries", label: "Max entries", placeholder: "10", kind: "number" },
    { key: "link_selector", label: "Link selector", placeholder: "article a" },
    { key: "link_pattern", label: "Link pattern", placeholder: "/posts/.*" },
    {
      key: "content_filter_strategy",
      label: "Content filter strategy",
      placeholder: "default",
    },
  ],
  rss: [
    { key: "url", label: "URL", placeholder: "https://example.com/feed.xml", required: true },
    { key: "name", label: "Name", placeholder: "Example Feed" },
    { key: "tags", label: "Tags", placeholder: "ai, news", kind: "list" },
    { key: "max_entries", label: "Max entries", placeholder: "10", kind: "number" },
  ],
  substack: [
    { key: "url", label: "URL", placeholder: "https://example.substack.com/feed", required: true },
    { key: "name", label: "Name", placeholder: "Example Substack" },
    { key: "tags", label: "Tags", placeholder: "ai, newsletter", kind: "list" },
    { key: "max_entries", label: "Max entries", placeholder: "10", kind: "number" },
  ],
  podcast: [
    { key: "url", label: "URL", placeholder: "https://example.com/podcast.rss", required: true },
    { key: "name", label: "Name", placeholder: "Example Podcast" },
    { key: "tags", label: "Tags", placeholder: "ai, audio", kind: "list" },
    { key: "max_entries", label: "Max entries", placeholder: "10", kind: "number" },
  ],
  youtube_rss: [
    { key: "url", label: "URL", placeholder: "https://www.youtube.com/feeds/...", required: true },
    { key: "name", label: "Name", placeholder: "Example Channel" },
    { key: "tags", label: "Tags", placeholder: "ai, video", kind: "list" },
    { key: "max_entries", label: "Max entries", placeholder: "10", kind: "number" },
  ],
  youtube_playlist: [
    { key: "id", label: "Playlist ID", placeholder: "PLxxxxxxxx", required: true },
    { key: "name", label: "Name", placeholder: "Example Playlist" },
    { key: "tags", label: "Tags", placeholder: "ai, video", kind: "list" },
    { key: "max_entries", label: "Max entries", placeholder: "10", kind: "number" },
  ],
  youtube_channel: [
    { key: "channel_id", label: "Channel ID", placeholder: "UCxxxxxxxx", required: true },
    { key: "name", label: "Name", placeholder: "Example Channel" },
    { key: "tags", label: "Tags", placeholder: "ai, video", kind: "list" },
    { key: "max_entries", label: "Max entries", placeholder: "10", kind: "number" },
  ],
  gmail: [
    { key: "query", label: "Query", placeholder: "label:newsletters", required: true },
    { key: "name", label: "Name", placeholder: "Newsletters" },
    { key: "tags", label: "Tags", placeholder: "ai, email", kind: "list" },
  ],
  scholar: [
    { key: "query", label: "Query", placeholder: "large language models", required: true },
    { key: "name", label: "Name", placeholder: "LLM Research" },
    { key: "tags", label: "Tags", placeholder: "ai, papers", kind: "list" },
  ],
  arxiv: [
    { key: "query", label: "Query", placeholder: "cat:cs.CL", required: true },
    { key: "name", label: "Name", placeholder: "arXiv CL" },
    { key: "tags", label: "Tags", placeholder: "ai, papers", kind: "list" },
    { key: "max_entries", label: "Max entries", placeholder: "10", kind: "number" },
  ],
  huggingface_papers: [
    { key: "name", label: "Name", placeholder: "HF Daily Papers" },
    { key: "tags", label: "Tags", placeholder: "ai, papers", kind: "list" },
    { key: "max_entries", label: "Max entries", placeholder: "10", kind: "number" },
  ],
  websearch: [
    { key: "query", label: "Query", placeholder: "latest AI news", required: true },
    { key: "name", label: "Name", placeholder: "AI News Search" },
    { key: "tags", label: "Tags", placeholder: "ai, news", kind: "list" },
    { key: "max_entries", label: "Max entries", placeholder: "10", kind: "number" },
  ],
}

const SOURCE_TYPES = Object.keys(SOURCE_FIELDS) as SourceType[]

/** Format a source type for display (e.g., "youtube_playlist" -> "Youtube Playlist") */
function formatType(type: string): string {
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")
}

/** Origin badge color classes */
const ORIGIN_BADGE_CLASSES: Record<SourceInfo["origin"], string> = {
  yaml: "border-border bg-muted text-muted-foreground",
  db: "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-400",
}

// ── Add-source dialog ──

function AddSourceDialog() {
  const upsert = useUpsertSource()
  const [open, setOpen] = useState(false)
  const [type, setType] = useState<SourceType>("rss")
  const [values, setValues] = useState<Record<string, string>>({})

  const fields = SOURCE_FIELDS[type]

  const reset = () => {
    setType("rss")
    setValues({})
  }

  const handleSubmit = () => {
    // Client-side required field validation
    const missing = fields.filter((f) => f.required && !values[f.key]?.trim())
    if (missing.length > 0) {
      toast.error(`Missing required field: ${missing.map((f) => f.label).join(", ")}`)
      return
    }

    // Build the config object, coercing list/number fields and dropping blanks
    const config: Record<string, unknown> = { type }
    for (const field of fields) {
      const raw = values[field.key]?.trim()
      if (!raw) continue
      if (field.kind === "list") {
        config[field.key] = raw
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
      } else if (field.kind === "number") {
        const n = Number(raw)
        if (!Number.isNaN(n)) config[field.key] = n
      } else {
        config[field.key] = raw
      }
    }

    upsert.mutate(
      { config },
      {
        onSuccess: (result) => {
          toast.success(`Added source ${result.source_key}`)
          setOpen(false)
          reset()
        },
        onError: (error) => {
          const message = isApiError(error)
            ? error.message
            : "Failed to add source"
          toast.error(message)
        },
      }
    )
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) reset()
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="mr-2 h-3.5 w-3.5" />
          Add source
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add ingestion source</DialogTitle>
          <DialogDescription>
            Choose a source type and fill in its fields. Required fields are
            marked with an asterisk.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="source-type">Type</Label>
            <Select
              value={type}
              onValueChange={(next) => {
                setType(next as SourceType)
                setValues({})
              }}
            >
              <SelectTrigger id="source-type" className="w-full" size="sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SOURCE_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>
                    {formatType(t)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {fields.map((field) => (
            <div key={field.key} className="space-y-1.5">
              <Label htmlFor={`source-field-${field.key}`}>
                {field.label}
                {field.required && (
                  <span className="text-destructive"> *</span>
                )}
              </Label>
              <Input
                id={`source-field-${field.key}`}
                type={field.kind === "number" ? "number" : "text"}
                placeholder={field.placeholder}
                value={values[field.key] ?? ""}
                onChange={(e) =>
                  setValues((prev) => ({ ...prev, [field.key]: e.target.value }))
                }
              />
            </div>
          ))}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setOpen(false)
              reset()
            }}
            disabled={upsert.isPending}
          >
            Cancel
          </Button>
          <Button size="sm" onClick={handleSubmit} disabled={upsert.isPending}>
            {upsert.isPending && (
              <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
            )}
            Add
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Source row ──

function SourceRow({ source }: { source: SourceInfo }) {
  const setEnabled = useSetSourceEnabled()
  const deleteSource = useDeleteSource()

  const key = source.source_key
  const canMutate = Boolean(key)

  const handleToggle = (checked: boolean) => {
    if (!key) return
    setEnabled.mutate(
      { key, enabled: checked },
      {
        onSuccess: () =>
          toast.success(
            `${source.name || source.url} ${checked ? "enabled" : "disabled"}`
          ),
        onError: (error) => {
          const message = isApiError(error)
            ? error.message
            : "Failed to update source"
          toast.error(message)
        },
      }
    )
  }

  const handleDelete = () => {
    if (!key) return
    deleteSource.mutate(key, {
      onSuccess: () => toast.success(`Deleted ${source.name || source.url}`),
      onError: (error) => {
        const message = isApiError(error)
          ? error.message
          : "Failed to delete source"
        toast.error(message)
      },
    })
  }

  return (
    <div className="flex items-center gap-3 rounded-md border bg-card px-3 py-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">
            {source.name || source.url}
          </span>
          <Badge
            className={`px-1.5 py-0 text-[10px] ${ORIGIN_BADGE_CLASSES[source.origin]}`}
          >
            {source.origin}
          </Badge>
        </div>
        <p className="mt-0.5 truncate font-mono text-xs text-muted-foreground">
          {source.url}
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Switch
          checked={source.enabled}
          onCheckedChange={handleToggle}
          disabled={!canMutate || setEnabled.isPending}
          aria-label={`Toggle ${source.name || source.url}`}
        />
        {source.origin === "db" && (
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 shrink-0 p-0 text-destructive hover:text-destructive"
            onClick={handleDelete}
            disabled={!canMutate || deleteSource.isPending}
            aria-label={`Delete ${source.name || source.url}`}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
    </div>
  )
}

export function SourcesConfigurator() {
  const { data, isLoading, isError, error, refetch } = useSources()

  // Group sources by type for organized display
  const grouped = useMemo(() => {
    const groups: Record<string, SourceInfo[]> = {}
    for (const source of data?.sources ?? []) {
      ;(groups[source.type] ??= []).push(source)
    }
    return groups
  }, [data])

  const types = useMemo(() => Object.keys(grouped).sort(), [grouped])

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-dashed">
        <div className="text-center">
          <AlertCircle className="mx-auto h-10 w-10 text-destructive/50" />
          <p className="mt-2 text-sm text-muted-foreground">
            Failed to load sources: {error?.message}
          </p>
          <Button
            className="mt-3"
            size="sm"
            variant="outline"
            onClick={() => refetch()}
          >
            <RefreshCw className="mr-2 h-3.5 w-3.5" />
            Retry
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {data?.total_sources ?? 0} sources · {data?.enabled_sources ?? 0}{" "}
          enabled
        </p>
        <AddSourceDialog />
      </div>

      {types.length === 0 ? (
        <div className="flex h-48 items-center justify-center rounded-lg border border-dashed">
          <p className="text-sm text-muted-foreground">
            No sources configured yet
          </p>
        </div>
      ) : (
        types.map((type) => (
          <div key={type} className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {formatType(type)}
            </h3>
            <div className="space-y-2">
              {grouped[type].map((source, idx) => (
                <SourceRow
                  key={source.source_key ?? `${type}-${idx}`}
                  source={source}
                />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
