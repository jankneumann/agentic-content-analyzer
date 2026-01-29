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

    await page.getByRole("link", { name: "Content", exact: true }).click()
    await expect(page).toHaveURL(/\/contents/)

    await page.getByRole("link", { name: "Digests", exact: true }).click()
    await expect(page).toHaveURL(/\/digests/)
  })

  test("contents page loads without errors", async ({ page }) => {
    await page.goto("/contents")

    // Page heading renders regardless of API data
    await expect(
      page.getByRole("heading", { name: "Contents", level: 1 })
    ).toBeVisible({ timeout: 10000 })
  })

  test("summaries page loads without errors", async ({ page }) => {
    await page.goto("/summaries")

    // Page heading renders regardless of API data
    await expect(
      page.getByRole("heading", { name: "Summaries", level: 1 })
    ).toBeVisible({ timeout: 10000 })
  })

  test("themes page loads without errors", async ({ page }) => {
    await page.goto("/themes")

    // Themes page should show the heading
    await expect(
      page.getByRole("heading", { name: "Themes", level: 1 })
    ).toBeVisible({ timeout: 10000 })
  })

  test("settings page loads without errors", async ({ page }) => {
    await page.goto("/settings")

    await expect(page.locator("main")).toBeVisible()
    await expect(page.locator("h1, h2").first()).toBeVisible()
  })
})
