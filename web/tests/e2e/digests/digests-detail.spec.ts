/**
 * Digest Detail Dialog Tests
 *
 * Tests the digest detail dialog including executive overview,
 * tabbed sections, recommendations, sources, and review actions.
 */

import { test, expect } from "../fixtures"
import { createDigestDetail, createDigestListItem } from "../fixtures/mock-data"

test.describe("Digest Detail Dialog", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockDigestDetail()
  })

  test("clicking view icon opens the detail dialog", async ({ digestsPage }) => {
    await digestsPage.navigate()

    // Click the view button on the first row
    const viewButton = digestsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view digest/i })
    await viewButton.click()

    // Dialog should open
    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show digest title
    await expect(dialog.getByText("Daily AI & Data Digest - Jan 15, 2025")).toBeVisible()
  })

  test("shows executive overview section", async ({ digestsPage }) => {
    await digestsPage.navigate()

    const viewButton = digestsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view digest/i })
    await viewButton.click()

    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show Executive Overview heading
    await expect(dialog.getByText("Executive Overview")).toBeVisible()

    // Should show the overview text from mock
    await expect(
      dialog.getByText(/key developments center on GPT-5/i)
    ).toBeVisible()
  })

  test("has tabs for Strategic, Technical, and Trends sections", async ({ digestsPage }) => {
    await digestsPage.navigate()

    const viewButton = digestsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view digest/i })
    await viewButton.click()

    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should have three section tabs
    await expect(dialog.getByRole("tab", { name: /strategic/i })).toBeVisible()
    await expect(dialog.getByRole("tab", { name: /technical/i })).toBeVisible()
    await expect(dialog.getByRole("tab", { name: /trends/i })).toBeVisible()
  })

  test("strategic tab shows section content", async ({ digestsPage }) => {
    await digestsPage.navigate()

    const viewButton = digestsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view digest/i })
    await viewButton.click()

    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Strategic tab should be active by default
    await expect(dialog.getByRole("tab", { name: /strategic/i })).toHaveAttribute(
      "data-state",
      "active"
    )

    // Should show strategic insight content from mock
    await expect(
      dialog.getByText("GPT-5 Changes Enterprise AI Landscape")
    ).toBeVisible()
  })

  test("technical tab shows section content when clicked", async ({ digestsPage }) => {
    await digestsPage.navigate()

    const viewButton = digestsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view digest/i })
    await viewButton.click()

    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Click Technical tab
    await dialog.getByRole("tab", { name: /technical/i }).click()

    // Should show technical content from mock
    await expect(
      dialog.getByText("Mixture-of-Experts Architecture")
    ).toBeVisible()
  })

  test("trends tab shows section content when clicked", async ({ digestsPage }) => {
    await digestsPage.navigate()

    const viewButton = digestsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view digest/i })
    await viewButton.click()

    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Click Trends tab
    await dialog.getByRole("tab", { name: /trends/i }).click()

    // Should show emerging trends content from mock
    await expect(dialog.getByText("AI Safety Regulation")).toBeVisible()
  })

  test("shows actionable recommendations", async ({ digestsPage }) => {
    await digestsPage.navigate()

    const viewButton = digestsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view digest/i })
    await viewButton.click()

    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show Actionable Recommendations heading
    await expect(dialog.getByText("Actionable Recommendations")).toBeVisible()

    // Should show recommendation items from mock
    await expect(
      dialog.getByText(/Evaluate GPT-5 for strategic initiatives/i)
    ).toBeVisible()
  })

  test("shows sources section", async ({ digestsPage }) => {
    await digestsPage.navigate()

    const viewButton = digestsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view digest/i })
    await viewButton.click()

    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show Sources heading with count
    await expect(dialog.getByText(/sources/i)).toBeVisible()

    // Should show source item from mock
    await expect(dialog.getByText("AI Weekly: GPT-5 Announced")).toBeVisible()
  })

  test("shows Approve and Reject buttons for PENDING_REVIEW status", async ({
    digestsPage,
    apiMocks,
  }) => {
    // Mock with PENDING_REVIEW status
    await apiMocks.mockDigestDetail(
      createDigestDetail({ status: "PENDING_REVIEW" })
    )

    await digestsPage.navigate()

    // Click the second row which has PENDING_REVIEW status
    const viewButton = digestsPage.page
      .locator("tbody tr")
      .nth(1)
      .getByRole("button", { name: /view digest/i })
    await viewButton.click()

    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show Approve and Reject buttons
    await expect(dialog.getByRole("button", { name: /approve/i })).toBeVisible()
    await expect(dialog.getByRole("button", { name: /reject/i })).toBeVisible()
  })

  test("dialog closes on Close button click", async ({ digestsPage }) => {
    await digestsPage.navigate()

    const viewButton = digestsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view digest/i })
    await viewButton.click()

    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Close via the Close button in the footer
    await dialog.getByRole("button", { name: /close/i }).first().click()

    await expect(dialog).not.toBeVisible()
  })

  test("dialog closes on Escape key", async ({ digestsPage }) => {
    await digestsPage.navigate()

    const viewButton = digestsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view digest/i })
    await viewButton.click()

    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Close via Escape
    await digestsPage.closeDialogViaEscape()

    await expect(dialog).not.toBeVisible()
  })
})
