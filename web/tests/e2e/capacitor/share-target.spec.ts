/**
 * E2E Tests: Share Target — Web Guard
 *
 * Verifies the share target handler's web-mode behavior:
 * initShareTarget() is called at module scope in __root.tsx but
 * exits immediately when isNative() returns false.
 *
 * Task 12.2 — E2E tests for share target flow
 */

import { test, expect } from "../fixtures"

test.describe("Share Target — Web Guard", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("app loads without share handler errors", async ({
    dashboardPage,
  }) => {
    await dashboardPage.navigate()
    await expect(dashboardPage.page.locator("main")).toBeVisible()
  })

  test("no share-related toasts appear on web startup", async ({
    dashboardPage,
  }) => {
    await dashboardPage.navigate()

    // Wait a moment to let any async handlers fire
    await dashboardPage.page.waitForTimeout(1000)

    // No share processing toasts should appear
    await expect(
      dashboardPage.page.getByText(/url saved for processing/i),
    ).not.toBeVisible()
    await expect(
      dashboardPage.page.getByText(/offline.*queued/i),
    ).not.toBeVisible()
  })

  test("settings page loads normally with share handler initialized", async ({
    settingsPage,
  }) => {
    // Verify share handler doesn't interfere with page rendering
    await settingsPage.navigate()
    await expect(settingsPage.page.locator("main")).toBeVisible()
  })
})
