/**
 * Normalize capability-driven form values for native inputs.
 *
 * JSON Schema defaults are often `null`. Chromium warns when a number,
 * date, or datetime-local input receives `null` / `"null"`. These helpers
 * always return an empty string or a value the control can parse.
 */

import type { CapabilityField } from "@/generated/workflow-contracts"

export function isMissingControlValue(value: unknown): boolean {
  return value === null || value === undefined
}

export function numberControlValue(value: unknown): string {
  if (isMissingControlValue(value) || value === "") return ""
  if (typeof value === "number" && Number.isFinite(value)) return String(value)
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? value : ""
  }
  return ""
}

export function dateControlValue(value: unknown): string {
  if (isMissingControlValue(value) || value === "") return ""
  if (typeof value !== "string") return ""
  const match = value.match(/^(\d{4}-\d{2}-\d{2})/)
  return match?.[1] ?? ""
}

export function datetimeLocalControlValue(value: unknown): string {
  if (isMissingControlValue(value) || value === "") return ""
  if (typeof value !== "string") return ""
  const local = value.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})/)
  if (local) return local[1]
  const parsed = Date.parse(value)
  if (Number.isNaN(parsed)) return ""
  const date = new Date(parsed)
  const pad = (part: number) => String(part).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function textControlValue(value: unknown): string {
  if (isMissingControlValue(value)) return ""
  if (typeof value === "string") return value
  if (typeof value === "number" && Number.isFinite(value)) return String(value)
  return ""
}

export function capabilityInputValue(
  field: Pick<CapabilityField, "type" | "format">,
  value: unknown
): string {
  if (field.format === "date-time") return datetimeLocalControlValue(value)
  if (field.format === "date") return dateControlValue(value)
  if (field.type === "integer" || field.type === "number") {
    return numberControlValue(value)
  }
  return textControlValue(value)
}

export function initialCapabilityValues(
  fields: Array<Pick<CapabilityField, "name" | "default">>,
  internalFields: Set<string>
): Record<string, unknown> {
  return Object.fromEntries(
    fields
      .filter(
        (field) =>
          !internalFields.has(field.name) && !isMissingControlValue(field.default)
      )
      .map((field) => [field.name, field.default])
  )
}
