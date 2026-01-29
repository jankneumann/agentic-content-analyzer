/**
 * Review Queue Index Page Tests
 *
 * Tests for /review page: review categories, links to individual
 * review pages, pending item counts, and empty state.
 *
 * All assertions are scoped to <main> to avoid matching sidebar nav text.
 */

import { test, expect } from "../fixtures"

test.describe("Review Queue Index Page", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("page shows Review Queue heading", async ({ reviewPage }) => {
    await reviewPage.navigate()

    await expect(
      reviewPage.page.locator("main").getByRole("heading", { name: "Review Queue", level: 1 })
    ).toBeVisible()
  })

  test("page shows description", async ({ reviewPage }) => {
    await reviewPage.navigate()

    await expect(
      reviewPage.page.locator("main").getByText(/items pending review and approval/i)
    ).toBeVisible()
  })

  test("page shows Pending Digests section", async ({ reviewPage }) => {
    await reviewPage.navigate()

    await expect(
      reviewPage.page.locator("main").getByRole("heading", { name: "Pending Digests" })
    ).toBeVisible()
  })

  test("page shows Digests card with description", async ({ reviewPage }) => {
    await reviewPage.navigate()

    const main = reviewPage.page.locator("main")
    await expect(main.getByText("Digests", { exact: true })).toBeVisible()
    await expect(
      main.getByText(/review and approve digest content/i)
    ).toBeVisible()
  })

  test("page shows Pending Scripts section", async ({ reviewPage }) => {
    await reviewPage.navigate()

    await expect(
      reviewPage.page.locator("main").getByRole("heading", { name: "Pending Scripts" })
    ).toBeVisible()
  })

  test("page shows Scripts card with description", async ({ reviewPage }) => {
    await reviewPage.navigate()

    const main = reviewPage.page.locator("main")
    await expect(main.getByText("Scripts", { exact: true }).first()).toBeVisible()
    await expect(
      main.getByText(/review podcast scripts/i)
    ).toBeVisible()
  })

  test("empty state shows when no digests pending", async ({ reviewPage }) => {
    await reviewPage.navigate()

    await expect(
      reviewPage.page.locator("main").getByText(/no digests pending review/i)
    ).toBeVisible()
  })

  test("empty state shows when no scripts pending", async ({ reviewPage }) => {
    await reviewPage.navigate()

    await expect(
      reviewPage.page.locator("main").getByText(/no scripts pending review/i)
    ).toBeVisible()
  })
})
