/**
 * Generate Summaries Dialog Tests
 *
 * Tests the generate summaries dialog for triggering AI summarization.
 */

import { test, expect } from "../fixtures"

test.describe("Generate Summaries Dialog", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockSummarizeContents()
  })

  test("Generate button opens the dialog", async ({ summariesPage }) => {
    await summariesPage.navigate()

    // Click the "Generate Summaries" button in page actions
    await summariesPage.openGenerateDialog()

    // Dialog should appear
    const dialog = summariesPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show title
    await expect(dialog.getByText("Generate Summaries")).toBeVisible()

    // Should show description
    await expect(dialog.getByText(/summarize content using ai/i)).toBeVisible()
  })

  test("dialog has mode selection tabs", async ({ summariesPage }) => {
    await summariesPage.navigate()
    await summariesPage.openGenerateDialog()

    const dialog = summariesPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should have "All Pending" and "Specific IDs" tabs
    await expect(dialog.getByRole("tab", { name: /all pending/i })).toBeVisible()
    await expect(dialog.getByRole("tab", { name: /specific ids/i })).toBeVisible()

    // "All Pending" should be active by default
    await expect(dialog.getByRole("tab", { name: /all pending/i })).toHaveAttribute(
      "data-state",
      "active"
    )
  })

  test("dialog shows pending count and configuration options", async ({ summariesPage }) => {
    await summariesPage.navigate()
    await summariesPage.openGenerateDialog()

    const dialog = summariesPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show pending items info
    await expect(dialog.getByText(/content items pending/i)).toBeVisible()

    // Should show force re-summarize toggle
    await expect(dialog.getByText(/force re-summarize/i)).toBeVisible()
  })

  test("can switch to Specific IDs mode", async ({ summariesPage }) => {
    await summariesPage.navigate()
    await summariesPage.openGenerateDialog()

    const dialog = summariesPage.page.getByRole("dialog")

    // Switch to Specific IDs tab
    await dialog.getByRole("tab", { name: /specific ids/i }).click()
    await expect(dialog.getByRole("tab", { name: /specific ids/i })).toHaveAttribute(
      "data-state",
      "active"
    )

    // Should show input for content IDs
    await expect(dialog.getByPlaceholder(/e\.g\., 123/i)).toBeVisible()
  })

  test("submit triggers summarization and closes dialog", async ({ summariesPage }) => {
    await summariesPage.navigate()
    await summariesPage.openGenerateDialog()

    const dialog = summariesPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Click the summarize button
    const summarizeButton = dialog.getByRole("button", { name: /summarize/i })
    await expect(summarizeButton).toBeVisible()
    await summarizeButton.click()

    // Dialog should close after submission
    await expect(dialog).not.toBeVisible({ timeout: 5000 })
  })

  test("cancel button closes dialog without action", async ({ summariesPage }) => {
    await summariesPage.navigate()
    await summariesPage.openGenerateDialog()

    const dialog = summariesPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Click Cancel
    await dialog.getByRole("button", { name: /cancel/i }).click()

    // Dialog should close
    await expect(dialog).not.toBeVisible()
  })
})
