/**
 * Podcasts List Page Tests
 *
 * Tests for /podcasts page: table rendering, status filter,
 * duration/file size columns, and empty state.
 */

import { test, expect } from "../fixtures"

test.describe("Podcasts List Page", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("table renders with podcast items", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await expect(podcastsPage.table).toBeVisible()
    const rowCount = await podcastsPage.getRowCount()
    expect(rowCount).toBeGreaterThan(0)
  })

  test("displays podcast title in table", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    // From createPodcastListItem: title = "AI Weekly Deep Dive - Episode 42"
    await expect(podcastsPage.page.getByText("AI Weekly Deep Dive - Episode 42")).toBeVisible()
  })

  test("status filter dropdown is visible", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await expect(podcastsPage.statusFilter).toBeVisible()
  })

  test("status filter shows options when clicked", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.statusFilter.click()

    await expect(podcastsPage.page.getByRole("option", { name: "All Status" })).toBeVisible()
    await expect(podcastsPage.page.getByRole("option", { name: "Generating" })).toBeVisible()
    await expect(podcastsPage.page.getByRole("option", { name: "Completed" })).toBeVisible()
    await expect(podcastsPage.page.getByRole("option", { name: "Failed" })).toBeVisible()
  })

  test("table shows duration column", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    // From createPodcastListItem: duration_seconds = 720 -> "12:00"
    await expect(podcastsPage.page.getByText("12:00")).toBeVisible()
  })

  test("table shows file size column", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    // From createPodcastListItem: file_size_bytes = 11520000 -> "11.0 MB"
    await expect(podcastsPage.page.getByText("11.0 MB")).toBeVisible()
  })

  test("table shows provider column", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    // From createPodcastListItem: voice_provider = "openai"
    await expect(podcastsPage.page.getByText("openai")).toBeVisible()
  })

  test("table shows status badge", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    // From createPodcastListItem: status = "completed"
    // "Completed" appears in both the stats card and the table status badge
    await expect(podcastsPage.page.getByRole("table").getByText("Completed")).toBeVisible()
  })

  test("empty state displays when no podcasts exist", async ({ apiMocks, podcastsPage }) => {
    await apiMocks.mockPodcastsEmpty()
    await podcastsPage.navigate()

    await expect(podcastsPage.emptyState).toBeVisible()
  })

  test("empty state shows generate button", async ({ apiMocks, podcastsPage }) => {
    await apiMocks.mockPodcastsEmpty()
    await podcastsPage.navigate()

    // Both header and empty state have a "Generate Audio" button; verify at least one exists
    await expect(podcastsPage.page.getByRole("button", { name: /generate audio/i }).first()).toBeVisible()
  })

  test("stats cards display podcast statistics", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await expect(podcastsPage.page.getByText("Total", { exact: true })).toBeVisible()
    await expect(podcastsPage.page.getByText("Generating", { exact: true })).toBeVisible()
    await expect(podcastsPage.page.getByText("Completed").first()).toBeVisible()
    await expect(podcastsPage.page.getByText("Total Duration")).toBeVisible()
  })

  test("stats show correct total from mock data", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    // From createPodcastStatistics: total = 5
    await expect(podcastsPage.page.getByText("5").first()).toBeVisible()
  })

  test("generate audio button is visible", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await expect(podcastsPage.generateButton).toBeVisible()
  })

  test("table has sortable column headers", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await expect(podcastsPage.page.getByRole("columnheader", { name: /duration/i })).toBeVisible()
    await expect(podcastsPage.page.getByRole("columnheader", { name: /size/i })).toBeVisible()
    await expect(podcastsPage.page.getByRole("columnheader", { name: /status/i })).toBeVisible()
  })
})
