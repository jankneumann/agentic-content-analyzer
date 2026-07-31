import { describe, expect, it, vi, beforeEach } from "vitest"

import { ApiClientError, apiClient } from "../client"
import {
  getAllCapabilities,
  getConfiguredSources,
  listBackgroundOperations,
  submitDigest,
  submitIngestion,
} from "../workflows"

describe("canonical workflow client", () => {
  beforeEach(() => vi.restoreAllMocks())

  it("collects every capability cursor page", async () => {
    const get = vi
      .spyOn(apiClient, "get")
      .mockResolvedValueOnce({
        contract_version: "2",
        source_commands: [{ key: "gmail" }],
        operation_types: [],
        resource_types: [],
        next_cursor: "next",
      })
      .mockResolvedValueOnce({
        contract_version: "2",
        source_commands: [{ key: "rss" }],
        operation_types: [],
        resource_types: [],
        next_cursor: null,
      })

    const capabilities = await getAllCapabilities()

    expect(capabilities.source_commands.map((source) => source.key)).toEqual([
      "gmail",
      "rss",
    ])
    expect(get).toHaveBeenNthCalledWith(2, "/capabilities", {
      params: { cursor: "next", limit: 100 },
    })
  })

  it("omits cursor from configured-source first page", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue({
      data: [],
      next_cursor: null,
    })

    await getConfiguredSources()

    expect(get).toHaveBeenCalledWith("/configured-sources", {
      params: { limit: 100 },
    })
  })

  it("submits the generated ingestion union without configured source internals", async () => {
    const post = vi
      .spyOn(apiClient, "post")
      .mockResolvedValue({ operation_id: "op-1" })

    await submitIngestion({ kind: "url", url: "https://example.com" })

    expect(post).toHaveBeenCalledWith(
      "/ingestions",
      { kind: "url", url: "https://example.com" },
      undefined
    )
  })

  it("preserves invalid ingestion field paths without alternate mutations", async () => {
    const problem = {
      type: "https://aca.rotkohl.ai/problems/validation-error",
      title: "Request validation failed",
      status: 422,
      detail: "Input should be greater than or equal to 1",
      instance: "/api/v1/ingestions",
      code: "validation_error",
      errors: [
        {
          path: ["x_search", "max_threads"],
          code: "greater_than_equal",
          message: "Input should be greater than or equal to 1",
        },
      ],
    }
    const post = vi
      .spyOn(apiClient, "post")
      .mockRejectedValue(new ApiClientError(problem, 422))
    const request = {
      kind: "x_search" as const,
      prompt: "agents",
      max_threads: 0,
    }

    await expect(submitIngestion(request)).rejects.toMatchObject({ problem })
    expect(post).toHaveBeenCalledTimes(1)
    expect(post).toHaveBeenCalledWith("/ingestions", request, undefined)
  })

  it("submits the canonical digest payload with idempotency", async () => {
    const operation = {
      schema_version: 2 as const,
      operation_id: "op-digest-1",
      operation_type: "digest.create" as const,
      status: "queued" as const,
      progress: 0,
      message: "Queued",
      cancellable: true,
      retry_count: 0,
      status_url: "/api/v1/operations/op-digest-1",
      events_url: "/api/v1/operations/op-digest-1/events",
      created_at: "2026-07-16T00:00:00Z",
    }
    const post = vi.spyOn(apiClient, "post").mockResolvedValue(operation)
    const request = {
      digest_type: "daily" as const,
      period_start: "2026-07-15T00:00:00Z",
      period_end: "2026-07-16T00:00:00Z",
      include_historical_context: false,
    }

    await expect(
      submitDigest(request, { idempotencyKey: "digest-parity-1" })
    ).resolves.toEqual(operation)
    expect(post).toHaveBeenCalledWith("/digests", request, {
      headers: { "Idempotency-Key": "digest-parity-1" },
    })
  })

  it("hydrates background operations with three bounded summary queries", async () => {
    const get = vi
      .spyOn(apiClient, "get")
      .mockResolvedValueOnce({ data: [{ operation_id: "recent" }], next_cursor: "ignored" })
      .mockResolvedValueOnce({ data: [{ operation_id: "queued" }], next_cursor: "ignored" })
      .mockResolvedValueOnce({ data: [{ operation_id: "running" }], next_cursor: "ignored" })

    expect(
      (await listBackgroundOperations()).map((operation) => operation.operation_id)
    ).toEqual(["recent", "queued", "running"])
    expect(get).toHaveBeenCalledTimes(3)
    expect(get).toHaveBeenNthCalledWith(1, "/operations", {
      params: { limit: 100 },
    })
    expect(get).toHaveBeenNthCalledWith(2, "/operations", {
      params: { limit: 100, status: "queued" },
    })
    expect(get).toHaveBeenNthCalledWith(3, "/operations", {
      params: { limit: 100, status: "in_progress" },
    })
  })

  it("retains the complete RFC 7807 problem", () => {
    const problem = {
      type: "urn:aca:validation",
      title: "Invalid",
      status: 422,
      detail: "Bad command",
      instance: "/api/v1/ingestions",
      code: "invalid_command",
      errors: [{ field: "url" }],
    }
    const error = new ApiClientError(problem, 422)
    expect(error.problem).toEqual(problem)
    expect(error.message).toBe("Bad command")
  })
})
