/**
 * Contents Detail Dialog Tests
 *
 * Tests the content detail dialog that opens when clicking a table row
 * or the view icon in the contents list.
 */

import { test, expect } from "../fixtures"
import { createContent } from "../fixtures/mock-data"

test.describe("Content Detail Dialog", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockContentDetail()
  })

  test("clicking view icon opens detail dialog", async ({ contentsPage }) => {
    await contentsPage.navigate()

    // Click the view button on the first row
    const viewButton = contentsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view content/i })
    await viewButton.click()

    // Dialog should open
    const dialog = contentsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Dialog should show "Content Details" title
    await expect(dialog.getByText("Content Details")).toBeVisible()
  })

  test("dialog shows content title and description", async ({ contentsPage }) => {
    await contentsPage.navigate()

    // Open detail dialog
    const viewButton = contentsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view content/i })
    await viewButton.click()

    const dialog = contentsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show the content title from mock data
    await expect(dialog.getByText("AI Weekly: GPT-5 Announced")).toBeVisible()
  })

  test("dialog shows source and publication metadata", async ({ contentsPage }) => {
    await contentsPage.navigate()

    const viewButton = contentsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view content/i })
    await viewButton.click()

    const dialog = contentsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show publication from createContent mock
    await expect(dialog.getByText("AI Weekly Newsletter")).toBeVisible()

    // Should show author
    await expect(dialog.getByText("Jane Smith")).toBeVisible()

    // Should show source type badge (use exact match to avoid matching "gmail_html")
    await expect(dialog.getByText("Gmail", { exact: true })).toBeVisible()
  })

  test("dialog shows markdown content", async ({ contentsPage }) => {
    await contentsPage.navigate()

    const viewButton = contentsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view content/i })
    await viewButton.click()

    const dialog = contentsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should render the markdown content (rendered view by default)
    // The mock has "# AI Weekly\n\nGPT-5 has been announced..." as markdown content
    // Use a unique text from the body to avoid matching title/publication
    await expect(dialog.getByText("GPT-5 has been announced")).toBeVisible()
  })

  test("dialog shows metadata section with parser and status", async ({ contentsPage }) => {
    await contentsPage.navigate()

    const viewButton = contentsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view content/i })
    await viewButton.click()

    const dialog = contentsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show parser info
    await expect(dialog.getByText("gmail_html")).toBeVisible()

    // Should show status badge
    await expect(dialog.getByText("Completed")).toBeVisible()
  })

  test("dialog closes on X button click", async ({ contentsPage }) => {
    await contentsPage.navigate()

    const viewButton = contentsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view content/i })
    await viewButton.click()

    const dialog = contentsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Close via the X button
    await contentsPage.closeDialog()

    // Dialog should be gone
    await expect(dialog).not.toBeVisible()
  })

  test("dialog closes on Escape key", async ({ contentsPage }) => {
    await contentsPage.navigate()

    const viewButton = contentsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view content/i })
    await viewButton.click()

    const dialog = contentsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Close via Escape
    await contentsPage.closeDialogViaEscape()

    // Dialog should be gone
    await expect(dialog).not.toBeVisible()
  })

  test("dialog has responsive sizing on mobile", async ({ contentsPage }) => {
    // Set mobile viewport
    await contentsPage.page.setViewportSize({ width: 390, height: 844 })

    await contentsPage.navigate()

    const viewButton = contentsPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view content/i })
    await viewButton.click()

    const dialog = contentsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Dialog should be visible and not overflow the viewport on mobile
    const dialogBox = await dialog.boundingBox()
    expect(dialogBox).not.toBeNull()
    if (dialogBox) {
      expect(dialogBox.width).toBeLessThanOrEqual(390)
    }
  })
})
