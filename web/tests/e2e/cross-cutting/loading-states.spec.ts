/**
 * Loading States E2E Tests
 *
 * Verifies that skeleton loaders or loading indicators appear while
 * the API response is in flight. Uses `mockWithDelay` to simulate
 * slow network conditions so the loading UI is observable.
 */

import { test, expect } from "../../fixtures"
import * as mockData from "../fixtures/mock-data"

test.describe("Loading States", () => {
  test("Contents page shows loading indicator during data fetch", async ({
    page,
    apiMocks,
  }) => {
    // Set up delayed responses to make loading state visible
    await apiMocks.mockWithDelay(
      "**/api/v1/contents?*",
      mockData.createContentListResponse(),
      2000
    )
    await apiMocks.mockWithDelay(
      "**/api/v1/contents",
      mockData.createContentListResponse(),
      2000
    )
    await apiMocks.mockWithDelay(
      "**/api/v1/contents/stats",
      mockData.createContentStats(),
      2000
    )
    await apiMocks.mockChatConfig()
    await apiMocks.mockSystemHealth()

    await page.goto("/contents")

    // A loading indicator (spinner, skeleton, or shimmer) should appear
    const loadingIndicator = page
      .locator('[class*="skeleton"], [class*="Skeleton"], [class*="animate-pulse"], [role="progressbar"], [class*="spinner"], [class*="loading"]')
      .first()

    await expect(loadingIndicator).toBeVisible({ timeout: 3_000 })

    // After the delay, data should eventually appear
    await expect(page.getByRole("table").or(page.getByText(/AI Weekly/i))).toBeVisible({
      timeout: 10_000,
    })
  })

  test("Digests page shows loading indicator during data fetch", async ({
    page,
    apiMocks,
  }) => {
    await apiMocks.mockWithDelay(
      "**/api/v1/digests/?*",
      [mockData.createDigestListItem({ id: 1 })],
      2000
    )
    await apiMocks.mockWithDelay(
      "**/api/v1/digests/",
      [mockData.createDigestListItem({ id: 1 })],
      2000
    )
    await apiMocks.mockWithDelay(
      "**/api/v1/digests/stats",
      mockData.createDigestStatistics(),
      2000
    )
    await apiMocks.mockChatConfig()
    await apiMocks.mockSystemHealth()

    await page.goto("/digests")

    const loadingIndicator = page
      .locator('[class*="skeleton"], [class*="Skeleton"], [class*="animate-pulse"], [role="progressbar"], [class*="spinner"], [class*="loading"]')
      .first()

    await expect(loadingIndicator).toBeVisible({ timeout: 3_000 })

    // Data should eventually load
    await expect(
      page.getByRole("table").or(page.getByText(/Daily AI/i))
    ).toBeVisible({ timeout: 10_000 })
  })

  test("Summaries page shows loading indicator during data fetch", async ({
    page,
    apiMocks,
  }) => {
    await apiMocks.mockWithDelay(
      "**/api/v1/summaries?*",
      mockData.createSummaryListResponse(),
      2000
    )
    await apiMocks.mockWithDelay(
      "**/api/v1/summaries",
      mockData.createSummaryListResponse(),
      2000
    )
    await apiMocks.mockWithDelay(
      "**/api/v1/summaries/stats",
      { total: 25, by_model: { "claude-haiku-4-5": 20, "claude-sonnet-4-5": 5 } },
      2000
    )
    await apiMocks.mockChatConfig()
    await apiMocks.mockSystemHealth()

    await page.goto("/summaries")

    const loadingIndicator = page
      .locator('[class*="skeleton"], [class*="Skeleton"], [class*="animate-pulse"], [role="progressbar"], [class*="spinner"], [class*="loading"]')
      .first()

    await expect(loadingIndicator).toBeVisible({ timeout: 3_000 })

    // Data should eventually load
    await expect(
      page.getByRole("table").or(page.getByText(/AI Weekly/i))
    ).toBeVisible({ timeout: 10_000 })
  })

  test("Loading indicator disappears after data loads", async ({
    page,
    apiMocks,
  }) => {
    await apiMocks.mockWithDelay(
      "**/api/v1/contents?*",
      mockData.createContentListResponse(),
      1500
    )
    await apiMocks.mockWithDelay(
      "**/api/v1/contents",
      mockData.createContentListResponse(),
      1500
    )
    await apiMocks.mockWithDelay(
      "**/api/v1/contents/stats",
      mockData.createContentStats(),
      1500
    )
    await apiMocks.mockChatConfig()
    await apiMocks.mockSystemHealth()

    await page.goto("/contents")

    // Wait for data to fully load
    await expect(
      page.getByRole("table").or(page.getByText(/AI Weekly/i))
    ).toBeVisible({ timeout: 10_000 })

    // Loading indicators should be gone
    const skeletons = page.locator('[class*="skeleton"], [class*="Skeleton"], [class*="animate-pulse"]')
    const skeletonCount = await skeletons.count()

    // Either no skeleton elements or they are hidden
    if (skeletonCount > 0) {
      for (let i = 0; i < skeletonCount; i++) {
        await expect(skeletons.nth(i)).not.toBeVisible()
      }
    }
  })
})
