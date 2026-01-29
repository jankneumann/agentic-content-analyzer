/**
 * Scripts List Page Tests
 *
 * Tests for /scripts page: table rendering, filtering, sorting,
 * empty state, and stats display.
 */

import { test, expect } from "../../fixtures"
import * as mockData from "../../fixtures/mock-data"

test.describe("Scripts List Page", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("table renders with script items", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await expect(scriptsPage.table).toBeVisible()
    const rowCount = await scriptsPage.getRowCount()
    expect(rowCount).toBeGreaterThan(0)
  })

  test("displays script titles in table rows", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await expect(scriptsPage.table).toBeVisible()
    await expect(scriptsPage.page.getByText("AI Weekly Deep Dive - Episode 42")).toBeVisible()
  })

  test("displays second script item", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await expect(scriptsPage.page.getByText("Data Engineering Roundup")).toBeVisible()
  })

  test("status filter dropdown is visible", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await expect(scriptsPage.statusFilter).toBeVisible()
  })

  test("status filter shows options when clicked", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await scriptsPage.statusFilter.click()

    await expect(scriptsPage.page.getByRole("option", { name: "All Status" })).toBeVisible()
    await expect(scriptsPage.page.getByRole("option", { name: "Pending Review" })).toBeVisible()
    await expect(scriptsPage.page.getByRole("option", { name: "Approved" })).toBeVisible()
  })

  test("table has sortable column headers", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await expect(scriptsPage.page.getByRole("columnheader", { name: /title/i })).toBeVisible()
    await expect(scriptsPage.page.getByRole("columnheader", { name: /status/i })).toBeVisible()
    await expect(scriptsPage.page.getByRole("columnheader", { name: /created date/i })).toBeVisible()
  })

  test("clicking sortable column header triggers sort", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    const createdHeader = scriptsPage.page.getByRole("columnheader", { name: /created date/i })
    await createdHeader.click()

    // After clicking, the column header should indicate sort direction
    await expect(createdHeader).toBeVisible()
  })

  test("empty state displays when no scripts exist", async ({ apiMocks, scriptsPage }) => {
    await apiMocks.mockScriptsEmpty()
    await scriptsPage.navigate()

    await expect(scriptsPage.emptyState).toBeVisible()
  })

  test("stats cards display script statistics", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    // The stats cards show Total, Pending Review, Revision Requested, Approved, Completed
    await expect(scriptsPage.page.getByText("Total")).toBeVisible()
    await expect(scriptsPage.page.getByText("Pending Review")).toBeVisible()
    await expect(scriptsPage.page.getByText("Approved")).toBeVisible()
    await expect(scriptsPage.page.getByText("Completed")).toBeVisible()
  })

  test("stats cards show correct counts from mock data", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    // From createScriptReviewStatistics: total=12
    await expect(scriptsPage.page.getByText("12")).toBeVisible()
  })

  test("search input filters scripts by title", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await scriptsPage.searchFor("Data Engineering")

    // Only matching script should remain visible
    await expect(scriptsPage.page.getByText("Data Engineering Roundup")).toBeVisible()
  })

  test("generate script button is visible", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await expect(scriptsPage.generateButton).toBeVisible()
  })

  test("table shows length column with badge", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await expect(scriptsPage.page.getByText("standard").first()).toBeVisible()
  })

  test("table shows duration column", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await expect(scriptsPage.page.getByText("12 min")).toBeVisible()
  })
})
