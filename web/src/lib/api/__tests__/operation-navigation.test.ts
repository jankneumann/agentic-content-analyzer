import { describe, expect, it } from "vitest"
import { operationResourcePath } from "@/lib/operation-navigation"

describe("operation resource navigation", () => {
  it("maps persisted resources to existing application views", () => {
    expect(operationResourcePath({ type: "digest", id: "42", url: "https://api.invalid/digests/42" })).toBe("/review/digest/42")
    expect(operationResourcePath({ type: "podcast_script", id: "7", url: "/api/v1/scripts/7" })).toBe("/review/script/7")
    expect(operationResourcePath({ type: "audio_digest", id: "9", url: "/api/v1/audio-digests/9" })).toBe("/audio-digests")
  })

  it("never returns the API resource URL", () => {
    expect(operationResourcePath({ type: "podcast", id: "3", url: "https://api.invalid/private/3" })).toBe("/podcasts")
  })
})
