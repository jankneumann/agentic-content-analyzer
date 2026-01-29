/**
 * Digest Review Page Tests
 *
 * Tests for /review/digest/:id page: two-pane layout,
 * left pane (summaries/sources), right pane (digest content),
 * navigation, chat panel, and actions.
 */

import { test, expect } from "../../fixtures"

test.describe("Digest Review Page", () => {
  test.beforeEach(async ({ apiMocks, page }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockDigestDetail()

    // Mock digest sources
    await page.route("**/api/v1/digests/*/sources", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: 1,
            title: "AI Weekly: GPT-5 Announced",
            publication: "AI Weekly Newsletter",
            executive_summary_preview: "OpenAI announced GPT-5...",
            key_themes: ["LLMs", "AI Safety"],
          },
        ]),
      })
    )

    // Mock digest navigation
    await page.route("**/api/v1/digests/*/navigation", (route) =>
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

    await expect(reviewPage.page.getByText("Review Digest")).toBeVisible()
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

    await expect(reviewPage.page.getByText("Back to Digests")).toBeVisible()
  })

  test("navigation shows position info", async ({ reviewPage }) => {
    await reviewPage.navigateToDigestReview(1)

    // Navigation shows "1 of 5"
    await expect(reviewPage.page.getByText(/1.*of.*5/i)).toBeVisible()
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
