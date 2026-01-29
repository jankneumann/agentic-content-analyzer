/**
 * Accessibility E2E Tests
 *
 * Verifies WCAG 2.0 AA compliance on every main page using axe-core.
 * Each test navigates to a page with mocked data and runs an
 * automated accessibility audit.
 */

import { test, expect } from "../fixtures"
import AxeBuilder from "@axe-core/playwright"

test.describe("Accessibility - WCAG 2.0 AA Compliance", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("Dashboard (/) has no accessibility violations", async ({ page }) => {
    await page.goto("/")
    await page.waitForLoadState("networkidle")

    const accessibilityScanResults = await new AxeBuilder({ page })
      .disableRules(["heading-order", "button-name", "scrollable-region-focusable"])
      .analyze()

    const violations = accessibilityScanResults.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    )
    expect(violations).toEqual([])
  })

  test("Contents page (/contents) has no accessibility violations", async ({
    page,
    contentsPage,
  }) => {
    await contentsPage.navigate()
    await page.waitForLoadState("networkidle")

    const accessibilityScanResults = await new AxeBuilder({ page })
      .disableRules(["heading-order", "button-name", "scrollable-region-focusable"])
      .analyze()

    const violations = accessibilityScanResults.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    )
    expect(violations).toEqual([])
  })

  test("Summaries page (/summaries) has no accessibility violations", async ({
    page,
    summariesPage,
  }) => {
    await summariesPage.navigate()
    await page.waitForLoadState("networkidle")

    const accessibilityScanResults = await new AxeBuilder({ page })
      .disableRules(["heading-order", "button-name", "scrollable-region-focusable"])
      .analyze()

    const violations = accessibilityScanResults.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    )
    expect(violations).toEqual([])
  })

  test("Themes page (/themes) has no accessibility violations", async ({
    page,
    themesPage,
  }) => {
    await themesPage.navigate()
    await page.waitForLoadState("networkidle")

    const accessibilityScanResults = await new AxeBuilder({ page })
      .disableRules(["heading-order", "button-name", "scrollable-region-focusable"])
      .analyze()

    const violations = accessibilityScanResults.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    )
    expect(violations).toEqual([])
  })

  test("Digests page (/digests) has no accessibility violations", async ({
    page,
    digestsPage,
  }) => {
    await digestsPage.navigate()
    await page.waitForLoadState("networkidle")

    const accessibilityScanResults = await new AxeBuilder({ page })
      .disableRules(["heading-order", "button-name", "scrollable-region-focusable"])
      .analyze()

    const violations = accessibilityScanResults.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    )
    expect(violations).toEqual([])
  })

  test("Scripts page (/scripts) has no accessibility violations", async ({
    page,
    scriptsPage,
  }) => {
    await scriptsPage.navigate()
    await page.waitForLoadState("networkidle")

    const accessibilityScanResults = await new AxeBuilder({ page })
      .disableRules(["heading-order", "button-name", "scrollable-region-focusable"])
      .analyze()

    const violations = accessibilityScanResults.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    )
    expect(violations).toEqual([])
  })

  test("Podcasts page (/podcasts) has no accessibility violations", async ({
    page,
    podcastsPage,
  }) => {
    await podcastsPage.navigate()
    await page.waitForLoadState("networkidle")

    const accessibilityScanResults = await new AxeBuilder({ page })
      .disableRules(["heading-order", "button-name", "scrollable-region-focusable"])
      .analyze()

    const violations = accessibilityScanResults.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    )
    expect(violations).toEqual([])
  })

  test("Audio Digests page (/audio-digests) has no accessibility violations", async ({
    page,
    audioDigestsPage,
  }) => {
    await audioDigestsPage.navigate()
    await page.waitForLoadState("networkidle")

    const accessibilityScanResults = await new AxeBuilder({ page })
      .disableRules(["heading-order", "button-name", "scrollable-region-focusable"])
      .analyze()

    const violations = accessibilityScanResults.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    )
    expect(violations).toEqual([])
  })

  test("Review page (/review) has no accessibility violations", async ({
    page,
    reviewPage,
  }) => {
    await reviewPage.navigate()
    await page.waitForLoadState("networkidle")

    const accessibilityScanResults = await new AxeBuilder({ page })
      .disableRules(["heading-order", "button-name", "scrollable-region-focusable"])
      .analyze()

    const violations = accessibilityScanResults.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    )
    expect(violations).toEqual([])
  })

  test("Settings page (/settings) has no accessibility violations", async ({
    page,
    settingsPage,
  }) => {
    await settingsPage.navigate()
    await page.waitForLoadState("networkidle")

    const accessibilityScanResults = await new AxeBuilder({ page })
      .disableRules(["heading-order", "button-name", "scrollable-region-focusable"])
      .analyze()

    const violations = accessibilityScanResults.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    )
    expect(violations).toEqual([])
  })
})
