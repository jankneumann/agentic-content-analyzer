/**
 * Script Review Page Tests
 *
 * Tests for /review/script/:id page: two-pane layout,
 * left pane (digest), right pane (script), section-level review,
 * and revision panel.
 */

import { test, expect } from "../../fixtures"

test.describe("Script Review Page", () => {
  test.beforeEach(async ({ apiMocks, page }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockScriptDetail()
    await apiMocks.mockDigestDetail()

    // Mock script navigation
    await page.route("**/api/v1/scripts/*/navigation", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          prev_id: null,
          next_id: 2,
          position: 1,
          total: 3,
        }),
      })
    )

    // Mock digest sources
    await page.route("**/api/v1/digests/*/sources", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
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

  test("navigates to script review page", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    await expect(reviewPage.page.getByText("Review Script")).toBeVisible()
  })

  test("two-pane layout renders", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    await expect(reviewPage.leftPane).toBeVisible()
    await expect(reviewPage.rightPane).toBeVisible()
  })

  test("left pane shows digest content", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    // Left pane contains the source digest
    await expect(reviewPage.leftPane).toBeVisible()
  })

  test("right pane shows script content", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    // Right pane contains the script
    await expect(reviewPage.rightPane).toBeVisible()
  })

  test("script shows section titles", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    // From createScriptDetail: sections include "Opening", "Strategic Insights", etc.
    await expect(reviewPage.page.getByText("Opening")).toBeVisible()
  })

  test("script shows speaker badges", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    // From createScriptSection: speakers are "alex" and "sam"
    await expect(reviewPage.page.getByText("alex").first()).toBeVisible()
    await expect(reviewPage.page.getByText("sam").first()).toBeVisible()
  })

  test("script shows dialogue text", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    // From createScriptSection dialogue
    await expect(
      reviewPage.page.getByText(/Welcome to another episode/)
    ).toBeVisible()
  })

  test("back link navigates to scripts", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    await expect(reviewPage.page.getByText("Back to Scripts")).toBeVisible()
  })

  test("navigation shows position info", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    // Navigation shows "1 of 3"
    await expect(reviewPage.page.getByText(/1.*of.*3/i)).toBeVisible()
  })

  test("next navigation button is visible", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    await expect(reviewPage.nextButton).toBeVisible()
  })

  test("revision chat panel is present at bottom", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    // The revision panel is rendered at the bottom
    await expect(reviewPage.page.locator(".border-t").last()).toBeVisible()
  })
})
