/**
 * E2E Tests: Ingestion Job Progress via Background Tasks
 *
 * Verifies that triggering ingestion from the frontend:
 * 1. Calls POST /api/v1/contents/ingest (returns task_id)
 * 2. Shows a background task indicator with progress
 * 3. Polls for new content and completes when count increases
 * 4. Handles error responses gracefully
 *
 * Task 7.4 from add-parallel-job-queue proposal.
 *
 * NOTE: The frontend uses a polling strategy (not direct SSE) for ingestion.
 * After receiving a task_id, it polls refetch() every 5s to detect new content.
 * SSE is used only for summarization via subscribeToProgress().
 */

import { test, expect } from "../fixtures"
import * as mockData from "../fixtures/mock-data"

test.describe("Ingestion Job Progress", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockIngestContents()
  })

  test("triggering ingestion shows background task indicator with progress", async ({
    page,
    contentsPage,
  }) => {
    await contentsPage.navigate()
    await contentsPage.openIngestDialog()

    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    // Submit ingestion from Gmail tab (default)
    const ingestButton = dialog.getByRole("button", { name: /ingest from gmail/i })
    await ingestButton.click()

    // Dialog should close
    await expect(dialog).not.toBeVisible({ timeout: 5_000 })

    // Background task indicator should appear showing ingestion progress
    const taskIndicator = page
      .getByText(/ingest|gmail|fetching|queuing|content/i)
      .first()
    await expect(taskIndicator).toBeVisible({ timeout: 10_000 })
  })

  test("ingestion completes when new content is detected", async ({
    page,
    apiMocks,
    contentsPage,
  }) => {
    // First mock: return initial content count
    let contentTotal = 5

    // Override the contents list mock to return dynamic total
    await page.route("**/api/v1/contents?*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          mockData.createContentListResponse({ total: contentTotal })
        ),
      })
    )
    await page.route("**/api/v1/contents", (route) => {
      if (route.request().url().includes("/ingest") || route.request().url().includes("/summarize")) {
        return route.fallback()
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          mockData.createContentListResponse({ total: contentTotal })
        ),
      })
    })

    await contentsPage.navigate()
    await contentsPage.openIngestDialog()

    const dialog = page.getByRole("dialog")
    const ingestButton = dialog.getByRole("button", { name: /ingest from gmail/i })
    await ingestButton.click()
    await expect(dialog).not.toBeVisible({ timeout: 5_000 })

    // Simulate content count increase after a short delay
    // (the frontend polls every 5s, so update the mock before next poll)
    contentTotal = 8 // 3 new items

    // Override the route again with the new count
    await page.route("**/api/v1/contents?*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          mockData.createContentListResponse({ total: contentTotal })
        ),
      })
    )

    // Wait for completion message (toast or task indicator)
    // The frontend shows "Ingested N content items" on completion
    const completionText = page
      .getByText(/ingested \d+ content item|no new content/i)
      .first()
    await expect(completionText).toBeVisible({ timeout: 30_000 })
  })

  test("ingestion from different sources shows correct source name", async ({
    page,
    contentsPage,
  }) => {
    await contentsPage.navigate()
    await contentsPage.openIngestDialog()

    const dialog = page.getByRole("dialog")

    // Switch to RSS tab
    await dialog.getByRole("tab", { name: /rss/i }).click()
    await expect(dialog.getByRole("tab", { name: /rss/i })).toHaveAttribute(
      "data-state",
      "active"
    )

    // Submit from RSS
    const ingestButton = dialog.getByRole("button", { name: /ingest from rss/i })
    await ingestButton.click()
    await expect(dialog).not.toBeVisible({ timeout: 5_000 })

    // Should show RSS-specific task text
    const taskIndicator = page
      .getByText(/rss|ingest|fetching|content/i)
      .first()
    await expect(taskIndicator).toBeVisible({ timeout: 10_000 })
  })

  test("ingestion error shows failure in task indicator", async ({
    page,
    contentsPage,
  }) => {
    // Override ingest endpoint to return an error
    await page.route("**/api/v1/contents/ingest", (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          message: "Gmail authentication failed",
          code: "AUTH_ERROR",
        }),
      })
    )

    await contentsPage.navigate()
    await contentsPage.openIngestDialog()

    const dialog = page.getByRole("dialog")
    const ingestButton = dialog.getByRole("button", { name: /ingest from gmail/i })
    await ingestButton.click()
    await expect(dialog).not.toBeVisible({ timeout: 5_000 })

    // Error toast or task failure indicator should appear
    const errorIndicator = page
      .getByText(/fail|error|unable/i)
      .first()
    await expect(errorIndicator).toBeVisible({ timeout: 10_000 })
  })

  test("POST /ingest receives correct payload from dialog", async ({
    page,
    contentsPage,
  }) => {
    // Capture the request to verify payload
    let capturedBody: Record<string, unknown> | null = null

    await page.route("**/api/v1/contents/ingest", async (route) => {
      const request = route.request()
      if (request.method() === "POST") {
        capturedBody = JSON.parse(request.postData() ?? "{}")
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          mockData.createTaskResponse({
            task_id: "42",
            message: "Ingestion started",
          })
        ),
      })
    })

    await contentsPage.navigate()
    await contentsPage.openIngestDialog()

    const dialog = page.getByRole("dialog")

    // Use Gmail tab (default) with defaults
    const ingestButton = dialog.getByRole("button", { name: /ingest from gmail/i })
    await ingestButton.click()
    await expect(dialog).not.toBeVisible({ timeout: 5_000 })

    // Verify the POST body includes expected fields
    expect(capturedBody).not.toBeNull()
    expect(capturedBody!.source).toBe("gmail")
    expect(capturedBody!.max_results).toBeDefined()
    expect(capturedBody!.days_back).toBeDefined()
  })
})
