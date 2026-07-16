import { describe, expect, it, vi, beforeEach } from "vitest"

import { ApiClientError, apiClient } from "../client"
import { getAllCapabilities, listAllOperations, submitIngestion } from "../workflows"

describe("canonical workflow client", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("collects every capability cursor page", async () => {
    const get = vi.spyOn(apiClient, "get")
      .mockResolvedValueOnce({ contract_version: "2", source_commands: [{ key: "gmail" }], operation_types: [], resource_types: [], next_cursor: "next" })
      .mockResolvedValueOnce({ contract_version: "2", source_commands: [{ key: "rss" }], operation_types: [], resource_types: [], next_cursor: null })

    const capabilities = await getAllCapabilities()

    expect(capabilities.source_commands.map((source) => source.key)).toEqual(["gmail", "rss"])
    expect(get).toHaveBeenNthCalledWith(2, "/capabilities", { params: { cursor: "next", limit: 100 } })
  })

  it("submits the generated ingestion union without configured source internals", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ operation_id: "op-1" })

    await submitIngestion({ kind: "url", url: "https://example.com" })

    expect(post).toHaveBeenCalledWith("/ingestions", { kind: "url", url: "https://example.com" }, undefined)
  })

  it("hydrates operations across cursor pages", async () => {
    vi.spyOn(apiClient, "get")
      .mockResolvedValueOnce({ data: [{ operation_id: "op-1" }], next_cursor: "next" })
      .mockResolvedValueOnce({ data: [{ operation_id: "op-2" }], next_cursor: null })

    expect((await listAllOperations()).map((operation) => operation.operation_id)).toEqual(["op-1", "op-2"])
  })

  it("retains the complete RFC 7807 problem", () => {
    const problem = { type: "urn:aca:validation", title: "Invalid", status: 422, detail: "Bad command", instance: "/api/v1/ingestions", code: "invalid_command", errors: [{ field: "url" }] }
    const error = new ApiClientError(problem, 422)
    expect(error.problem).toEqual(problem)
    expect(error.message).toBe("Bad command")
  })
})
