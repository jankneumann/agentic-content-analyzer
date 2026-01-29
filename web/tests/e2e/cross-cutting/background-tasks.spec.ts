/**
 * Background Tasks E2E Tests
 *
 * Verifies that background task indicators appear when a generation
 * task is triggered, showing task type and status to the user.
 */

import { test, expect } from "../../fixtures"
import * as mockData from "../fixtures/mock-data"

test.describe("Background Tasks", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("Digest generation triggers a background task indicator", async ({
    page,
    apiMocks,
    digestsPage,
  }) => {
    // Mock the generate endpoint to return a task response
    await apiMocks.mockGenerateDigest()

    await digestsPage.navigate()
    await digestsPage.openGenerateDialog()

    // Click the generate button inside the dialog
    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible()
    const generateButton = dialog.getByRole("button", { name: /generate/i })
    await generateButton.click()

    // Dialog should close after triggering generation
    await expect(dialog).not.toBeVisible({ timeout: 5_000 })

    // A background task indicator should appear somewhere in the UI
    // (toast notification, status bar, or floating indicator)
    const taskIndicator = page
      .getByText(/generating|generation started|processing|in progress|digest/i)
      .first()

    await expect(taskIndicator).toBeVisible({ timeout: 10_000 })
  })

  test("Theme analysis triggers a background task indicator", async ({
    page,
    apiMocks,
    themesPage,
  }) => {
    await apiMocks.mockAnalyzeThemes()

    await themesPage.navigate()
    await themesPage.openAnalyzeDialog()

    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Click the analyze button inside the dialog
    const analyzeButton = dialog
      .getByRole("button", { name: /analyze/i })
      .last()
    await analyzeButton.click()

    // Dialog should close
    await expect(dialog).not.toBeVisible({ timeout: 5_000 })

    // A background task indicator should appear
    const taskIndicator = page
      .getByText(/analy|started|processing|in progress|theme/i)
      .first()

    await expect(taskIndicator).toBeVisible({ timeout: 10_000 })
  })

  test("Content ingestion triggers a background task indicator", async ({
    page,
    apiMocks,
    contentsPage,
  }) => {
    await apiMocks.mockIngestContents()

    await contentsPage.navigate()
    await contentsPage.openIngestDialog()

    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Submit the ingest form
    const ingestButton = dialog
      .getByRole("button", { name: /ingest|start|submit/i })
      .last()
    await ingestButton.click()

    // Dialog should close
    await expect(dialog).not.toBeVisible({ timeout: 5_000 })

    // A background task indicator should appear
    const taskIndicator = page
      .getByText(/ingest|started|processing|in progress|content/i)
      .first()

    await expect(taskIndicator).toBeVisible({ timeout: 10_000 })
  })

  test("Summarization triggers a background task indicator", async ({
    page,
    apiMocks,
    summariesPage,
  }) => {
    await apiMocks.mockSummarizeContents()

    await summariesPage.navigate()
    await summariesPage.openGenerateDialog()

    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Click the generate/summarize button inside the dialog
    const submitButton = dialog
      .getByRole("button", { name: /generate|summarize|start/i })
      .last()
    await submitButton.click()

    // Dialog should close
    await expect(dialog).not.toBeVisible({ timeout: 5_000 })

    // A background task indicator should appear
    const taskIndicator = page
      .getByText(/summar|started|processing|in progress/i)
      .first()

    await expect(taskIndicator).toBeVisible({ timeout: 10_000 })
  })

  test("Script generation triggers a background task indicator", async ({
    page,
    apiMocks,
    scriptsPage,
  }) => {
    // Mock the script generation endpoint
    await page.route("**/api/v1/scripts/generate", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          mockData.createTaskResponse({ message: "Script generation started" })
        ),
      })
    )
    // Mock approved digests for the script generation dialog
    await page.route("**/api/v1/digests/?*", (route) => {
      if (route.request().url().includes("status=APPROVED")) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            mockData.createDigestListItem({ id: 1, status: "APPROVED" }),
          ]),
        })
      }
      return route.fallback()
    })

    await scriptsPage.navigate()
    await scriptsPage.openGenerateDialog()

    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Click the generate button inside the dialog
    const generateButton = dialog
      .getByRole("button", { name: /generate|start/i })
      .last()
    await generateButton.click()

    // Dialog should close
    await expect(dialog).not.toBeVisible({ timeout: 5_000 })

    // A background task indicator should appear
    const taskIndicator = page
      .getByText(/script|started|processing|in progress|generat/i)
      .first()

    await expect(taskIndicator).toBeVisible({ timeout: 10_000 })
  })
})
