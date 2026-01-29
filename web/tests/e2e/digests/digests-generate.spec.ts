/**
 * Generate Digest Dialog Tests
 *
 * Tests the generate digest dialog for configuring and triggering
 * daily or weekly digest generation.
 */

import { test, expect } from "../../fixtures"

test.describe("Generate Digest Dialog", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockGenerateDigest()
  })

  test("Generate button opens the dialog", async ({ digestsPage }) => {
    await digestsPage.navigate()

    // Click the "Generate Digest" button in page actions
    await digestsPage.openGenerateDialog()

    // Dialog should appear
    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show title
    await expect(dialog.getByText("Generate Digest")).toBeVisible()

    // Should show description
    await expect(dialog.getByText(/configure and generate a new/i)).toBeVisible()
  })

  test("can select Daily or Weekly via digest type tabs", async ({ digestsPage }) => {
    await digestsPage.navigate()
    await digestsPage.openGenerateDialog()

    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should have Daily and Weekly tabs
    const dailyTab = dialog.getByRole("tab", { name: /daily/i })
    const weeklyTab = dialog.getByRole("tab", { name: /weekly/i })
    await expect(dailyTab).toBeVisible()
    await expect(weeklyTab).toBeVisible()

    // Daily should be selected by default
    await expect(dailyTab).toHaveAttribute("data-state", "active")

    // Switch to Weekly
    await weeklyTab.click()
    await expect(weeklyTab).toHaveAttribute("data-state", "active")

    // Description should update
    await expect(dialog.getByText(/past week/i)).toBeVisible()
  })

  test("date range inputs available for custom dates", async ({ digestsPage }) => {
    await digestsPage.navigate()
    await digestsPage.openGenerateDialog()

    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show Date Range section
    await expect(dialog.getByText("Date Range")).toBeVisible()

    // Click "Customize" to show custom date inputs
    await dialog.getByRole("button", { name: /customize/i }).click()

    // Date inputs should appear
    const startDateInput = dialog.locator('input[type="date"]').first()
    const endDateInput = dialog.locator('input[type="date"]').last()
    await expect(startDateInput).toBeVisible()
    await expect(endDateInput).toBeVisible()
  })

  test("section limit configuration is available", async ({ digestsPage }) => {
    await digestsPage.navigate()
    await digestsPage.openGenerateDialog()

    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show Section Limits label
    await expect(dialog.getByText("Section Limits")).toBeVisible()

    // Should have strategic, technical, and trends limit selectors
    await expect(dialog.getByText("Strategic")).toBeVisible()
    await expect(dialog.getByText("Technical")).toBeVisible()
    await expect(dialog.getByText("Trends")).toBeVisible()
  })

  test("submit triggers generation and closes dialog", async ({ digestsPage }) => {
    await digestsPage.navigate()
    await digestsPage.openGenerateDialog()

    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Click the Generate button in the dialog footer
    const generateButton = dialog.getByRole("button", { name: /generate daily digest/i })
    await expect(generateButton).toBeVisible()
    await generateButton.click()

    // Dialog should close after submission
    await expect(dialog).not.toBeVisible({ timeout: 5000 })
  })

  test("dialog closes after submission when weekly is selected", async ({ digestsPage }) => {
    await digestsPage.navigate()
    await digestsPage.openGenerateDialog()

    const dialog = digestsPage.page.getByRole("dialog")

    // Switch to Weekly
    await dialog.getByRole("tab", { name: /weekly/i }).click()

    // Click the Generate button
    const generateButton = dialog.getByRole("button", { name: /generate weekly digest/i })
    await generateButton.click()

    // Dialog should close
    await expect(dialog).not.toBeVisible({ timeout: 5000 })
  })

  test("cancel button closes dialog without generating", async ({ digestsPage }) => {
    await digestsPage.navigate()
    await digestsPage.openGenerateDialog()

    const dialog = digestsPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Click Cancel
    await dialog.getByRole("button", { name: /cancel/i }).click()

    // Dialog should close
    await expect(dialog).not.toBeVisible()
  })
})
