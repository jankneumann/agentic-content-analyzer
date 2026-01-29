/**
 * Smoke Tests
 *
 * Integration tests that hit the REAL backend with NO mocking.
 * Tagged with @smoke so they are excluded from the default test run
 * and only execute via the "smoke" Playwright project.
 *
 * Prerequisites:
 *   - Backend API running at the configured base URL
 *   - Database seeded (or at least accessible)
 */

import { test, expect } from "@playwright/test"

test.describe("Smoke Tests @smoke", () => {
  test("dashboard loads with real API", async ({ page }) => {
    await page.goto("/")

    await expect(page.locator("#root")).toBeVisible()
    await expect(page.locator("main")).toBeVisible()
  })

  test("navigation works end-to-end", async ({ page }) => {
    await page.goto("/")

    await page.getByRole("link", { name: "Content" }).click()
    await expect(page).toHaveURL(/\/contents/)

    await page.getByRole("link", { name: "Digests" }).click()
    await expect(page).toHaveURL(/\/digests/)
  })

  test("contents page fetches real data", async ({ page }) => {
    await page.goto("/contents")

    // Wait for either table data or empty state
    await expect(
      page.getByRole("table").or(page.getByText(/no content/i))
    ).toBeVisible({ timeout: 10000 })
  })

  test("summaries page loads without errors", async ({ page }) => {
    await page.goto("/summaries")

    await expect(
      page.getByRole("table").or(page.getByText(/no summar/i))
    ).toBeVisible({ timeout: 10000 })
  })

  test("themes page loads without errors", async ({ page }) => {
    await page.goto("/themes")

    // Themes page should show either analysis data or an empty prompt
    await expect(
      page.locator("main").getByText(/theme|analysis|no analysis|analyze/i)
    ).toBeVisible({ timeout: 10000 })
  })

  test("settings page loads without errors", async ({ page }) => {
    await page.goto("/settings")

    await expect(page.locator("main")).toBeVisible()
    await expect(page.locator("h1, h2").first()).toBeVisible()
  })
})
