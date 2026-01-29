/**
 * Navigation E2E Tests
 *
 * Tests sidebar navigation links, active state highlighting,
 * breadcrumb updates, sidebar collapse/expand, and keyboard navigation.
 *
 * All tests mock the API to avoid real backend dependencies.
 */

import { test, expect } from "../../fixtures"

/** All sidebar navigation items with their expected routes and labels */
const NAV_ITEMS = [
  { key: "dashboard" as const, label: "Dashboard", route: "/" },
  { key: "content" as const, label: "Content", route: "/contents" },
  { key: "summaries" as const, label: "Summaries", route: "/summaries" },
  { key: "themes" as const, label: "Themes", route: "/themes" },
  { key: "digests" as const, label: "Digests", route: "/digests" },
  { key: "scripts" as const, label: "Scripts", route: "/scripts" },
  { key: "podcasts" as const, label: "Podcasts", route: "/podcasts" },
  { key: "audioDigests" as const, label: "Audio Digests", route: "/audio-digests" },
  { key: "reviewQueue" as const, label: "Review Queue", route: "/review" },
  { key: "settings" as const, label: "Settings", route: "/settings" },
]

test.describe("Sidebar Navigation", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("sidebar shows all navigation links on desktop", async ({
    basePage,
  }) => {
    test.skip(basePage.isMobile(), "Desktop-only test")

    await basePage.goto("/")

    for (const item of NAV_ITEMS) {
      await expect(basePage.navLinks[item.key]).toBeVisible()
    }
  })

  test("clicking each nav link navigates to the correct route", async ({
    basePage,
  }) => {
    test.skip(basePage.isMobile(), "Desktop-only test")

    await basePage.goto("/")

    // Navigate to each route and verify URL updates
    for (const item of NAV_ITEMS) {
      await basePage.navLinks[item.key].click()
      await basePage.page.waitForURL(`**${item.route}`)
      expect(basePage.page.url()).toContain(item.route)
    }
  })

  test("active nav item is highlighted with primary color", async ({
    basePage,
  }) => {
    test.skip(basePage.isMobile(), "Desktop-only test")

    await basePage.goto("/contents")

    // The active link should have the primary styling class
    const contentLink = basePage.navLinks.content
    await expect(contentLink).toHaveClass(/bg-primary/)

    // A non-active link should not have primary styling
    const settingsLink = basePage.navLinks.settings
    await expect(settingsLink).not.toHaveClass(/bg-primary/)
  })

  test("breadcrumb updates to show current page name", async ({
    basePage,
  }) => {
    test.skip(basePage.isMobile(), "Desktop-only test")

    // Dashboard shows heading instead of breadcrumb nav
    await basePage.goto("/")
    const dashboardText = await basePage.getBreadcrumbText()
    expect(dashboardText).toContain("Dashboard")

    // Non-root pages show breadcrumb nav with page name
    await basePage.goto("/contents")
    await expect(basePage.breadcrumb).toBeVisible()
    const breadcrumbText = await basePage.breadcrumb.textContent()
    expect(breadcrumbText).toContain("Content")

    // Navigate to another page and verify breadcrumb changes
    await basePage.navLinks.summaries.click()
    await basePage.page.waitForURL("**/summaries")
    const summariesBreadcrumb = await basePage.breadcrumb.textContent()
    expect(summariesBreadcrumb).toContain("Summaries")
  })

  test("breadcrumb includes Dashboard link for non-root pages", async ({
    basePage,
  }) => {
    test.skip(basePage.isMobile(), "Desktop-only test")

    await basePage.goto("/digests")

    // Breadcrumb should have both Dashboard and current page
    await expect(basePage.breadcrumb).toBeVisible()
    const text = await basePage.breadcrumb.textContent()
    expect(text).toContain("Dashboard")
    expect(text).toContain("Digests")
  })
})

test.describe("Sidebar Collapse and Expand", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("sidebar can be collapsed and expanded", async ({ basePage }) => {
    test.skip(basePage.isMobile(), "Desktop-only test")

    await basePage.goto("/")

    // Sidebar starts expanded (w-64 class) with visible text labels
    await expect(basePage.sidebar.first()).toBeVisible()
    await expect(basePage.collapseButton).toBeVisible()

    // Collapse the sidebar
    await basePage.collapseButton.click()

    // After collapsing, expand button should be visible
    await expect(basePage.expandButton).toBeVisible()

    // Expand the sidebar again
    await basePage.expandButton.click()

    // Collapse button should be visible again
    await expect(basePage.collapseButton).toBeVisible()
  })

  test("collapsed state persists to localStorage", async ({ basePage }) => {
    test.skip(basePage.isMobile(), "Desktop-only test")

    await basePage.goto("/")

    // Initially not collapsed
    const initialState = await basePage.page.evaluate(() =>
      localStorage.getItem("sidebar-collapsed")
    )
    expect(initialState).not.toBe("true")

    // Collapse the sidebar
    await basePage.collapseButton.click()

    // Verify localStorage was updated
    const collapsedState = await basePage.page.evaluate(() =>
      localStorage.getItem("sidebar-collapsed")
    )
    expect(collapsedState).toBe("true")

    // Reload the page
    await basePage.page.reload()
    await basePage.page.waitForLoadState("domcontentloaded")

    // Sidebar should remain collapsed after reload
    await expect(basePage.expandButton).toBeVisible()
  })

  test("collapsed sidebar shows expand button with tooltip", async ({
    basePage,
  }) => {
    test.skip(basePage.isMobile(), "Desktop-only test")

    await basePage.goto("/")

    // Collapse the sidebar
    await basePage.collapseButton.click()

    // Expand button should be accessible
    await expect(basePage.expandButton).toBeVisible()
    await expect(basePage.expandButton).toHaveAttribute(
      "aria-label",
      "Expand sidebar"
    )
  })
})

test.describe("Keyboard Navigation", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("Tab key moves focus through navigation links", async ({
    basePage,
  }) => {
    test.skip(basePage.isMobile(), "Desktop-only test")

    await basePage.goto("/")

    // Focus the first nav link
    await basePage.navLinks.dashboard.focus()
    await expect(basePage.navLinks.dashboard).toBeFocused()

    // Tab through subsequent links
    await basePage.page.keyboard.press("Tab")
    await expect(basePage.navLinks.content).toBeFocused()

    await basePage.page.keyboard.press("Tab")
    await expect(basePage.navLinks.summaries).toBeFocused()
  })

  test("Enter key activates focused navigation link", async ({
    basePage,
  }) => {
    test.skip(basePage.isMobile(), "Desktop-only test")

    await basePage.goto("/")

    // Focus and activate the Content link
    await basePage.navLinks.content.focus()
    await basePage.page.keyboard.press("Enter")

    await basePage.page.waitForURL("**/contents")
    expect(basePage.page.url()).toContain("/contents")
  })
})
