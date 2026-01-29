/**
 * Summary Detail Dialog Tests
 *
 * Tests the summary detail dialog that opens when clicking a row
 * or view icon in the summaries list.
 */

import { test, expect } from "../fixtures"

test.describe("Summary Detail Dialog", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockSummaryDetail()
  })

  test("clicking view icon opens the detail dialog", async ({ summariesPage }) => {
    await summariesPage.navigate()

    // Click the view button on the first row
    const viewButton = summariesPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view summary details/i })
    await viewButton.click()

    // Dialog should open
    const dialog = summariesPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show dialog title
    await expect(dialog.getByText("Summary Details")).toBeVisible()
  })

  test("shows executive summary text", async ({ summariesPage }) => {
    await summariesPage.navigate()

    const viewButton = summariesPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view summary details/i })
    await viewButton.click()

    const dialog = summariesPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show Executive Summary heading
    await expect(dialog.getByText("Executive Summary")).toBeVisible()

    // Should show the executive summary text from mock
    await expect(
      dialog.getByText(/OpenAI announced GPT-5 with significant improvements/i)
    ).toBeVisible()
  })

  test("shows key themes as badges", async ({ summariesPage }) => {
    await summariesPage.navigate()

    const viewButton = summariesPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view summary details/i })
    await viewButton.click()

    const dialog = summariesPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show Key Themes heading
    await expect(dialog.getByText("Key Themes")).toBeVisible()

    // Should show theme badges from createSummary mock
    await expect(dialog.getByText("Large Language Models")).toBeVisible()
    await expect(dialog.getByText("AI Safety")).toBeVisible()
    await expect(dialog.getByText("Multimodal AI")).toBeVisible()
  })

  test("shows strategic insights section", async ({ summariesPage }) => {
    await summariesPage.navigate()

    const viewButton = summariesPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view summary details/i })
    await viewButton.click()

    const dialog = summariesPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show Strategic Insights
    await expect(dialog.getByText("Strategic Insights")).toBeVisible()
    await expect(
      dialog.getByText(/GPT-5 represents a significant leap/i)
    ).toBeVisible()
  })

  test("shows technical details section", async ({ summariesPage }) => {
    await summariesPage.navigate()

    const viewButton = summariesPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view summary details/i })
    await viewButton.click()

    const dialog = summariesPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show Technical Details
    await expect(dialog.getByText("Technical Details")).toBeVisible()
    await expect(
      dialog.getByText(/mixture-of-experts with 8 specialized modules/i)
    ).toBeVisible()
  })

  test("shows actionable items section", async ({ summariesPage }) => {
    await summariesPage.navigate()

    const viewButton = summariesPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view summary details/i })
    await viewButton.click()

    const dialog = summariesPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show Actionable Items
    await expect(dialog.getByText("Actionable Items")).toBeVisible()
    await expect(
      dialog.getByText(/Evaluate GPT-5 API for existing summarization pipeline/i)
    ).toBeVisible()
  })

  test("shows relevance scores metadata", async ({ summariesPage }) => {
    await summariesPage.navigate()

    const viewButton = summariesPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view summary details/i })
    await viewButton.click()

    const dialog = summariesPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Should show model metadata
    await expect(dialog.getByText("claude-haiku-4-5")).toBeVisible()

    // Should show processing time
    await expect(dialog.getByText("4.2s")).toBeVisible()

    // Should show token usage
    await expect(dialog.getByText("2,500")).toBeVisible()
  })

  test("dialog closes on X button click", async ({ summariesPage }) => {
    await summariesPage.navigate()

    const viewButton = summariesPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view summary details/i })
    await viewButton.click()

    const dialog = summariesPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Close via the Close button in footer
    await dialog.getByRole("button", { name: /close/i }).first().click()

    await expect(dialog).not.toBeVisible()
  })

  test("dialog closes on Escape key", async ({ summariesPage }) => {
    await summariesPage.navigate()

    const viewButton = summariesPage.page
      .locator("tbody tr")
      .first()
      .getByRole("button", { name: /view summary details/i })
    await viewButton.click()

    const dialog = summariesPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Close via Escape key
    await summariesPage.closeDialogViaEscape()

    await expect(dialog).not.toBeVisible()
  })
})
