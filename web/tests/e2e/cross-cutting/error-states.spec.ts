/**
 * Error States E2E Tests
 *
 * Verifies that API errors (500 responses) produce visible error UI
 * on each main page, rather than leaving the user with a blank screen
 * or an unhandled exception.
 */

import { test, expect } from "../fixtures"

test.describe("Error States", () => {
  test("Contents page shows error UI when API returns 500", async ({
    page,
    apiMocks,
    contentsPage,
  }) => {
    await apiMocks.mockAllErrors()
    await contentsPage.navigate()

    // The page should display an error indicator
    await expect(
      page.getByText(/error|failed|something went wrong|could not load/i)
    ).toBeVisible({ timeout: 10_000 })
  })

  test("Digests page shows error UI when API returns 500", async ({
    page,
    apiMocks,
    digestsPage,
  }) => {
    await apiMocks.mockAllErrors()
    await digestsPage.navigate()

    await expect(
      page.getByText(/error|failed|something went wrong|could not load/i)
    ).toBeVisible({ timeout: 10_000 })
  })

  test("Summaries page shows error UI when API returns 500", async ({
    page,
    apiMocks,
    summariesPage,
  }) => {
    await apiMocks.mockAllErrors()
    await summariesPage.navigate()

    await expect(
      page.getByText(/error|failed|something went wrong|could not load/i)
    ).toBeVisible({ timeout: 10_000 })
  })

  test("Scripts page shows error UI when API returns 500", async ({
    page,
    apiMocks,
    scriptsPage,
  }) => {
    await apiMocks.mockAllErrors()
    await scriptsPage.navigate()

    await expect(
      page.getByText(/error|failed|something went wrong|could not load/i)
    ).toBeVisible({ timeout: 10_000 })
  })

  test("Themes page shows empty state when API returns 500", async ({
    page,
    apiMocks,
    themesPage,
  }) => {
    await apiMocks.mockAllErrors()
    await themesPage.navigate()

    // When themes API fails, the page renders the empty/no-analysis state
    // rather than an explicit error message
    await expect(
      page.getByText(/no theme analysis|error|failed|something went wrong|could not load/i)
    ).toBeVisible({ timeout: 10_000 })
  })

  test("Retry mechanism is available after an error", async ({
    page,
    apiMocks,
    contentsPage,
  }) => {
    await apiMocks.mockAllErrors()
    await contentsPage.navigate()

    // Wait for error UI to appear
    await expect(
      page.getByText(/error|failed|something went wrong|could not load/i)
    ).toBeVisible({ timeout: 10_000 })

    // There should be a retry button or the page should allow the user
    // to recover (retry button, or a link back to reload)
    const retryButton = page.getByRole("button", { name: /retry|try again|reload/i })
    const retryLink = page.getByRole("link", { name: /retry|try again|reload/i })

    await expect(retryButton.or(retryLink)).toBeVisible({ timeout: 5_000 })
  })

  test("Specific endpoint error shows contextual message", async ({
    page,
    apiMocks,
    contentsPage,
  }) => {
    // Mock only the contents endpoint with a specific error
    await apiMocks.mockWithError(
      "**/api/v1/contents?*",
      503,
      "Service temporarily unavailable"
    )
    await apiMocks.mockWithError(
      "**/api/v1/contents",
      503,
      "Service temporarily unavailable"
    )
    await apiMocks.mockContentStats()
    await apiMocks.mockChatConfig()
    await apiMocks.mockSystemHealth()

    await contentsPage.navigate()

    // The page should show some error indication
    await expect(
      page.getByText(/error|unavailable|failed|could not load/i)
    ).toBeVisible({ timeout: 10_000 })
  })
})
