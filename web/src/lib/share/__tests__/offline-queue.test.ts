import { describe, it, expect, vi, beforeEach } from "vitest"

// Mock @capacitor/preferences before importing the module under test
const mockGet = vi.fn()
const mockSet = vi.fn()

vi.mock("@capacitor/preferences", () => ({
  Preferences: {
    get: (...args: unknown[]) => mockGet(...args),
    set: (...args: unknown[]) => mockSet(...args),
  },
}))

// Import after mock setup
const { enqueue, dequeue, getPending, flushQueue } = await import(
  "../offline-queue"
)

describe("offline-queue", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue({ value: null })
    mockSet.mockResolvedValue(undefined)
  })

  describe("getPending", () => {
    it("returns empty array when storage is empty", async () => {
      mockGet.mockResolvedValue({ value: null })
      const result = await getPending()
      expect(result).toEqual([])
    })

    it("returns parsed items from storage", async () => {
      const items = [
        { url: "https://a.com", queuedAt: "2026-01-01T00:00:00Z", retryCount: 0 },
      ]
      mockGet.mockResolvedValue({ value: JSON.stringify(items) })
      const result = await getPending()
      expect(result).toEqual(items)
    })

    it("returns empty array on parse error", async () => {
      mockGet.mockResolvedValue({ value: "invalid json{{{" })
      const result = await getPending()
      expect(result).toEqual([])
    })
  })

  describe("enqueue", () => {
    it("adds a new URL to empty queue", async () => {
      mockGet.mockResolvedValue({ value: null })

      await enqueue("https://example.com/article")

      expect(mockSet).toHaveBeenCalledWith({
        key: "pending_shares",
        value: expect.stringContaining("https://example.com/article"),
      })

      const saved = JSON.parse(mockSet.mock.calls[0][0].value)
      expect(saved).toHaveLength(1)
      expect(saved[0].url).toBe("https://example.com/article")
      expect(saved[0].retryCount).toBe(0)
      expect(saved[0].queuedAt).toBeTruthy()
    })

    it("deduplicates by normalized URL", async () => {
      const existing = [
        { url: "https://example.com/article", queuedAt: "2026-01-01T00:00:00Z", retryCount: 1 },
      ]
      mockGet.mockResolvedValue({ value: JSON.stringify(existing) })

      // Same URL with trailing slash — should normalize to same
      await enqueue("https://example.com/article/")

      // Should NOT have been called since it's a dupe
      expect(mockSet).not.toHaveBeenCalled()
    })

    it("adds different URLs to existing queue", async () => {
      const existing = [
        { url: "https://first.com", queuedAt: "2026-01-01T00:00:00Z", retryCount: 0 },
      ]
      mockGet.mockResolvedValue({ value: JSON.stringify(existing) })

      await enqueue("https://second.com")

      const saved = JSON.parse(mockSet.mock.calls[0][0].value)
      expect(saved).toHaveLength(2)
      expect(saved[1].url).toBe("https://second.com")
    })

    it("trims whitespace from URL", async () => {
      await enqueue("  https://example.com  ")

      const saved = JSON.parse(mockSet.mock.calls[0][0].value)
      expect(saved[0].url).toBe("https://example.com")
    })
  })

  describe("dequeue", () => {
    it("removes URL from queue", async () => {
      const items = [
        { url: "https://a.com", queuedAt: "2026-01-01T00:00:00Z", retryCount: 0 },
        { url: "https://b.com", queuedAt: "2026-01-01T00:00:00Z", retryCount: 0 },
      ]
      mockGet.mockResolvedValue({ value: JSON.stringify(items) })

      await dequeue("https://a.com")

      const saved = JSON.parse(mockSet.mock.calls[0][0].value)
      expect(saved).toHaveLength(1)
      expect(saved[0].url).toBe("https://b.com")
    })

    it("handles dequeue of non-existent URL gracefully", async () => {
      const items = [
        { url: "https://a.com", queuedAt: "2026-01-01T00:00:00Z", retryCount: 0 },
      ]
      mockGet.mockResolvedValue({ value: JSON.stringify(items) })

      await dequeue("https://not-in-queue.com")

      const saved = JSON.parse(mockSet.mock.calls[0][0].value)
      expect(saved).toHaveLength(1)
    })
  })

  describe("flushQueue", () => {
    it("returns 0 for empty queue", async () => {
      mockGet.mockResolvedValue({ value: null })
      const saveFn = vi.fn()
      const result = await flushQueue(saveFn)
      expect(result).toBe(0)
      expect(saveFn).not.toHaveBeenCalled()
    })

    it("saves all URLs and returns count", async () => {
      const items = [
        { url: "https://a.com", queuedAt: "2026-01-01T00:00:00Z", retryCount: 0 },
        { url: "https://b.com", queuedAt: "2026-01-01T00:00:00Z", retryCount: 0 },
      ]
      mockGet.mockResolvedValue({ value: JSON.stringify(items) })
      const saveFn = vi.fn().mockResolvedValue(true)

      const result = await flushQueue(saveFn)

      expect(result).toBe(2)
      expect(saveFn).toHaveBeenCalledWith("https://a.com")
      expect(saveFn).toHaveBeenCalledWith("https://b.com")
      // Queue should be empty after flush
      const saved = JSON.parse(mockSet.mock.calls[0][0].value)
      expect(saved).toEqual([])
    })

    it("keeps failed URLs with incremented retry count", async () => {
      const items = [
        { url: "https://a.com", queuedAt: "2026-01-01T00:00:00Z", retryCount: 0 },
        { url: "https://b.com", queuedAt: "2026-01-01T00:00:00Z", retryCount: 2 },
      ]
      mockGet.mockResolvedValue({ value: JSON.stringify(items) })
      const saveFn = vi.fn()
        .mockResolvedValueOnce(true)   // a.com succeeds
        .mockResolvedValueOnce(false)  // b.com fails

      const result = await flushQueue(saveFn)

      expect(result).toBe(1)
      const saved = JSON.parse(mockSet.mock.calls[0][0].value)
      expect(saved).toHaveLength(1)
      expect(saved[0].url).toBe("https://b.com")
      expect(saved[0].retryCount).toBe(3) // was 2, now 3
    })

    it("drops URLs that exceed max retries", async () => {
      const items = [
        { url: "https://exhausted.com", queuedAt: "2026-01-01T00:00:00Z", retryCount: 5 },
      ]
      mockGet.mockResolvedValue({ value: JSON.stringify(items) })
      const saveFn = vi.fn().mockResolvedValue(false)

      const result = await flushQueue(saveFn)

      expect(result).toBe(0)
      // Should be dropped (retryCount 5 >= MAX_RETRIES 5)
      const saved = JSON.parse(mockSet.mock.calls[0][0].value)
      expect(saved).toEqual([])
    })

    it("handles saveFn throwing errors", async () => {
      const items = [
        { url: "https://a.com", queuedAt: "2026-01-01T00:00:00Z", retryCount: 0 },
      ]
      mockGet.mockResolvedValue({ value: JSON.stringify(items) })
      const saveFn = vi.fn().mockRejectedValue(new Error("Network error"))

      const result = await flushQueue(saveFn)

      expect(result).toBe(0)
      const saved = JSON.parse(mockSet.mock.calls[0][0].value)
      expect(saved).toHaveLength(1)
      expect(saved[0].retryCount).toBe(1)
    })
  })
})
