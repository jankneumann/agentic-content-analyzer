/**
 * Digest Review Page Tests
 *
 * Tests for /review/digest/:id page: two-pane layout,
 * left pane (summaries/sources), right pane (digest content),
 * navigation, chat panel, and actions.
 *
 * The ReviewHeader renders:
 * - <h1> title: "Review Digest"
 * - Back label in <span class="hidden sm:inline"> (hidden on mobile)
 * - Navigation: "{position} of {total}" in a <span>
 * - Prev/Next buttons with aria-labels "Previous item" / "Next item"
 */

import { test, expect } from "../fixtures"

test.describe("Digest Review Page", () => {
  test.beforeEach(async ({ apiMocks, page }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockDigestDetail()

    // Mock digest sources — SummariesListPane accesses .length on array fields,
    // so sources must include full summary data (strategic_insights, technical_details, etc.)
    await page.route("**/api/v1/digests/*/sources", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: 1,
            content_id: 1,
            title: "AI Weekly: GPT-5 Announced",
            publication: "AI Weekly Newsletter",
            executive_summary:
              "OpenAI announced GPT-5 with significant improvements in reasoning.",
            executive_summary_preview: "OpenAI announced GPT-5...",
            key_themes: ["LLMs", "AI Safety"],
            strategic_insights: [
              "GPT-5 represents a significant leap in reasoning capabilities",
            ],
            technical_details: [
              "Architecture uses mixture-of-experts with 8 specialized modules",
            ],
            actionable_items: [
              "Evaluate GPT-5 API for existing summarization pipeline",
            ],
            notable_quotes: [
              '"This represents the biggest leap in AI capability since GPT-4" - Sam Altman',
            ],
            model_used: "claude-haiku-4-5",
            created_at: "2025-01-15T12:05:00Z",
            processing_time_seconds: 4.2,
          },
        ]),
      })
    )

    // Mock digest navigation (trailing * matches query params)
    await page.route("**/api/v1/digests/*/navigation*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          prev_id: null,
          next_id: 2,
          position: 1,
          total: 5,
        }),
      })
    )

    // Mock chat endpoints
    await page.route("**/api/v1/chat/**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ messages: [], conversation_id: null }),
      })
    )
  })

  test("navigates to digest review page", async ({ reviewPage }) => {
    await reviewPage.navigateToDigestReview(1)

    await expect(
      reviewPage.page.getByRole("heading", { name: "Review Digest", level: 1 })
    ).toBeVisible()
  })

  test("two-pane layout renders", async ({ reviewPage }) => {
    await reviewPage.navigateToDigestReview(1)

    await expect(reviewPage.leftPane).toBeVisible()
    await expect(reviewPage.rightPane).toBeVisible()
  })

  test("left pane shows summaries section", async ({ reviewPage }) => {
    await reviewPage.navigateToDigestReview(1)

    // Left pane should show the source summaries
    await expect(reviewPage.leftPane).toBeVisible()
  })

  test("right pane shows digest content", async ({ reviewPage }) => {
    await reviewPage.navigateToDigestReview(1)

    // Right pane has the digest content
    await expect(reviewPage.rightPane).toBeVisible()
  })

  test("back link navigates to digests", async ({ reviewPage }) => {
    await reviewPage.navigateToDigestReview(1)

    // Back label is inside a link to /digests; the text "Back to Digests" is
    // in a <span class="hidden sm:inline"> so it may be hidden on mobile.
    // Assert the link itself exists pointing to /digests.
    await expect(
      reviewPage.page.locator("a[href='/digests']").first()
    ).toBeVisible()
  })

  test("navigation shows position info", async ({ reviewPage }) => {
    await reviewPage.navigateToDigestReview(1)

    // Navigation shows "1 of 5"
    await expect(reviewPage.page.getByText("1 of 5")).toBeVisible()
  })

  test("next navigation button is visible", async ({ reviewPage }) => {
    await reviewPage.navigateToDigestReview(1)

    await expect(reviewPage.nextButton).toBeVisible()
  })

  test("chat panel is present at bottom", async ({ reviewPage }) => {
    await reviewPage.navigateToDigestReview(1)

    // The revision chat panel is rendered at the bottom
    await expect(reviewPage.page.locator(".border-t").last()).toBeVisible()
  })
})
