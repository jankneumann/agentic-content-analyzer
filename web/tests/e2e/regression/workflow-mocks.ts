/**
 * Stateful Workflow Mocks
 *
 * Provides mock infrastructure for regression tests that simulate
 * multi-step workflows. Unlike static API mocks, these track state
 * transitions across sequential user actions, ensuring that the UX
 * correctly reflects pipeline progression.
 *
 * Example: After "generate digest", the digests list should show
 * a new item with status "GENERATING" → then "PENDING_REVIEW".
 */

import type { Page } from "@playwright/test"
import * as mockData from "../fixtures/mock-data"

// ─── State Machine ──────────────────────────────────────────

export type PipelineStage =
  | "empty"
  | "content_ingested"
  | "content_summarized"
  | "themes_analyzed"
  | "digest_generated"
  | "digest_reviewed"
  | "script_generated"
  | "script_approved"
  | "podcast_generated"

/**
 * Tracks the current pipeline state and returns appropriate mock
 * data for each API endpoint based on which stages have completed.
 */
export class WorkflowState {
  stage: PipelineStage = "empty"
  private requestLog: Array<{ method: string; url: string; body?: string }> = []

  /** Advance to the next stage */
  advance(to: PipelineStage): void {
    this.stage = to
  }

  /** Log an intercepted request for later assertions */
  logRequest(method: string, url: string, body?: string): void {
    this.requestLog.push({ method, url, body })
  }

  /** Get all logged requests */
  getRequests(): Array<{ method: string; url: string; body?: string }> {
    return [...this.requestLog]
  }

  /** Find requests matching a pattern */
  findRequests(
    pattern: string | RegExp
  ): Array<{ method: string; url: string; body?: string }> {
    return this.requestLog.filter((r) =>
      typeof pattern === "string"
        ? r.url.includes(pattern)
        : pattern.test(r.url)
    )
  }

  /** Check if a POST was made to a specific endpoint */
  wasPostedTo(urlFragment: string): boolean {
    return this.requestLog.some(
      (r) => r.method === "POST" && r.url.includes(urlFragment)
    )
  }
}

// ─── Stage-Aware Mock Data ──────────────────────────────────

/** Content items that appear after ingestion */
function ingestedContentItems() {
  return [
    mockData.createContentListItem({
      id: 101,
      title: "AI Weekly: GPT-5 Announced",
      source_type: "gmail",
      status: "completed",
    }),
    mockData.createContentListItem({
      id: 102,
      title: "ML Ops Digest: Kubernetes for ML",
      source_type: "rss",
      status: "completed",
    }),
    mockData.createContentListItem({
      id: 103,
      title: "Deep Learning Trends Q1 2025",
      source_type: "rss",
      status: "completed",
    }),
  ]
}

/** Summaries that appear after summarization */
function generatedSummaries() {
  return {
    items: [
      mockData.createSummaryListItem({
        id: 201,
        content_id: 101,
        title: "AI Weekly: GPT-5 Announced",
      }),
      mockData.createSummaryListItem({
        id: 202,
        content_id: 102,
        title: "ML Ops Digest: Kubernetes for ML",
      }),
      mockData.createSummaryListItem({
        id: 203,
        content_id: 103,
        title: "Deep Learning Trends Q1 2025",
      }),
    ],
    total: 3,
    offset: 0,
    limit: 20,
    has_more: false,
  }
}

/** Digest in PENDING_REVIEW state */
function pendingReviewDigest() {
  return mockData.createDigestDetail({
    id: 301,
    status: "PENDING_REVIEW",
    title: "Daily AI & Data Digest - Regression Test",
    content_count: 3,
    revision_count: 0,
    reviewed_by: null,
    reviewed_at: null,
  })
}

/** Digest in APPROVED state */
function approvedDigest() {
  return mockData.createDigestDetail({
    id: 301,
    status: "APPROVED",
    title: "Daily AI & Data Digest - Regression Test",
    content_count: 3,
    revision_count: 0,
    reviewed_by: "regression-tester",
    reviewed_at: "2025-01-16T12:00:00Z",
    review_notes: "Approved via regression test",
  })
}

/** Script in PENDING_REVIEW state */
function pendingReviewScript() {
  return mockData.createScriptDetail({
    id: 401,
    digest_id: 301,
    title: "AI Weekly Deep Dive - Regression Test",
    status: "script_pending_review",
  })
}

/** Script in APPROVED state */
function approvedScript() {
  return mockData.createScriptDetail({
    id: 401,
    digest_id: 301,
    title: "AI Weekly Deep Dive - Regression Test",
    status: "script_approved",
  })
}

/** Podcast in COMPLETED state */
function completedPodcast() {
  return mockData.createPodcastDetail({
    id: 501,
    script_id: 401,
    title: "AI Weekly Deep Dive - Regression Test",
    status: "completed",
  })
}

// ─── Workflow Mock Setup ────────────────────────────────────

/**
 * Sets up stateful API mocks for the daily pipeline workflow.
 *
 * Mock responses change based on the current WorkflowState,
 * simulating how the real API would behave as the pipeline
 * progresses through stages.
 */
export async function setupDailyPipelineWorkflow(
  page: Page,
  state: WorkflowState
): Promise<void> {
  // ── Always-available endpoints ──
  await page.route("**/api/v1/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "healthy", version: "1.0.0" }),
    })
  )

  await page.route("**/api/v1/chat/config", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockData.createChatConfig()),
    })
  )

  await page.route("**/api/v1/settings/connections*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockData.createConnectionStatusResponse()),
    })
  )

  await page.route("**/api/v1/notifications/events*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        mockData.createNotificationEventListResponse()
      ),
    })
  )

  await page.route("**/api/v1/notifications/unread-count*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockData.createUnreadCountResponse()),
    })
  )

  await page.route("**/api/v1/settings/notifications*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        mockData.createNotificationPreferencesResponse()
      ),
    })
  )

  await page.route("**/api/v1/voice/cleanup*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ cleaned_text: "Cleaned up text." }),
    })
  )

  await page.route("**/api/v1/settings/voice*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        voice_provider: "openai_tts",
        voices: { alex: "alloy", sam: "nova" },
      }),
    })
  )

  await page.route("**/api/v1/settings/models*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    })
  )

  // ── Content endpoints (state-dependent) ──

  await page.route("**/api/v1/contents/statistics*", (route) => {
    const hasContent = stageAtLeast(state.stage, "content_ingested")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        hasContent
          ? { total: 3, by_source: { gmail: 1, rss: 2 }, by_status: { completed: 3 } }
          : { total: 0, by_source: {}, by_status: {} }
      ),
    })
  })

  await page.route(/\/api\/v1\/contents(\?|$)/, (route) => {
    const hasContent = stageAtLeast(state.stage, "content_ingested")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        hasContent
          ? {
              items: ingestedContentItems(),
              total: 3,
              offset: 0,
              limit: 20,
              has_more: false,
            }
          : { items: [], total: 0, offset: 0, limit: 20, has_more: false }
      ),
    })
  })

  // ── Summarize action ──

  await page.route("**/api/v1/contents/summarize", (route) => {
    state.logRequest(
      route.request().method(),
      route.request().url(),
      route.request().postData() ?? undefined
    )
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        mockData.createTaskResponse({ message: "Summarization started" })
      ),
    })
  })

  // ── Summary endpoints (state-dependent) ──

  await page.route("**/api/v1/summaries/statistics*", (route) => {
    const hasSummaries = stageAtLeast(state.stage, "content_summarized")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        hasSummaries ? { total: 3, by_model: { "claude-haiku-4-5": 3 } } : { total: 0, by_model: {} }
      ),
    })
  })

  await page.route(/\/api\/v1\/summaries(\?|$)/, (route) => {
    const hasSummaries = stageAtLeast(state.stage, "content_summarized")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        hasSummaries
          ? generatedSummaries()
          : { items: [], total: 0, offset: 0, limit: 20, has_more: false }
      ),
    })
  })

  // ── Theme endpoints (state-dependent) ──

  await page.route("**/api/v1/themes/analyze", (route) => {
    state.logRequest(
      route.request().method(),
      route.request().url(),
      route.request().postData() ?? undefined
    )
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        mockData.createTaskResponse({ message: "Analysis started" })
      ),
    })
  })

  await page.route("**/api/v1/themes/latest", (route) => {
    const hasThemes = stageAtLeast(state.stage, "themes_analyzed")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        hasThemes
          ? mockData.createThemeAnalysisResult()
          : { message: "No analysis found" }
      ),
    })
  })

  await page.route(/\/api\/v1\/themes(\?|$)/, (route) => {
    const url = route.request().url()
    if (/\/themes\/(latest|analyze|analysis)/.test(url)) {
      return route.fallback()
    }
    const hasThemes = stageAtLeast(state.stage, "themes_analyzed")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        hasThemes
          ? [
              {
                id: 1,
                status: "completed",
                analysis_date: "2025-01-16T00:00:00Z",
                start_date: "2025-01-01T00:00:00Z",
                end_date: "2025-01-15T23:59:59Z",
                total_themes: 3,
                content_count: 3,
                created_at: "2025-01-16T00:05:00Z",
              },
            ]
          : []
      ),
    })
  })

  // ── Digest endpoints (state-dependent) ──

  await page.route("**/api/v1/digests/generate", (route) => {
    state.logRequest(
      route.request().method(),
      route.request().url(),
      route.request().postData() ?? undefined
    )
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "processing",
        message: "Digest generation started",
        period_start: "2025-01-15T00:00:00Z",
        period_end: "2025-01-15T23:59:59Z",
      }),
    })
  })

  await page.route("**/api/v1/digests/statistics", (route) => {
    const hasDigest = stageAtLeast(state.stage, "digest_generated")
    const isApproved = stageAtLeast(state.stage, "digest_reviewed")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        total: hasDigest ? 1 : 0,
        pending: 0,
        generating: 0,
        completed: 0,
        pending_review: hasDigest && !isApproved ? 1 : 0,
        approved: isApproved ? 1 : 0,
        delivered: 0,
        by_type: hasDigest ? { daily: 1 } : {},
      }),
    })
  })

  // Digest detail (must be before digest list to match /digests/*)
  await page.route("**/api/v1/digests/*", (route) => {
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
    const hasDigest = stageAtLeast(state.stage, "digest_generated")
    if (!hasDigest) {
      return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ message: "Not found" }) })
    }
    const isApproved = stageAtLeast(state.stage, "digest_reviewed")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(isApproved ? approvedDigest() : pendingReviewDigest()),
    })
  })

  // Digest review action
  await page.route("**/api/v1/digests/*/review", (route) => {
    state.logRequest(
      route.request().method(),
      route.request().url(),
      route.request().postData() ?? undefined
    )
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "approved", message: "Digest approved" }),
    })
  })

  // Digest approve shortcut
  await page.route("**/api/v1/digests/*/approve*", (route) => {
    state.logRequest(
      route.request().method(),
      route.request().url(),
      route.request().postData() ?? undefined
    )
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "approved", message: "Digest approved" }),
    })
  })

  // Digest navigation
  await page.route("**/api/v1/digests/*/navigation*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ prev_id: null, next_id: null }),
    })
  )

  // Digest sources
  await page.route("**/api/v1/digests/*/sources*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    })
  )

  // Digest list
  await page.route(/\/api\/v1\/digests\/?\?/, (route) => {
    const hasDigest = stageAtLeast(state.stage, "digest_generated")
    const isApproved = stageAtLeast(state.stage, "digest_reviewed")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        hasDigest
          ? [
              mockData.createDigestListItem({
                id: 301,
                status: isApproved ? "APPROVED" : "PENDING_REVIEW",
                title: "Daily AI & Data Digest - Regression Test",
              }),
            ]
          : []
      ),
    })
  })

  await page.route("**/api/v1/digests/", (route) => {
    if (route.request().url().includes("?")) return route.fallback()
    const hasDigest = stageAtLeast(state.stage, "digest_generated")
    const isApproved = stageAtLeast(state.stage, "digest_reviewed")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        hasDigest
          ? [
              mockData.createDigestListItem({
                id: 301,
                status: isApproved ? "APPROVED" : "PENDING_REVIEW",
                title: "Daily AI & Data Digest - Regression Test",
              }),
            ]
          : []
      ),
    })
  })

  // ── Script endpoints (state-dependent) ──

  await page.route("**/api/v1/scripts/statistics", (route) => {
    const hasScript = stageAtLeast(state.stage, "script_generated")
    const isApproved = stageAtLeast(state.stage, "script_approved")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        pending_review: hasScript && !isApproved ? 1 : 0,
        revision_requested: 0,
        approved_ready_for_audio: isApproved ? 1 : 0,
        completed_with_audio: stageAtLeast(state.stage, "podcast_generated") ? 1 : 0,
        failed_rejected: 0,
        total: hasScript ? 1 : 0,
      }),
    })
  })

  await page.route("**/api/v1/scripts/pending-review", (route) => {
    const hasScript = stageAtLeast(state.stage, "script_generated")
    const isApproved = stageAtLeast(state.stage, "script_approved")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        hasScript && !isApproved
          ? [mockData.createScriptListItem({ id: 401, digest_id: 301, status: "script_pending_review" })]
          : []
      ),
    })
  })

  await page.route("**/api/v1/scripts/approved", (route) => {
    const isApproved = stageAtLeast(state.stage, "script_approved")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        isApproved
          ? [{ id: 401, digest_id: 301, title: "AI Weekly Deep Dive - Regression Test", length: "standard", word_count: 3200, estimated_duration_seconds: 720, approved_at: "2025-01-16T10:00:00Z" }]
          : []
      ),
    })
  })

  // Script detail
  await page.route("**/api/v1/scripts/*", (route) => {
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
    const hasScript = stageAtLeast(state.stage, "script_generated")
    if (!hasScript) {
      return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ message: "Not found" }) })
    }
    const isApproved = stageAtLeast(state.stage, "script_approved")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(isApproved ? approvedScript() : pendingReviewScript()),
    })
  })

  // Script review action
  await page.route("**/api/v1/scripts/*/review", (route) => {
    state.logRequest(route.request().method(), route.request().url(), route.request().postData() ?? undefined)
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "approved", message: "Script approved" }),
    })
  })

  await page.route("**/api/v1/scripts/*/approve*", (route) => {
    state.logRequest(route.request().method(), route.request().url(), route.request().postData() ?? undefined)
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "approved", message: "Script approved" }),
    })
  })

  // Script list
  await page.route(/\/api\/v1\/scripts\/?\?/, (route) => {
    const hasScript = stageAtLeast(state.stage, "script_generated")
    const isApproved = stageAtLeast(state.stage, "script_approved")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        hasScript
          ? [mockData.createScriptListItem({
              id: 401,
              digest_id: 301,
              status: isApproved ? "script_approved" : "script_pending_review",
            })]
          : []
      ),
    })
  })

  await page.route("**/api/v1/scripts/", (route) => {
    if (route.request().url().includes("?")) return route.fallback()
    const hasScript = stageAtLeast(state.stage, "script_generated")
    const isApproved = stageAtLeast(state.stage, "script_approved")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        hasScript
          ? [mockData.createScriptListItem({
              id: 401,
              digest_id: 301,
              status: isApproved ? "script_approved" : "script_pending_review",
            })]
          : []
      ),
    })
  })

  // ── Podcast endpoints (state-dependent) ──

  await page.route("**/api/v1/podcasts/generate", (route) => {
    state.logRequest(route.request().method(), route.request().url(), route.request().postData() ?? undefined)
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: 501, status: "generating", message: "Podcast generation started" }),
    })
  })

  await page.route("**/api/v1/podcasts/statistics", (route) => {
    const hasPodcast = stageAtLeast(state.stage, "podcast_generated")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        hasPodcast
          ? mockData.createPodcastStatistics({ total: 1, completed: 1 })
          : { total: 0, generating: 0, completed: 0, failed: 0, total_duration_seconds: 0, by_voice_provider: {} }
      ),
    })
  })

  // Podcast detail
  await page.route("**/api/v1/podcasts/*", (route) => {
    const url = route.request().url()
    if (
      url.includes("/stats") ||
      url.includes("/generate") ||
      url.includes("/audio") ||
      url.endsWith("/podcasts/")
    ) {
      return route.fallback()
    }
    const hasPodcast = stageAtLeast(state.stage, "podcast_generated")
    if (!hasPodcast) {
      return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ message: "Not found" }) })
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(completedPodcast()),
    })
  })

  // Podcast list
  await page.route(/\/api\/v1\/podcasts\/?\?/, (route) => {
    const hasPodcast = stageAtLeast(state.stage, "podcast_generated")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        hasPodcast ? [mockData.createPodcastListItem({ id: 501, status: "completed" })] : []
      ),
    })
  })

  await page.route("**/api/v1/podcasts/", (route) => {
    if (route.request().url().includes("?")) return route.fallback()
    const hasPodcast = stageAtLeast(state.stage, "podcast_generated")
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        hasPodcast ? [mockData.createPodcastListItem({ id: 501, status: "completed" })] : []
      ),
    })
  })

  // ── Audio digest endpoints (always empty for daily pipeline tests) ──

  await page.route(/\/api\/v1\/audio-digests/, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    })
  )

  // ── Job history ──

  await page.route("**/api/v1/jobs/history*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockData.createJobHistoryResponse()),
    })
  )

  // ── Prompts ──

  await page.route("**/api/v1/prompts*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockData.createPromptListResponse()),
    })
  )

  // ── Content query preview (for digest dry-run) ──

  await page.route("**/api/v1/contents/query/preview*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockData.createContentQueryPreview()),
    })
  )
}

// ─── Helpers ────────────────────────────────────────────────

const STAGE_ORDER: PipelineStage[] = [
  "empty",
  "content_ingested",
  "content_summarized",
  "themes_analyzed",
  "digest_generated",
  "digest_reviewed",
  "script_generated",
  "script_approved",
  "podcast_generated",
]

/** Check if the current stage is at or past a given stage */
function stageAtLeast(current: PipelineStage, target: PipelineStage): boolean {
  return STAGE_ORDER.indexOf(current) >= STAGE_ORDER.indexOf(target)
}
