/**
 * API Mocks
 *
 * Centralized route interception for all /api/v1/* endpoints.
 * Uses Playwright's page.route() to intercept network requests
 * and return deterministic mock data.
 *
 * Usage:
 *   const mocks = new ApiMocks(page)
 *   await mocks.mockAllDefaults()  // Mock everything with realistic data
 *   await mocks.mockAllEmpty()     // Mock everything with empty responses
 *   await mocks.mockAllErrors()    // Mock everything with 500 errors
 */

import type { Page } from "@playwright/test"
import * as mockData from "./mock-data"

export class ApiMocks {
  constructor(private page: Page) {}

  // ─── Convenience Methods ─────────────────────────────────

  /** Mock all endpoints with realistic default data */
  async mockAllDefaults(): Promise<void> {
    await Promise.all([
      this.mockContents(),
      this.mockContentStats(),
      this.mockSummaries(),
      this.mockSummaryStats(),
      this.mockDigests(),
      this.mockDigestStats(),
      this.mockScripts(),
      this.mockScriptStats(),
      this.mockPodcasts(),
      this.mockPodcastStats(),
      this.mockAudioDigests(),
      this.mockAudioDigestStats(),
      this.mockThemes(),
      this.mockChatConfig(),
      this.mockSystemHealth(),
    ])
  }

  /** Mock all endpoints with empty responses */
  async mockAllEmpty(): Promise<void> {
    await Promise.all([
      this.mockContentsEmpty(),
      this.mockContentStatsEmpty(),
      this.mockSummariesEmpty(),
      this.mockSummaryStatsEmpty(),
      this.mockDigestsEmpty(),
      this.mockDigestStatsEmpty(),
      this.mockScriptsEmpty(),
      this.mockScriptStatsEmpty(),
      this.mockPodcastsEmpty(),
      this.mockPodcastStatsEmpty(),
      this.mockAudioDigestsEmpty(),
      this.mockAudioDigestStatsEmpty(),
      this.mockThemesEmpty(),
      this.mockChatConfig(),
      this.mockSystemHealth(),
    ])
  }

  /** Mock all endpoints with 500 error responses */
  async mockAllErrors(): Promise<void> {
    await this.page.route("**/api/v1/**", (route) => {
      return route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          message: "Internal server error",
          code: "INTERNAL_ERROR",
        }),
      })
    })
  }

  // ─── Content Endpoints ───────────────────────────────────

  async mockContents(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/contents?*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createContentListResponse()),
      })
    )
    // Also match without query params
    await this.page.route("**/api/v1/contents", (route) => {
      if (route.request().url().includes("?")) return route.fallback()
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createContentListResponse()),
      })
    })
  }

  async mockContentsEmpty(): Promise<void> {
    await this.mockContents(mockData.createEmptyContentListResponse())
  }

  async mockContentDetail(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/contents/*", (route) => {
      const url = route.request().url()
      // Skip if this is a sub-resource like /contents/stats
      if (
        url.includes("/stats") ||
        url.includes("/duplicates") ||
        url.includes("/ingest") ||
        url.includes("/summarize")
      ) {
        return route.fallback()
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createContent()),
      })
    })
  }

  async mockContentStats(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/contents/stats", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createContentStats()),
      })
    )
  }

  async mockContentStatsEmpty(): Promise<void> {
    await this.mockContentStats({
      total: 0,
      by_status: {
        pending: 0,
        parsing: 0,
        parsed: 0,
        processing: 0,
        completed: 0,
        failed: 0,
      },
      by_source: {
        gmail: 0,
        rss: 0,
        file_upload: 0,
        youtube: 0,
        manual: 0,
        webpage: 0,
        other: 0,
      },
      pending_count: 0,
      completed_count: 0,
      failed_count: 0,
      needs_summarization_count: 0,
    })
  }

  async mockIngestContents(): Promise<void> {
    await this.page.route("**/api/v1/contents/ingest", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          mockData.createTaskResponse({ message: "Ingestion started" })
        ),
      })
    )
  }

  // ─── Summary Endpoints ───────────────────────────────────

  async mockSummaries(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/summaries?*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createSummaryListResponse()),
      })
    )
    await this.page.route("**/api/v1/summaries", (route) => {
      if (route.request().url().includes("?")) return route.fallback()
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createSummaryListResponse()),
      })
    })
  }

  async mockSummariesEmpty(): Promise<void> {
    await this.mockSummaries(mockData.createEmptyPaginatedResponse())
  }

  async mockSummaryDetail(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/summaries/*", (route) => {
      const url = route.request().url()
      if (url.includes("/stats") || url.includes("/navigation")) {
        return route.fallback()
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createSummary()),
      })
    })
  }

  async mockSummaryStats(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/summaries/stats", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          data ?? { total: 25, by_model: { "claude-haiku-4-5": 20, "claude-sonnet-4-5": 5 } }
        ),
      })
    )
  }

  async mockSummaryStatsEmpty(): Promise<void> {
    await this.mockSummaryStats({ total: 0, by_model: {} })
  }

  async mockSummarizeContents(): Promise<void> {
    await this.page.route("**/api/v1/contents/summarize", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          mockData.createTaskResponse({ message: "Summarization started" })
        ),
      })
    )
  }

  // ─── Digest Endpoints ────────────────────────────────────

  async mockDigests(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/digests/?*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          data ?? [
            mockData.createDigestListItem({ id: 1, status: "COMPLETED" }),
            mockData.createDigestListItem({
              id: 2,
              status: "PENDING_REVIEW",
              title: "Weekly AI Digest - Jan 8-14",
              digest_type: "weekly",
            }),
          ]
        ),
      })
    )
    await this.page.route("**/api/v1/digests/", (route) => {
      if (route.request().url().includes("?")) return route.fallback()
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          data ?? [
            mockData.createDigestListItem({ id: 1, status: "COMPLETED" }),
            mockData.createDigestListItem({
              id: 2,
              status: "PENDING_REVIEW",
              title: "Weekly AI Digest - Jan 8-14",
              digest_type: "weekly",
            }),
          ]
        ),
      })
    })
  }

  async mockDigestsEmpty(): Promise<void> {
    await this.mockDigests([])
  }

  async mockDigestDetail(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/digests/*", (route) => {
      const url = route.request().url()
      if (
        url.includes("/stats") ||
        url.includes("/generate") ||
        url.includes("/review") ||
        url.includes("/approve") ||
        url.includes("/reject") ||
        url.includes("/sections") ||
        url.includes("/sources") ||
        url.includes("/navigation") ||
        url.includes("/audio") ||
        url.endsWith("/digests/")
      ) {
        return route.fallback()
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createDigestDetail()),
      })
    })
  }

  async mockDigestStats(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/digests/stats", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createDigestStatistics()),
      })
    )
  }

  async mockDigestStatsEmpty(): Promise<void> {
    await this.mockDigestStats({
      total: 0,
      pending: 0,
      generating: 0,
      completed: 0,
      pending_review: 0,
      approved: 0,
      delivered: 0,
      by_type: {},
    })
  }

  async mockGenerateDigest(): Promise<void> {
    await this.page.route("**/api/v1/digests/generate", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "processing",
          message: "Digest generation started",
          period_start: "2025-01-15T00:00:00Z",
          period_end: "2025-01-15T23:59:59Z",
        }),
      })
    )
  }

  // ─── Script Endpoints ────────────────────────────────────

  async mockScripts(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/scripts/?*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          data ?? [
            mockData.createScriptListItem({ id: 1 }),
            mockData.createScriptListItem({
              id: 2,
              title: "Data Engineering Roundup",
              status: "script_approved",
            }),
          ]
        ),
      })
    )
    await this.page.route("**/api/v1/scripts/", (route) => {
      if (route.request().url().includes("?")) return route.fallback()
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          data ?? [
            mockData.createScriptListItem({ id: 1 }),
            mockData.createScriptListItem({
              id: 2,
              title: "Data Engineering Roundup",
              status: "script_approved",
            }),
          ]
        ),
      })
    })
  }

  async mockScriptsEmpty(): Promise<void> {
    await this.mockScripts([])
  }

  async mockScriptDetail(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/scripts/*", (route) => {
      const url = route.request().url()
      if (
        url.includes("/stats") ||
        url.includes("/generate") ||
        url.includes("/review") ||
        url.includes("/approve") ||
        url.includes("/reject") ||
        url.includes("/pending") ||
        url.includes("/approved") ||
        url.includes("/sections") ||
        url.includes("/navigation") ||
        url.endsWith("/scripts/")
      ) {
        return route.fallback()
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createScriptDetail()),
      })
    })
  }

  async mockScriptStats(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/scripts/stats", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createScriptReviewStatistics()),
      })
    )
  }

  async mockScriptStatsEmpty(): Promise<void> {
    await this.mockScriptStats({
      pending_review: 0,
      revision_requested: 0,
      approved_ready_for_audio: 0,
      completed_with_audio: 0,
      failed_rejected: 0,
      total: 0,
    })
  }

  async mockPendingScripts(): Promise<void> {
    await this.page.route("**/api/v1/scripts/pending-review", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          mockData.createScriptListItem({
            id: 1,
            status: "script_pending_review",
          }),
        ]),
      })
    )
  }

  async mockApprovedScripts(): Promise<void> {
    await this.page.route("**/api/v1/scripts/approved", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockData.createApprovedScripts()),
      })
    )
  }

  // ─── Podcast Endpoints ───────────────────────────────────

  async mockPodcasts(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/podcasts/?*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          data ?? [mockData.createPodcastListItem({ id: 1 })]
        ),
      })
    )
    await this.page.route("**/api/v1/podcasts/", (route) => {
      if (route.request().url().includes("?")) return route.fallback()
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          data ?? [mockData.createPodcastListItem({ id: 1 })]
        ),
      })
    })
  }

  async mockPodcastsEmpty(): Promise<void> {
    await this.mockPodcasts([])
  }

  async mockPodcastDetail(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/podcasts/*", (route) => {
      const url = route.request().url()
      if (
        url.includes("/stats") ||
        url.includes("/generate") ||
        url.includes("/audio") ||
        url.endsWith("/podcasts/")
      ) {
        return route.fallback()
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createPodcastDetail()),
      })
    })
  }

  async mockPodcastStats(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/podcasts/stats", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createPodcastStatistics()),
      })
    )
  }

  async mockPodcastStatsEmpty(): Promise<void> {
    await this.mockPodcastStats({
      total: 0,
      generating: 0,
      completed: 0,
      failed: 0,
      total_duration_seconds: 0,
      by_voice_provider: {},
    })
  }

  // ─── Audio Digest Endpoints ──────────────────────────────

  async mockAudioDigests(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/audio-digests/?*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          data ?? [mockData.createAudioDigestListItem({ id: 1 })]
        ),
      })
    )
    await this.page.route("**/api/v1/audio-digests/", (route) => {
      if (route.request().url().includes("?")) return route.fallback()
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          data ?? [mockData.createAudioDigestListItem({ id: 1 })]
        ),
      })
    })
    // Also match /audio-digests without trailing slash
    await this.page.route("**/api/v1/audio-digests", (route) => {
      if (route.request().url().includes("?")) return route.fallback()
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          data ?? [mockData.createAudioDigestListItem({ id: 1 })]
        ),
      })
    })
  }

  async mockAudioDigestsEmpty(): Promise<void> {
    await this.mockAudioDigests([])
  }

  async mockAudioDigestDetail(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/audio-digests/*", (route) => {
      const url = route.request().url()
      if (
        url.includes("/stats") ||
        url.includes("/stream") ||
        url.endsWith("/audio-digests/")
      ) {
        return route.fallback()
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createAudioDigestDetail()),
      })
    })
  }

  async mockAudioDigestStats(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/audio-digests/stats", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createAudioDigestStatistics()),
      })
    )
  }

  async mockAudioDigestStatsEmpty(): Promise<void> {
    await this.mockAudioDigestStats({
      total: 0,
      generating: 0,
      completed: 0,
      failed: 0,
      total_duration_seconds: 0,
      by_voice: {},
      by_provider: {},
    })
  }

  async mockAvailableDigests(): Promise<void> {
    await this.page.route("**/api/v1/audio-digests/available-digests*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockData.createAvailableDigests()),
      })
    )
  }

  // ─── Theme Endpoints ─────────────────────────────────────

  async mockThemes(data?: unknown): Promise<void> {
    await this.page.route("**/api/v1/themes/latest", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data ?? mockData.createThemeAnalysisResult()),
      })
    )
    await this.page.route("**/api/v1/themes/analyses*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "analysis-1",
            analysis_date: "2025-01-16T00:00:00Z",
            total_themes: 3,
            content_count: 25,
          },
        ]),
      })
    )
  }

  async mockThemesEmpty(): Promise<void> {
    await this.page.route("**/api/v1/themes/latest", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "No analysis found" }),
      })
    )
    await this.page.route("**/api/v1/themes/analyses*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      })
    )
  }

  async mockAnalyzeThemes(): Promise<void> {
    await this.page.route("**/api/v1/themes/analyze", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          mockData.createTaskResponse({ message: "Analysis started" })
        ),
      })
    )
  }

  // ─── Chat Endpoints ──────────────────────────────────────

  async mockChatConfig(): Promise<void> {
    await this.page.route("**/api/v1/chat/config", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockData.createChatConfig()),
      })
    )
  }

  // ─── System Endpoints ────────────────────────────────────

  async mockSystemHealth(): Promise<void> {
    await this.page.route("**/api/v1/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "healthy", version: "1.0.0" }),
      })
    )
  }

  // ─── Delayed Response Helper ─────────────────────────────

  /** Mock an endpoint with a delayed response (for loading state tests) */
  async mockWithDelay(
    pattern: string,
    data: unknown,
    delayMs: number
  ): Promise<void> {
    await this.page.route(pattern, async (route) => {
      await new Promise((resolve) => setTimeout(resolve, delayMs))
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data),
      })
    })
  }

  /** Mock an endpoint with a specific error */
  async mockWithError(
    pattern: string,
    status: number,
    message: string
  ): Promise<void> {
    await this.page.route(pattern, (route) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify({ message, code: `ERROR_${status}` }),
      })
    )
  }
}
