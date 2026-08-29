import { describe, expect, it } from "vitest"

import {
  capabilityInputValue,
  dateControlValue,
  datetimeLocalControlValue,
  initialCapabilityValues,
  numberControlValue,
} from "../capability-form-values"

describe("capability form control values", () => {
  it("never feeds null into number, date, or datetime-local controls", () => {
    expect(numberControlValue(null)).toBe("")
    expect(numberControlValue(undefined)).toBe("")
    expect(dateControlValue(null)).toBe("")
    expect(datetimeLocalControlValue(null)).toBe("")
    expect(capabilityInputValue({ type: "integer" }, null)).toBe("")
    expect(
      capabilityInputValue({ type: "string", format: "date" }, null)
    ).toBe("")
    expect(
      capabilityInputValue({ type: "string", format: "date-time" }, null)
    ).toBe("")
  })

  it("keeps finite numbers and drops non-numeric junk", () => {
    expect(numberControlValue(0)).toBe("0")
    expect(numberControlValue(12)).toBe("12")
    expect(numberControlValue("3")).toBe("3")
    expect(numberControlValue("null")).toBe("")
  })

  it("accepts date and datetime-local shaped strings", () => {
    expect(dateControlValue("2026-07-23")).toBe("2026-07-23")
    expect(datetimeLocalControlValue("2026-07-23T09:30")).toBe("2026-07-23T09:30")
    expect(datetimeLocalControlValue("null")).toBe("")
  })

  it("omits null schema defaults from initial values", () => {
    const values = initialCapabilityValues(
      [
        { name: "max_entries", default: null },
        { name: "after", default: null },
        { name: "kind", default: "rss" },
        { name: "force", default: false },
      ],
      new Set(["kind"])
    )
    expect(values).toEqual({ force: false })
    expect(values.max_entries).toBeUndefined()
    expect(values.after).toBeUndefined()
  })
})
