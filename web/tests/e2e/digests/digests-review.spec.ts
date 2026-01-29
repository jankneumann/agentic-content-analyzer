/**
 * Digest Review Integration Tests
 *
 * Tests the review queue page and navigation to digest review pages.
 */

import { test, expect } from "../../fixtures"

test.describe("Digest Review Integration", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("review queue page loads with pending sections", async ({ reviewPage }) => {
    await reviewPage.navigate()

    // Should show the Review Queue heading
    await expect(reviewPage.page.getByText("Review Queue")).toBeVisible()

    // Should show the Pending Digests section
    await expect(reviewPage.page.getByText("Pending Digests")).toBeVisible()

    // Should show the Digests card
    await expect(reviewPage.page.getByText("Review and approve digest content before delivery")).toBeVisible()
  })

  test("review queue shows pending scripts section", async ({ reviewPage }) => {
    await reviewPage.navigate()

    // Should show the Pending Scripts section
    await expect(reviewPage.page.getByText("Pending Scripts")).toBeVisible()

    // Should show the Scripts card
    await expect(reviewPage.page.getByText("Review podcast scripts before audio generation")).toBeVisible()
  })

  test("navigation to digest review page works", async ({ reviewPage, apiMocks }) => {
    // Mock digest detail for the review page
    await apiMocks.mockDigestDetail()

    await reviewPage.navigateToDigestReview(1)

    // Should navigate to the digest review URL
    await expect(reviewPage.page).toHaveURL(/\/review\/digest\/1/)
  })

  test("digest list has review links for reviewable digests", async ({ digestsPage }) => {
    await digestsPage.navigate()

    // The PENDING_REVIEW digest (second row) should have a review link
    const secondRow = digestsPage.page.locator("tbody tr").nth(1)
    const reviewLink = secondRow.getByRole("link", { name: /review digest/i })
    await expect(reviewLink).toBeVisible()

    // The review link should point to the review page
    await expect(reviewLink).toHaveAttribute("href", /\/review\/digest\/2/)
  })

  test("COMPLETED digests also have review links", async ({ digestsPage }) => {
    await digestsPage.navigate()

    // The COMPLETED digest (first row) should also have a review link
    const firstRow = digestsPage.page.locator("tbody tr").first()
    const reviewLink = firstRow.getByRole("link", { name: /review digest/i })
    await expect(reviewLink).toBeVisible()

    // Should link to review page with digest id
    await expect(reviewLink).toHaveAttribute("href", /\/review\/digest\/1/)
  })
})
