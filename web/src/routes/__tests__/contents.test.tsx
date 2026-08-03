import { describe, expect, it } from "vitest"

import { getContentSourceDisplay } from "@/lib/content-source-display"

describe("contents source display", () => {
  it("maps persisted Obsidian content to a renderable badge", () => {
    const display = getContentSourceDisplay("obsidian")

    expect(display.label).toBe("Obsidian")
    expect(display.icon).toBeDefined()
  })

  it("maps persisted Readwise content to a renderable badge", () => {
    const display = getContentSourceDisplay("readwise")

    expect(display.label).toBe("Readwise")
    expect(display.icon).toBeDefined()
  })
})
