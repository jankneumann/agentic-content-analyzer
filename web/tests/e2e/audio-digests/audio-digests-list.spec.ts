/**
 * Audio Digests List Page Tests
 *
 * Tests for /audio-digests page: table rendering, status filter,
 * delete button with confirmation, empty state, and stats display.
 */

import { test, expect } from "../fixtures"

test.describe("Audio Digests List Page", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("table renders with audio digest items", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await expect(audioDigestsPage.table).toBeVisible()
    const rowCount = await audioDigestsPage.getRowCount()
    expect(rowCount).toBeGreaterThan(0)
  })

  test("displays digest ID in table", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    // From createAudioDigestListItem: digest_id = 1
    await expect(audioDigestsPage.page.getByText("Digest #1")).toBeVisible()
  })

  test("status filter dropdown is visible", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await expect(audioDigestsPage.statusFilter).toBeVisible()
  })

  test("status filter shows options when clicked", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.statusFilter.click()

    await expect(audioDigestsPage.page.getByRole("option", { name: "All Status" })).toBeVisible()
    await expect(audioDigestsPage.page.getByRole("option", { name: "Pending" })).toBeVisible()
    await expect(audioDigestsPage.page.getByRole("option", { name: "Processing" })).toBeVisible()
    await expect(audioDigestsPage.page.getByRole("option", { name: "Completed" })).toBeVisible()
    await expect(audioDigestsPage.page.getByRole("option", { name: "Failed" })).toBeVisible()
  })

  test("table shows voice column", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    // From createAudioDigestListItem: voice = "nova"
    await expect(audioDigestsPage.page.getByText("nova")).toBeVisible()
  })

  test("table shows speed column", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    // From createAudioDigestListItem: speed = 1.0
    await expect(audioDigestsPage.page.getByText("1x").first()).toBeVisible()
  })

  test("table shows duration column", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    // From createAudioDigestListItem: duration_seconds = 480 -> "8:00"
    await expect(audioDigestsPage.page.getByText("8:00")).toBeVisible()
  })

  test("delete button is visible on table rows", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await expect(
      audioDigestsPage.page.getByRole("button", { name: "Delete audio digest" }).first()
    ).toBeVisible()
  })

  test("clicking delete button opens confirmation dialog", async ({ apiMocks, audioDigestsPage, page }) => {
    // Mock the delete endpoint
    await page.route("**/api/v1/audio-digests/*", (route) => {
      if (route.request().method() === "DELETE") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ message: "Deleted" }),
        })
      }
      return route.fallback()
    })

    await audioDigestsPage.navigate()

    const deleteButton = audioDigestsPage.page
      .getByRole("button", { name: "Delete audio digest" })
      .first()
    await deleteButton.click()

    // Confirmation dialog should appear
    const dialog = await audioDigestsPage.waitForDialog()
    await expect(dialog.getByText("Delete Audio Digest?")).toBeVisible()
    await expect(dialog.getByText(/permanently delete/i)).toBeVisible()
  })

  test("delete confirmation dialog has Cancel and Delete buttons", async ({ apiMocks, audioDigestsPage, page }) => {
    await page.route("**/api/v1/audio-digests/*", (route) => {
      if (route.request().method() === "DELETE") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ message: "Deleted" }),
        })
      }
      return route.fallback()
    })

    await audioDigestsPage.navigate()

    const deleteButton = audioDigestsPage.page
      .getByRole("button", { name: "Delete audio digest" })
      .first()
    await deleteButton.click()

    const dialog = await audioDigestsPage.waitForDialog()
    await expect(dialog.getByRole("button", { name: "Cancel" })).toBeVisible()
    await expect(dialog.getByRole("button", { name: "Delete" })).toBeVisible()
  })

  test("empty state displays when no audio digests exist", async ({ apiMocks, audioDigestsPage }) => {
    await apiMocks.mockAudioDigestsEmpty()
    await audioDigestsPage.navigate()

    await expect(audioDigestsPage.emptyState).toBeVisible()
  })

  test("empty state shows generate button", async ({ apiMocks, audioDigestsPage }) => {
    await apiMocks.mockAudioDigestsEmpty()
    await audioDigestsPage.navigate()

    // Both header and empty state have a "Generate Audio" button; verify at least one exists
    await expect(
      audioDigestsPage.page.getByRole("button", { name: /generate audio/i }).first()
    ).toBeVisible()
  })

  test("stats cards display audio digest statistics", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await expect(audioDigestsPage.page.getByText("Total", { exact: true })).toBeVisible()
    await expect(audioDigestsPage.page.getByText("Processing", { exact: true })).toBeVisible()
    await expect(audioDigestsPage.page.getByText("Completed").first()).toBeVisible()
    await expect(audioDigestsPage.page.getByText("Total Duration")).toBeVisible()
  })

  test("stats show correct total from mock data", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    // From createAudioDigestStatistics: total = 8
    await expect(audioDigestsPage.page.getByText("8").first()).toBeVisible()
  })

  test("generate audio button is visible", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await expect(audioDigestsPage.generateButton).toBeVisible()
  })
})
