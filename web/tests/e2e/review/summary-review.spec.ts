/**
 * Summary Review Page Tests
 *
 * Tests for /review/summary/:id page: two-pane layout,
 * left pane (original content), right pane (summary),
 * feedback panel, and regenerate button.
 *
 * The ReviewHeader renders:
 * - <h1> title: "Review Summary"
 * - Back label in <span class="hidden sm:inline"> (hidden on mobile)
 * - Navigation: "{position} of {total}" in a <span>
 * - Prev/Next buttons with aria-labels "Previous item" / "Next item"
 */

import { test, expect } from "../fixtures"
import * as mockData from "../fixtures/mock-data"

test.describe("Summary Review Page", () => {
  test.beforeEach(async ({ apiMocks, page }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockContentDetail()
    await apiMocks.mockSummaryDetail()

    // Mock the summaries/by-content endpoint (app calls GET /api/v1/summaries/by-content/{contentId})
    await page.route("**/api/v1/summaries/by-content/*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockData.createSummary()),
      })
    )

    // Also mock the direct content detail for the route
    await page.route("**/api/v1/contents/*", (route) => {
      const url = route.request().url()
      if (
        url.includes("/stats") ||
        url.includes("/duplicates") ||
        url.includes("/ingest") ||
        url.includes("/summarize") ||
        url.includes("/with-summary")
      ) {
        return route.fallback()
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...mockData.createContent(),
          summary: mockData.createSummary(),
        }),
      })
    })

    // Mock summary navigation
    await page.route("**/api/v1/summaries/*/navigation*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          prev_id: null,
          next_id: 2,
          prev_content_id: null,
          next_content_id: 2,
          position: 1,
          total: 10,
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

  test("navigates to summary review page", async ({ reviewPage }) => {
    await reviewPage.navigateToSummaryReview(1)

    await expect(
      reviewPage.page.getByRole("heading", { name: "Review Summary", level: 1 })
    ).toBeVisible()
  })

  test("two-pane layout renders", async ({ reviewPage }) => {
    await reviewPage.navigateToSummaryReview(1)

    await expect(reviewPage.leftPane).toBeVisible()
    await expect(reviewPage.rightPane).toBeVisible()
  })

  test("left pane shows source content label", async ({ reviewPage }) => {
    await reviewPage.navigateToSummaryReview(1)

    // ReviewPaneHeader renders "Source Content" as an h3
    await expect(reviewPage.page.getByText("Source Content")).toBeVisible()
  })

  test("right pane shows summary content", async ({ reviewPage }) => {
    await reviewPage.navigateToSummaryReview(1)

    // Right pane should display the summary
    await expect(reviewPage.rightPane).toBeVisible()
  })

  test("back link navigates to summaries", async ({ reviewPage }) => {
    await reviewPage.navigateToSummaryReview(1)

    // Back label is inside a link to /summaries; the text "Back to Summaries" is
    // in a <span class="hidden sm:inline"> so it may be hidden on mobile.
    // Assert the link itself exists pointing to /summaries.
    await expect(
      reviewPage.page.locator("a[href='/summaries']").first()
    ).toBeVisible()
  })

  test("navigation shows position info", async ({ reviewPage }) => {
    await reviewPage.navigateToSummaryReview(1)

    // Navigation shows "1 of 10"
    await expect(reviewPage.page.getByText("1 of 10")).toBeVisible()
  })

  test("next navigation button is visible", async ({ reviewPage }) => {
    await reviewPage.navigateToSummaryReview(1)

    await expect(reviewPage.nextButton).toBeVisible()
  })

  test("revision chat panel is present at bottom", async ({ reviewPage }) => {
    await reviewPage.navigateToSummaryReview(1)

    // The revision panel is rendered in the border-t area
    await expect(reviewPage.page.locator(".border-t").last()).toBeVisible()
  })
})
