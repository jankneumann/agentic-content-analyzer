import { describe, it, expect, vi, beforeEach } from "vitest"

// Mock the apiClient before importing the module under test so the spies are
// wired up. We assert that the sources API functions hit the right endpoints
// and URL-encode the source key (which contains ":" and "/").
vi.mock("../client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
  isApiError: vi.fn(),
}))

import { apiClient } from "../client"
import {
  fetchSources,
  upsertSource,
  deleteSource,
  setSourceEnabled,
} from "../sources"
import type {
  SourceDeleteResult,
  SourceInfo,
  SourceMutationResult,
  SourceUpsertRequest,
} from "@/types/settings"

describe("sources API client", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("fetchSources GETs /sources", async () => {
    await fetchSources()
    expect(apiClient.get).toHaveBeenCalledWith("/sources")
  })

  it("upsertSource POSTs the request body to /sources", async () => {
    const request: SourceUpsertRequest = {
      config: { type: "rss", url: "https://x.test/feed" },
    }
    await upsertSource(request)
    expect(apiClient.post).toHaveBeenCalledWith("/sources", request)
  })

  it("shares generated mutation and deletion response shapes", () => {
    const mutation: SourceMutationResult = {
      source_key: "src_0123456789abcdef0123",
      version: 1,
      origin: "db",
      enabled: true,
    }
    const deletion: SourceDeleteResult = {
      source_key: mutation.source_key,
      deleted: true,
    }

    expect(deletion.source_key).toBe(mutation.source_key)
  })

  it("represents Readwise and opaque Obsidian response rows", () => {
    const sources: SourceInfo[] = [
      {
        type: "readwise",
        name: "Readwise",
        url: "default",
        enabled: true,
        tags: [],
        origin: "db",
        source_key: "readwise:default",
      },
      {
        type: "obsidian_vault",
        name: null,
        url: "src_0123456789abcdef0123",
        enabled: false,
        tags: [],
        origin: "db",
        source_key: "src_0123456789abcdef0123",
      },
    ]

    expect(sources.map((source) => source.type)).toEqual([
      "readwise",
      "obsidian_vault",
    ])
  })

  it("setSourceEnabled PATCHes an encoded key with { enabled }", async () => {
    await setSourceEnabled("rss:https://x.test/feed", false)
    expect(apiClient.patch).toHaveBeenCalledWith(
      "/sources/rss%3Ahttps%3A%2F%2Fx.test%2Ffeed",
      { enabled: false }
    )
  })

  it("deleteSource DELETEs an encoded key", async () => {
    await deleteSource("youtube_playlist:PL123")
    expect(apiClient.delete).toHaveBeenCalledWith(
      "/sources/youtube_playlist%3APL123"
    )
  })
})
