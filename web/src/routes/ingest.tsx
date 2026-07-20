import * as React from "react"
import { createRoute } from "@tanstack/react-router"
import { useMutation, useQuery } from "@tanstack/react-query"
import { CalendarRange, FileUp, Loader2, Play, RefreshCw } from "lucide-react"
import { toast } from "sonner"

import { Route as rootRoute } from "./__root"
import { PageContainer } from "@/components/layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { useBackgroundTasks } from "@/contexts/BackgroundTasksContext"
import type {
  CapabilityField,
  IngestCommand,
  SourceCapability,
} from "@/generated/workflow-contracts"
import {
  getAllCapabilities,
  submitIngestion,
  submitPipeline,
  uploadFile,
} from "@/lib/api/workflows"

export const IngestRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "ingest",
  component: IngestPage,
})

type FormValues = Record<string, string | boolean | number | Array<string>>
const INTERNAL_FIELDS = new Set(["kind", "configured_sources"])

function initialValues(source: SourceCapability): FormValues {
  return Object.fromEntries(
    source.fields
      .filter(
        (field) =>
          !INTERNAL_FIELDS.has(field.name) && field.default !== undefined
      )
      .map((field) => [field.name, field.default as FormValues[string]])
  )
}

function InputField({
  field,
  value,
  onChange,
}: {
  field: CapabilityField
  value: FormValues[string] | undefined
  onChange: (value: FormValues[string] | undefined) => void
}) {
  const id = `source-field-${field.name}`
  const label = field.name
    .split("_")
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ")
  if (field.type === "boolean")
    return (
      <div className="flex items-start gap-2">
        <Checkbox
          id={id}
          checked={Boolean(value)}
          onCheckedChange={(checked) => onChange(checked === true)}
        />
        <div>
          <Label htmlFor={id}>{label}</Label>
          {field.description && (
            <p className="text-muted-foreground text-xs">{field.description}</p>
          )}
        </div>
      </div>
    )
  if (field.enum?.length)
    return (
      <div className="space-y-1.5">
        <Label htmlFor={id}>
          {label}
          {field.required ? " *" : ""}
        </Label>
        <Select value={String(value ?? "")} onValueChange={onChange}>
          <SelectTrigger id={id}>
            <SelectValue placeholder={`Select ${label.toLowerCase()}`} />
          </SelectTrigger>
          <SelectContent>
            {field.enum.map((option) => (
              <SelectItem key={option} value={option}>
                {option.replaceAll("_", " ")}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    )
  if (field.type === "array")
    return (
      <div className="space-y-1.5">
        <Label htmlFor={id}>
          {label}
          {field.required ? " *" : ""}
        </Label>
        <Textarea
          id={id}
          value={Array.isArray(value) ? value.join("\n") : ""}
          onChange={(event) =>
            onChange(
              event.target.value
                .split("\n")
                .map((item) => item.trim())
                .filter(Boolean)
            )
          }
          placeholder="One value per line"
        />
      </div>
    )
  if (["prompt", "notes", "custom_instructions"].includes(field.name))
    return (
      <div className="space-y-1.5">
        <Label htmlFor={id}>
          {label}
          {field.required ? " *" : ""}
        </Label>
        <Textarea
          id={id}
          required={field.required}
          value={String(value ?? "")}
          onChange={(event) => onChange(event.target.value || undefined)}
        />
      </div>
    )
  const numeric = field.type === "integer" || field.type === "number"
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>
        {label}
        {field.required ? " *" : ""}
      </Label>
      <Input
        id={id}
        type={
          field.format === "date-time"
            ? "datetime-local"
            : numeric
              ? "number"
              : field.format === "uri"
                ? "url"
                : "text"
        }
        required={field.required}
        value={value === undefined ? "" : String(value)}
        min={
          numeric && field.constraints?.minimum !== undefined
            ? Number(field.constraints.minimum)
            : undefined
        }
        max={
          numeric && field.constraints?.maximum !== undefined
            ? Number(field.constraints.maximum)
            : undefined
        }
        onChange={(event) =>
          onChange(
            event.target.value === ""
              ? undefined
              : numeric
                ? Number(event.target.value)
                : event.target.value
          )
        }
        aria-describedby={field.description ? `${id}-help` : undefined}
      />
      {field.description && (
        <p id={`${id}-help`} className="text-muted-foreground text-xs">
          {field.description}
        </p>
      )}
    </div>
  )
}

function SourceForm({ source }: { source: SourceCapability }) {
  const { addOperation } = useBackgroundTasks()
  const [values, setValues] = React.useState<FormValues>(() =>
    initialValues(source)
  )
  const [files, setFiles] = React.useState<File[]>([])
  const mutation = useMutation({
    mutationFn: async () => {
      const payload = {
        kind: source.key,
        ...values,
      } as unknown as IngestCommand
      if (source.key === "files") {
        const uploads = await Promise.all(files.map((file) => uploadFile(file)))
        return submitIngestion({
          kind: "files",
          upload_ids: uploads.map((upload) => upload.id),
          force_reprocess: Boolean(values.force_reprocess),
        })
      }
      return submitIngestion(payload)
    },
    onSuccess: (operation) => {
      addOperation(operation)
      toast.success(`${source.display_name} ingestion queued`)
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "Unable to submit ingestion"
      ),
  })
  const visibleFields = source.fields.filter(
    (field) => !INTERNAL_FIELDS.has(field.name) && field.name !== "upload_ids"
  )
  const invalid =
    visibleFields.some((field) => {
      const value = values[field.name]
      if (
        field.required &&
        (value === undefined ||
          value === "" ||
          (Array.isArray(value) && value.length === 0))
      )
        return true
      if (
        typeof value === "number" &&
        field.constraints?.minimum !== undefined &&
        value < Number(field.constraints.minimum)
      )
        return true
      return false
    }) ||
    (source.key === "files" && files.length === 0)
  return (
    <form
      className="border-b py-4 last:border-b-0"
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-medium">{source.display_name}</h2>
          <div className="mt-1 flex flex-wrap gap-1">
            {source.emitted_sources.map((item) => (
              <Badge key={item} variant="secondary">
                {item}
              </Badge>
            ))}
            {source.scheduled && <Badge variant="outline">scheduled</Badge>}
          </div>
        </div>
        <Button
          type="submit"
          size="sm"
          disabled={invalid || mutation.isPending}
        >
          {mutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Play className="mr-2 h-4 w-4" />
          )}
          Run
        </Button>
      </div>
      {source.key === "files" && (
        <div className="mt-4 space-y-1.5">
          <Label htmlFor="ingestion-files">Files *</Label>
          <Input
            id="ingestion-files"
            type="file"
            multiple
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
          />
          <p className="text-muted-foreground text-xs">
            {files.length
              ? `${files.length} selected`
              : "Uploads are stored before the durable ingestion operation is submitted."}
          </p>
        </div>
      )}
      {visibleFields.length > 0 && (
        <div className="mt-4 grid min-h-24 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {visibleFields.map((field) => (
            <InputField
              key={field.name}
              field={field}
              value={values[field.name]}
              onChange={(value) =>
                setValues((current) => {
                  const next = { ...current }
                  if (value === undefined) delete next[field.name]
                  else next[field.name] = value
                  return next
                })
              }
            />
          ))}
        </div>
      )}
    </form>
  )
}

function PipelineForm() {
  const { addOperation } = useBackgroundTasks()
  const today = new Date().toISOString().slice(0, 10)
  const [period, setPeriod] = React.useState<"daily" | "weekly">("daily")
  const [end, setEnd] = React.useState(today)
  const mutation = useMutation({
    mutationFn: () => {
      const periodEnd = new Date(`${end}T23:59:59Z`)
      const periodStart = new Date(periodEnd)
      periodStart.setUTCDate(
        periodStart.getUTCDate() - (period === "daily" ? 1 : 7)
      )
      return submitPipeline({
        period,
        period_start: periodStart.toISOString(),
        period_end: periodEnd.toISOString(),
        continue_on_source_error: true,
      })
    },
    onSuccess: (operation) => {
      addOperation(operation)
      toast.success("Pipeline queued")
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "Unable to submit pipeline"
      ),
  })
  return (
    <section className="mb-6 border-b pb-5">
      <div className="flex items-center gap-2">
        <CalendarRange className="h-5 w-5" />
        <h2 className="font-medium">Full pipeline</h2>
      </div>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="pipeline-period">Period</Label>
          <Select
            value={period}
            onValueChange={(value) => setPeriod(value as "daily" | "weekly")}
          >
            <SelectTrigger id="pipeline-period" className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="daily">Daily</SelectItem>
              <SelectItem value="weekly">Weekly</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="pipeline-end">Period ending</Label>
          <Input
            id="pipeline-end"
            type="date"
            value={end}
            onChange={(event) => setEnd(event.target.value)}
          />
        </div>
        <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          {mutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Run pipeline
        </Button>
      </div>
    </section>
  )
}

function IngestPage() {
  const capabilities = useQuery({
    queryKey: ["workflow-capabilities"],
    queryFn: getAllCapabilities,
    staleTime: 5 * 60_000,
  })
  const [selectedSource, setSelectedSource] = React.useState<string>()
  const frontendSources =
    capabilities.data?.source_commands.filter((source) =>
      source.transports.includes("frontend")
    ) ?? []
  const activeSource =
    frontendSources.find((source) => source.key === selectedSource) ??
    frontendSources[0]
  return (
    <PageContainer
      title="Ingestion"
      description="Submit durable source and pipeline operations"
    >
      {capabilities.isLoading && (
        <div className="flex items-center gap-2 py-8" role="status">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading source capabilities
        </div>
      )}
      {capabilities.isError && (
        <div className="border-destructive border p-4" role="alert">
          <p className="font-medium">Capabilities unavailable</p>
          <p className="text-muted-foreground text-sm">
            {capabilities.error.message}
          </p>
          <Button
            className="mt-3"
            variant="outline"
            onClick={() => void capabilities.refetch()}
          >
            Retry
          </Button>
        </div>
      )}
      {capabilities.data && (
        <>
          <PipelineForm />
          <section aria-labelledby="source-operations">
            <div className="flex items-center gap-2">
              <FileUp className="h-5 w-5" />
              <h2 id="source-operations" className="font-medium">
                Source operation
              </h2>
            </div>
            <div className="mt-3 max-w-sm space-y-1.5">
              <Label htmlFor="source-command">Source</Label>
              <Select
                value={activeSource?.key}
                onValueChange={setSelectedSource}
              >
                <SelectTrigger id="source-command">
                  <SelectValue placeholder="Select a source" />
                </SelectTrigger>
                <SelectContent>
                  {frontendSources.map((source) => (
                    <SelectItem key={source.key} value={source.key}>
                      {source.display_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="mt-2 min-h-64">
              {activeSource && (
                <SourceForm key={activeSource.key} source={activeSource} />
              )}
            </div>
          </section>
        </>
      )}
    </PageContainer>
  )
}
