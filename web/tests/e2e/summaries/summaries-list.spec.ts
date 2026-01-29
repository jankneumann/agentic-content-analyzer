/**
 * Summaries List Page Tests
 *
 * Tests the /summaries page: table rendering, filtering, sorting,
 * and empty state.
 */

import { test, expect } from "../fixtures"
import {
  createSummaryListResponse,
  createSummaryListItem,
  createEmptyPaginatedResponse,
} from "../fixtures/mock-data"
import type { SummaryListItem } from "../../../src/types"

test.describe("Summaries List Page", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("renders table with summary items", async ({ summariesPage }) => {
    await summariesPage.navigate()

    await expect(summariesPage.table).toBeVisible()

    // Default mock has 2 summary items
    const rowCount = await summariesPage.getRowCount()
    expect(rowCount).toBe(2)

    // Verify summary titles appear
    await expect(summariesPage.page.getByText("AI Weekly: GPT-5 Announced")).toBeVisible()
    await expect(summariesPage.page.getByText("ML Ops Digest: Kubernetes for ML")).toBeVisible()
  })

  test("table shows publication, themes, and model columns", async ({ summariesPage }) => {
    await summariesPage.navigate()

    await expect(summariesPage.table).toBeVisible()

    // Verify column headers
    await expect(summariesPage.page.getByRole("columnheader", { name: /content/i })).toBeVisible()
    await expect(summariesPage.page.getByRole("columnheader", { name: /key themes/i })).toBeVisible()
    await expect(summariesPage.page.getByRole("columnheader", { name: /model/i })).toBeVisible()
    await expect(summariesPage.page.getByRole("columnheader", { name: /time/i })).toBeVisible()
    await expect(summariesPage.page.getByRole("columnheader", { name: /created/i })).toBeVisible()

    // Verify theme badges appear in table
    await expect(summariesPage.page.getByText("Large Language Models")).toBeVisible()
    await expect(summariesPage.page.getByText("AI Safety")).toBeVisible()
  })

  test("search input filters summaries", async ({ summariesPage }) => {
    await summariesPage.navigate()

    await expect(summariesPage.searchInput).toBeVisible()

    // Type search text
    await summariesPage.searchFor("GPT")

    // Verify search input has value
    await expect(summariesPage.searchInput).toHaveValue("GPT")
  })

  test("model filter dropdown is available", async ({ summariesPage }) => {
    await summariesPage.navigate()

    // The model filter should be visible
    const modelFilter = summariesPage.page.getByRole("combobox").first()
    await expect(modelFilter).toBeVisible()

    // Click the model filter
    await modelFilter.click()

    // Should show All Models option
    await expect(summariesPage.page.getByRole("option", { name: /all models/i })).toBeVisible()
  })

  test("sort by column works via column header click", async ({ summariesPage }) => {
    await summariesPage.navigate()

    // Click the sortable Model header
    const modelHeader = summariesPage.page.getByRole("columnheader", { name: /model/i })
    await expect(modelHeader).toBeVisible()
    await modelHeader.click()

    // Click the sortable Time header
    const timeHeader = summariesPage.page.getByRole("columnheader", { name: /time/i })
    await expect(timeHeader).toBeVisible()
    await timeHeader.click()
  })

  test("shows empty state when no summaries exist", async ({ summariesPage, apiMocks }) => {
    await apiMocks.mockAllEmpty()

    await summariesPage.navigate()

    // Should show empty state message
    await expect(summariesPage.page.getByText(/no summaries generated yet/i)).toBeVisible()

    // Should have a Generate Summaries button in empty state
    await expect(
      summariesPage.page.getByRole("button", { name: /generate summaries/i }).first()
    ).toBeVisible()
  })

  test("stats cards display summary statistics", async ({ summariesPage }) => {
    await summariesPage.navigate()

    // From mockSummaryStats: total=25
    await expect(summariesPage.page.getByText("Total Summaries")).toBeVisible()
    await expect(summariesPage.page.getByText("25")).toBeVisible()

    // Should show model count card
    await expect(summariesPage.page.getByText("Models Used")).toBeVisible()
  })
})
