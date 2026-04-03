/**
 * Themes Views Tests
 *
 * Tests for /themes page view toggles: Cards, Table View, Graph View,
 * graph sub-tabs (Network/Timeline), and active state styling.
 */

import { test, expect } from "../fixtures"

test.describe("Themes Page Views", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockAnalyzeThemes()
  })

  test("displays theme cards by default when analysis exists", async ({
    themesPage,
  }) => {
    await themesPage.navigate()

    // Cards view is the default — theme names from createThemeAnalysisResult should be visible
    await expect(
      themesPage.page.getByText("Large Language Models").first()
    ).toBeVisible()
    await expect(
      themesPage.page.getByText("MLOps Best Practices")
    ).toBeVisible()
    await expect(
      themesPage.page.getByText("AI Safety Regulation")
    ).toBeVisible()
  })

  test("switches to table view and shows sortable table", async ({
    themesPage,
  }) => {
    await themesPage.navigate()

    // Click "Table View" button
    await themesPage.page
      .getByRole("button", { name: /table view/i })
      .click()

    // Verify sortable column headers appear (from ThemeTableView)
    await expect(
      themesPage.page.getByRole("columnheader", { name: /name/i })
    ).toBeVisible()
    await expect(
      themesPage.page.getByRole("columnheader", { name: /category/i })
    ).toBeVisible()
    await expect(
      themesPage.page.getByRole("columnheader", { name: /trend/i })
    ).toBeVisible()
    await expect(
      themesPage.page.getByRole("columnheader", { name: /relevance/i })
    ).toBeVisible()

    // Verify both theme names are in the table
    await expect(
      themesPage.page.getByText("Large Language Models").first()
    ).toBeVisible()
    await expect(
      themesPage.page.getByText("MLOps Best Practices")
    ).toBeVisible()
    await expect(
      themesPage.page.getByText("AI Safety Regulation")
    ).toBeVisible()
  })

  test("switches to graph view and shows network tab", async ({
    themesPage,
  }) => {
    await themesPage.navigate()

    // Click "Graph View" button
    await themesPage.page
      .getByRole("button", { name: /graph view/i })
      .click()

    // Verify "Network" and "Timeline" tab buttons appear (from ThemeGraphView)
    await expect(
      themesPage.page.getByRole("button", { name: "Network" })
    ).toBeVisible()
    await expect(
      themesPage.page.getByRole("button", { name: "Timeline" })
    ).toBeVisible()
  })

  test("switches between graph tabs", async ({ themesPage }) => {
    await themesPage.navigate()

    // Enter graph view
    await themesPage.page
      .getByRole("button", { name: /graph view/i })
      .click()

    // Network tab should be active by default (has bg-background class)
    const networkButton = themesPage.page.getByRole("button", {
      name: "Network",
    })
    const timelineButton = themesPage.page.getByRole("button", {
      name: "Timeline",
    })

    // Network should have the active styling (bg-background)
    await expect(networkButton).toHaveClass(/bg-background/)

    // Click Timeline tab
    await timelineButton.click()

    // Timeline should now have the active styling
    await expect(timelineButton).toHaveClass(/bg-background/)
  })

  test("view toggle buttons show active state", async ({ themesPage }) => {
    await themesPage.navigate()

    const cardsButton = themesPage.page.getByRole("button", { name: "Cards" })
    const tableButton = themesPage.page.getByRole("button", {
      name: "Table View",
    })
    const graphButton = themesPage.page.getByRole("button", {
      name: "Graph View",
    })

    // Cards is the default active view — variant="default" renders differently from variant="outline"
    // The active button does NOT have the "border" class (outline variant has it)
    // Check that Cards button is NOT outline (active) and Table View IS outline (inactive)
    await expect(cardsButton).not.toHaveClass(/border-input/)
    await expect(tableButton).toHaveClass(/border/)

    // Click "Table View" — it should become active, Cards should become inactive
    await tableButton.click()

    // Now Table View should be active (not outline) and Cards should be inactive (outline)
    await expect(tableButton).not.toHaveClass(/border-input/)
    await expect(cardsButton).toHaveClass(/border/)
  })
})
