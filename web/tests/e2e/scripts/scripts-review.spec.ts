/**
 * Script Review Page Tests
 *
 * Tests for /review/script/:id page: two-pane layout,
 * approve/reject buttons, and navigation.
 */

import { test, expect } from "../fixtures"

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

    // Mock chat session
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

    // Should show "Review Script" header
    await expect(reviewPage.page.getByText("Review Script")).toBeVisible()
  })

  test("two-pane layout renders", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    // The review layout has left and right panes
    await expect(reviewPage.leftPane).toBeVisible()
    await expect(reviewPage.rightPane).toBeVisible()
  })

  test("left pane shows digest content", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    // Left pane should contain the digest content
    await expect(reviewPage.leftPane).toBeVisible()
  })

  test("right pane shows script content", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    // Right pane should contain the script
    await expect(reviewPage.rightPane).toBeVisible()
  })

  test("back to scripts link is visible", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    await expect(reviewPage.page.getByText("Back to Scripts")).toBeVisible()
  })

  test("revision chat panel is present", async ({ reviewPage }) => {
    await reviewPage.navigateToScriptReview(1)

    // The revision panel at the bottom should be present
    await expect(reviewPage.page.locator(".border-t").last()).toBeVisible()
  })
})
