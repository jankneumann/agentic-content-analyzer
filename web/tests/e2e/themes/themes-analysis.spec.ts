/**
 * Themes Analysis Page Tests
 *
 * Tests for /themes page: stats cards, theme list, analyze dialog,
 * date range tabs, configuration options, and empty state.
 */

import { test, expect } from "../fixtures"

test.describe("Themes Analysis Page", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockAnalyzeThemes()
  })

  test("stats cards show total themes count", async ({ themesPage }) => {
    await themesPage.navigate()

    await expect(themesPage.page.getByText("Total Themes")).toBeVisible()
    // From createThemeAnalysisResult: total_themes = 3
    await expect(themesPage.page.getByText("3").first()).toBeVisible()
  })

  test("stats cards show emerging themes count", async ({ themesPage }) => {
    await themesPage.navigate()

    await expect(themesPage.page.getByText("Emerging").first()).toBeVisible()
    // From createThemeAnalysisResult: emerging_themes_count = 1
    await expect(themesPage.page.getByText("1").first()).toBeVisible()
  })

  test("stats cards show content items analyzed count", async ({ themesPage }) => {
    await themesPage.navigate()

    await expect(themesPage.page.getByText("Content Items Analyzed")).toBeVisible()
    // From createThemeAnalysisResult: content_count = 25
    await expect(themesPage.page.getByText("25")).toBeVisible()
  })

  test("stats cards show top theme", async ({ themesPage }) => {
    await themesPage.navigate()

    await expect(themesPage.page.getByText("Top Theme")).toBeVisible()
    // From createThemeAnalysisResult: top_theme = "Large Language Models"
    await expect(themesPage.page.getByText("Large Language Models").first()).toBeVisible()
  })

  test("theme list renders with theme items", async ({ themesPage }) => {
    await themesPage.navigate()

    // Themes from createThemeAnalysisResult: LLMs, MLOps, AI Safety
    await expect(themesPage.page.getByText("Large Language Models").first()).toBeVisible()
    await expect(themesPage.page.getByText("MLOps Best Practices")).toBeVisible()
    await expect(themesPage.page.getByText("AI Safety Regulation")).toBeVisible()
  })

  test("each theme shows name", async ({ themesPage }) => {
    await themesPage.navigate()

    await expect(themesPage.page.getByText("Large Language Models").first()).toBeVisible()
  })

  test("each theme shows category badge", async ({ themesPage }) => {
    await themesPage.navigate()

    // From createThemeData: category = "ml_ai" -> "ml ai"
    await expect(themesPage.page.getByText("ml ai").first()).toBeVisible()
  })

  test("each theme shows trend badge", async ({ themesPage }) => {
    await themesPage.navigate()

    // From createThemeAnalysisResult: themes have trends "growing", "established", "emerging"
    await expect(themesPage.page.getByText("growing").first()).toBeVisible()
    await expect(themesPage.page.getByText("emerging").first()).toBeVisible()
  })

  test("each theme shows relevance score", async ({ themesPage }) => {
    await themesPage.navigate()

    // From createThemeData: relevance_score = 0.92 -> "92%"
    await expect(themesPage.page.getByText("92%").first()).toBeVisible()
  })

  test("analyze button is visible", async ({ themesPage }) => {
    await themesPage.navigate()

    await expect(themesPage.analyzeButton).toBeVisible()
  })

  test("analyze button opens dialog", async ({ themesPage }) => {
    await themesPage.navigate()

    await themesPage.openAnalyzeDialog()

    const dialog = await themesPage.page.getByRole("dialog")
    await expect(dialog).toBeVisible()
  })

  test("analyze dialog has Analysis Period title", async ({ themesPage }) => {
    await themesPage.navigate()

    await themesPage.openAnalyzeDialog()

    const dialog = themesPage.page.getByRole("dialog")
    await expect(dialog.getByText("Analysis Period")).toBeVisible()
  })

  test("analyze dialog has date range tabs", async ({ themesPage }) => {
    await themesPage.navigate()

    await themesPage.openAnalyzeDialog()

    const dialog = themesPage.page.getByRole("dialog")
    await expect(dialog.getByRole("tab", { name: "Last Week" })).toBeVisible()
    await expect(dialog.getByRole("tab", { name: "Last Month" })).toBeVisible()
    await expect(dialog.getByRole("tab", { name: "Custom" })).toBeVisible()
  })

  test("Last Week tab is selected by default", async ({ themesPage }) => {
    await themesPage.navigate()

    await themesPage.openAnalyzeDialog()

    const dialog = themesPage.page.getByRole("dialog")
    const weekTab = dialog.getByRole("tab", { name: "Last Week" })
    await expect(weekTab).toHaveAttribute("data-state", "active")
  })

  test("clicking Last Month tab switches selection", async ({ themesPage }) => {
    await themesPage.navigate()

    await themesPage.openAnalyzeDialog()

    const dialog = themesPage.page.getByRole("dialog")
    await dialog.getByRole("tab", { name: "Last Month" }).click()

    const monthTab = dialog.getByRole("tab", { name: "Last Month" })
    await expect(monthTab).toHaveAttribute("data-state", "active")
  })

  test("clicking Custom tab shows date inputs", async ({ themesPage }) => {
    await themesPage.navigate()

    await themesPage.openAnalyzeDialog()

    const dialog = themesPage.page.getByRole("dialog")
    await dialog.getByRole("tab", { name: "Custom" }).click()

    await expect(dialog.locator('input[type="date"]').first()).toBeVisible()
  })

  test("dialog has max themes configuration", async ({ themesPage }) => {
    await themesPage.navigate()

    await themesPage.openAnalyzeDialog()

    const dialog = themesPage.page.getByRole("dialog")
    await expect(dialog.getByText(/max.*themes/i)).toBeVisible()
  })

  test("dialog has Analyze Themes submit button", async ({ themesPage }) => {
    await themesPage.navigate()

    await themesPage.openAnalyzeDialog()

    const dialog = themesPage.page.getByRole("dialog")
    // The dialog has a submit button labeled "Analyze Themes"
    await expect(
      dialog.getByRole("button", { name: /analyze themes/i })
    ).toBeVisible()
  })

  test("empty state when no analysis exists", async ({ apiMocks, themesPage }) => {
    await apiMocks.mockThemesEmpty()
    await themesPage.navigate()

    await expect(themesPage.page.getByText(/no theme analysis/i)).toBeVisible()
  })

  test("empty state shows analyze button", async ({ apiMocks, themesPage }) => {
    await apiMocks.mockThemesEmpty()
    await themesPage.navigate()

    // The empty state includes an "Analyze Themes" button
    await expect(
      themesPage.page.getByRole("button", { name: /analyze themes/i }).first()
    ).toBeVisible()
  })
})
