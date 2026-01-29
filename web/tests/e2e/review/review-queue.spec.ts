/**
 * Review Queue Index Page Tests
 *
 * Tests for /review page: review categories, links to individual
 * review pages, pending item counts, and empty state.
 */

import { test, expect } from "../../fixtures"

test.describe("Review Queue Index Page", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("page shows Review Queue heading", async ({ reviewPage }) => {
    await reviewPage.navigate()

    await expect(reviewPage.page.getByText("Review Queue")).toBeVisible()
  })

  test("page shows description", async ({ reviewPage }) => {
    await reviewPage.navigate()

    await expect(
      reviewPage.page.getByText(/items pending review and approval/i)
    ).toBeVisible()
  })

  test("page shows Pending Digests section", async ({ reviewPage }) => {
    await reviewPage.navigate()

    await expect(reviewPage.page.getByText("Pending Digests")).toBeVisible()
  })

  test("page shows Digests card with description", async ({ reviewPage }) => {
    await reviewPage.navigate()

    await expect(reviewPage.page.getByText("Digests")).toBeVisible()
    await expect(
      reviewPage.page.getByText(/review and approve digest content/i)
    ).toBeVisible()
  })

  test("page shows Pending Scripts section", async ({ reviewPage }) => {
    await reviewPage.navigate()

    await expect(reviewPage.page.getByText("Pending Scripts")).toBeVisible()
  })

  test("page shows Scripts card with description", async ({ reviewPage }) => {
    await reviewPage.navigate()

    await expect(reviewPage.page.getByText("Scripts")).toBeVisible()
    await expect(
      reviewPage.page.getByText(/review podcast scripts/i)
    ).toBeVisible()
  })

  test("empty state shows when no digests pending", async ({ reviewPage }) => {
    await reviewPage.navigate()

    await expect(
      reviewPage.page.getByText(/no digests pending review/i)
    ).toBeVisible()
  })

  test("empty state shows when no scripts pending", async ({ reviewPage }) => {
    await reviewPage.navigate()

    await expect(
      reviewPage.page.getByText(/no scripts pending review/i)
    ).toBeVisible()
  })
})
