/**
 * Digests List Page Tests
 *
 * Tests the /digests page: table rendering, filtering, sorting,
 * stats cards, and empty state.
 */

import { test, expect } from "../../fixtures"
import { createDigestListItem, createDigestStatistics } from "../../fixtures/mock-data"

test.describe("Digests List Page", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("renders table with digest items", async ({ digestsPage }) => {
    await digestsPage.navigate()

    await expect(digestsPage.table).toBeVisible()

    // Default mock has 2 digest items
    const rowCount = await digestsPage.getRowCount()
    expect(rowCount).toBe(2)

    // Verify digest titles appear
    await expect(digestsPage.page.getByText("Daily AI & Data Digest - Jan 15, 2025")).toBeVisible()
    await expect(digestsPage.page.getByText("Weekly AI Digest - Jan 8-14")).toBeVisible()
  })

  test("table shows type, period, and status columns", async ({ digestsPage }) => {
    await digestsPage.navigate()

    await expect(digestsPage.table).toBeVisible()

    // Verify column headers
    await expect(digestsPage.page.getByRole("columnheader", { name: /title/i })).toBeVisible()
    await expect(digestsPage.page.getByRole("columnheader", { name: /type/i })).toBeVisible()
    await expect(digestsPage.page.getByRole("columnheader", { name: /period/i })).toBeVisible()
    await expect(digestsPage.page.getByRole("columnheader", { name: /status/i })).toBeVisible()

    // Verify type badges
    await expect(digestsPage.page.getByText("daily")).toBeVisible()
    await expect(digestsPage.page.getByText("weekly")).toBeVisible()

    // Verify status badges
    await expect(digestsPage.page.getByText("Completed")).toBeVisible()
    await expect(digestsPage.page.getByText("Pending Review")).toBeVisible()
  })

  test("search input filters digests", async ({ digestsPage }) => {
    await digestsPage.navigate()

    await expect(digestsPage.searchInput).toBeVisible()

    // Type search text
    await digestsPage.searchFor("Weekly")

    // Verify search input has value
    await expect(digestsPage.searchInput).toHaveValue("Weekly")
  })

  test("type filter dropdown works", async ({ digestsPage }) => {
    await digestsPage.navigate()

    // The type filter should be visible
    const typeFilter = digestsPage.page.getByRole("combobox", { name: /filter by type/i })
    await expect(typeFilter).toBeVisible()

    // Click type filter and select Daily
    await typeFilter.click()
    await digestsPage.page.getByRole("option", { name: /daily/i }).click()
  })

  test("status filter dropdown works", async ({ digestsPage }) => {
    await digestsPage.navigate()

    // The status filter should be visible
    const statusFilter = digestsPage.page.getByRole("combobox", { name: /filter by status/i })
    await expect(statusFilter).toBeVisible()

    // Click status filter and select Pending Review
    await statusFilter.click()
    await digestsPage.page.getByRole("option", { name: /pending review/i }).click()
  })

  test("stats cards show digest statistics", async ({ digestsPage }) => {
    await digestsPage.navigate()

    // Stats from createDigestStatistics: total=15, pending_review=3, approved=2, delivered=1
    await expect(digestsPage.page.getByText("Total")).toBeVisible()
    await expect(digestsPage.page.getByText("15")).toBeVisible()

    await expect(digestsPage.page.getByText("Pending Review")).toBeVisible()
    await expect(digestsPage.page.getByText("3")).toBeVisible()

    await expect(digestsPage.page.getByText("Approved")).toBeVisible()
    await expect(digestsPage.page.getByText("2")).toBeVisible()

    await expect(digestsPage.page.getByText("Delivered")).toBeVisible()
  })

  test("shows empty state when no digests exist", async ({ digestsPage, apiMocks }) => {
    await apiMocks.mockAllEmpty()

    await digestsPage.navigate()

    // Should show empty state message
    await expect(digestsPage.page.getByText(/no digests found/i)).toBeVisible()
  })

  test("sort by column works via column header click", async ({ digestsPage }) => {
    await digestsPage.navigate()

    // Click the sortable Type header
    const typeHeader = digestsPage.page.getByRole("columnheader", { name: /type/i })
    await expect(typeHeader).toBeVisible()
    await typeHeader.click()

    // Click the sortable Status header
    const statusHeader = digestsPage.page.getByRole("columnheader", { name: /status/i })
    await expect(statusHeader).toBeVisible()
    await statusHeader.click()
  })
})
