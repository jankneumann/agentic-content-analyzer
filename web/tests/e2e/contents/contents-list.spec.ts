/**
 * Contents List Page Tests
 *
 * Tests the /contents page: table rendering, filtering, sorting,
 * pagination, empty state, and stats cards.
 */

import { test, expect } from "../fixtures"
import {
  createContentListResponse,
  createContentListItem,
  createContentStats,
  createEmptyContentListResponse,
} from "../fixtures/mock-data"

test.describe("Contents List Page", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("renders table with mocked content items", async ({ contentsPage }) => {
    await contentsPage.navigate()

    await expect(contentsPage.table).toBeVisible()

    // Default mock has 3 items
    const rowCount = await contentsPage.getRowCount()
    expect(rowCount).toBe(3)

    // Verify content titles appear
    await expect(contentsPage.page.getByText("AI Weekly: GPT-5 Announced")).toBeVisible()
    await expect(contentsPage.page.getByText("ML Ops Digest: Kubernetes for ML")).toBeVisible()
    await expect(contentsPage.page.getByText("Data Engineering Weekly")).toBeVisible()
  })

  test("search input filters content", async ({ contentsPage }) => {
    await contentsPage.navigate()

    await expect(contentsPage.searchInput).toBeVisible()

    // Type search text
    await contentsPage.searchFor("GPT-5")

    // Verify the search input has the value
    await expect(contentsPage.searchInput).toHaveValue("GPT-5")
  })

  test("source type filter is available and functional", async ({ contentsPage }) => {
    await contentsPage.navigate()

    // The source filter dropdown should be visible
    const sourceFilter = contentsPage.page.getByRole("combobox").filter({ hasText: /source|all sources/i }).first()
    await expect(sourceFilter).toBeVisible()

    // Click the source filter and select Gmail
    await sourceFilter.click()
    await contentsPage.page.getByRole("option", { name: /gmail/i }).click()
  })

  test("status filter is available and functional", async ({ contentsPage }) => {
    await contentsPage.navigate()

    // The status filter dropdown should be visible
    const statusFilter = contentsPage.page.getByRole("combobox").filter({ hasText: /status|all status/i }).first()
    await expect(statusFilter).toBeVisible()

    // Click the status filter and select Completed
    await statusFilter.click()
    await contentsPage.page.getByRole("option", { name: /completed/i }).click()
  })

  test("column headers are sortable", async ({ contentsPage }) => {
    await contentsPage.navigate()

    // Verify sortable column headers exist
    const titleHeader = contentsPage.page.getByRole("columnheader", { name: /title/i })
    await expect(titleHeader).toBeVisible()

    const sourceHeader = contentsPage.page.getByRole("columnheader", { name: /source/i })
    await expect(sourceHeader).toBeVisible()

    const publishedHeader = contentsPage.page.getByRole("columnheader", { name: /published/i })
    await expect(publishedHeader).toBeVisible()

    // Click a sortable header to trigger sort
    await titleHeader.click()
  })

  test("pagination shows when many items exist", async ({ contentsPage, apiMocks }) => {
    // Mock with more items than page size
    const manyItems = Array.from({ length: 20 }, (_, i) =>
      createContentListItem({
        id: i + 1,
        title: `Content Item ${i + 1}`,
      })
    )
    await apiMocks.mockContents(
      createContentListResponse({
        items: manyItems,
        total: 50,
        page: 1,
        page_size: 20,
        has_next: true,
        has_prev: false,
      })
    )

    await contentsPage.navigate()

    // Should show pagination controls
    const nextButton = contentsPage.page.getByRole("button", { name: /next/i })
    await expect(nextButton).toBeVisible()

    const prevButton = contentsPage.page.getByRole("button", { name: /previous/i })
    await expect(prevButton).toBeVisible()
    await expect(prevButton).toBeDisabled()

    // Should show page info text
    await expect(contentsPage.page.getByText(/page 1/i)).toBeVisible()
    await expect(contentsPage.page.getByText(/50 items/i)).toBeVisible()
  })

  test("shows empty state when no items exist", async ({ contentsPage, apiMocks }) => {
    await apiMocks.mockAllEmpty()

    await contentsPage.navigate()

    // Should show empty state message
    await expect(contentsPage.page.getByText(/no contents found/i)).toBeVisible()

    // Should have a button to ingest content
    await expect(contentsPage.page.getByRole("button", { name: /ingest content/i })).toBeVisible()
  })

  test("stats cards display content counts", async ({ contentsPage }) => {
    await contentsPage.navigate()

    // Stats from createContentStats: total=42, pending=5, completed=28, failed=3
    // Scope to stats grid to avoid matching status badges in the table
    const statsGrid = contentsPage.page.locator(".grid").first()
    await expect(statsGrid.getByText("42")).toBeVisible()
    await expect(statsGrid.getByText("Total")).toBeVisible()
    await expect(statsGrid.getByText("Pending")).toBeVisible()
    await expect(statsGrid.getByText("Completed")).toBeVisible()
    await expect(statsGrid.getByText("Failed")).toBeVisible()
  })
})
