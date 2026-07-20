import { beforeEach, describe, expect, it, vi } from "vitest"

import { apiClient } from "../client"
import { saveUrl } from "../contents"

describe("content ingestion client", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("omits native share metadata from the strict URL command", async () => {
    const post = vi
      .spyOn(apiClient, "post")
      .mockResolvedValue({ operation_id: "op-url" })

    await saveUrl({
      url: "https://example.com/article",
      title: "Article",
      tags: ["shared"],
      notes: "Read later",
      source: "native-share",
    })

    expect(post).toHaveBeenCalledWith("/ingestions", {
      kind: "url",
      url: "https://example.com/article",
      title: "Article",
      tags: ["shared"],
      notes: "Read later",
    })
  })
})
