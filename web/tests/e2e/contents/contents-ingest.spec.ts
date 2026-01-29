/**
 * Contents Ingest Dialog Tests
 *
 * Tests the ingest content dialog for fetching content
 * from Gmail, RSS feeds, and YouTube.
 */

import { test, expect } from "../../fixtures"

test.describe("Ingest Contents Dialog", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockIngestContents()
  })

  test("Ingest button opens the dialog", async ({ contentsPage }) => {
    await contentsPage.navigate()

    // Click the "Ingest New" button
    await contentsPage.openIngestDialog()

    // Dialog should appear
    const dialog = contentsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show "Ingest Content" title
    await expect(dialog.getByText("Ingest Content")).toBeVisible()
  })

  test("dialog shows source tabs (Gmail, RSS, YouTube)", async ({ contentsPage }) => {
    await contentsPage.navigate()
    await contentsPage.openIngestDialog()

    const dialog = contentsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should have three source tabs
    await expect(dialog.getByRole("tab", { name: /gmail/i })).toBeVisible()
    await expect(dialog.getByRole("tab", { name: /rss/i })).toBeVisible()
    await expect(dialog.getByRole("tab", { name: /youtube/i })).toBeVisible()

    // Gmail should be selected by default
    const gmailTab = dialog.getByRole("tab", { name: /gmail/i })
    await expect(gmailTab).toHaveAttribute("data-state", "active")
  })

  test("can switch between source tabs", async ({ contentsPage }) => {
    await contentsPage.navigate()
    await contentsPage.openIngestDialog()

    const dialog = contentsPage.page.getByRole("dialog")

    // Switch to RSS tab
    await dialog.getByRole("tab", { name: /rss/i }).click()
    await expect(dialog.getByRole("tab", { name: /rss/i })).toHaveAttribute(
      "data-state",
      "active"
    )

    // Description should update to RSS
    await expect(dialog.getByText(/rss feeds/i)).toBeVisible()

    // Switch to YouTube tab
    await dialog.getByRole("tab", { name: /youtube/i }).click()
    await expect(dialog.getByRole("tab", { name: /youtube/i })).toHaveAttribute(
      "data-state",
      "active"
    )

    // Description should update to YouTube
    await expect(dialog.getByText(/youtube/i)).toBeVisible()
  })

  test("max results slider is adjustable", async ({ contentsPage }) => {
    await contentsPage.navigate()
    await contentsPage.openIngestDialog()

    const dialog = contentsPage.page.getByRole("dialog")

    // Should show max results label and value
    await expect(dialog.getByText(/maximum/i)).toBeVisible()

    // Default value should be displayed (50)
    await expect(dialog.getByText("50")).toBeVisible()

    // The slider should be present
    const slider = dialog.getByRole("slider")
    await expect(slider).toBeVisible()
  })

  test("days back slider is present", async ({ contentsPage }) => {
    await contentsPage.navigate()
    await contentsPage.openIngestDialog()

    const dialog = contentsPage.page.getByRole("dialog")

    // Should show Days Back label
    await expect(dialog.getByText(/days back/i)).toBeVisible()

    // Default value should be displayed (7 days)
    await expect(dialog.getByText("7 days")).toBeVisible()
  })

  test("submit button triggers ingest and closes dialog", async ({ contentsPage }) => {
    await contentsPage.navigate()
    await contentsPage.openIngestDialog()

    const dialog = contentsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Click the ingest button in the dialog footer
    const ingestSubmitButton = dialog.getByRole("button", { name: /ingest from gmail/i })
    await expect(ingestSubmitButton).toBeVisible()
    await ingestSubmitButton.click()

    // Dialog should close after submission
    await expect(dialog).not.toBeVisible({ timeout: 5000 })
  })

  test("cancel button closes dialog without action", async ({ contentsPage }) => {
    await contentsPage.navigate()
    await contentsPage.openIngestDialog()

    const dialog = contentsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Click Cancel
    await dialog.getByRole("button", { name: /cancel/i }).click()

    // Dialog should close
    await expect(dialog).not.toBeVisible()
  })
})
