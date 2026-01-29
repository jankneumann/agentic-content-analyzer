/**
 * Theme Toggle E2E Tests
 *
 * Tests the dark/light theme toggle functionality including:
 * - Adding and removing the `.dark` class on document.documentElement
 * - Persisting theme preference to localStorage
 * - Displaying the correct icon for the current mode
 *
 * The ThemeToggle component in Header.tsx:
 * - Shows Moon icon in light mode (click to go dark)
 * - Shows Sun icon in dark mode (click to go light)
 * - Reads initial state from localStorage key "theme"
 * - Falls back to system preference via prefers-color-scheme
 */

import { test, expect } from "../fixtures"

test.describe("Theme Toggle", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("clicking toggle adds .dark class to documentElement", async ({
    basePage,
  }) => {
    // Clear any stored theme preference to start in light mode
    await basePage.page.addInitScript(() => {
      localStorage.removeItem("theme")
    })

    await basePage.goto("/")

    // Verify we start without .dark class
    const initiallyDark = await basePage.isDarkMode()
    expect(initiallyDark).toBe(false)

    // Click the theme toggle
    await basePage.toggleTheme()

    // Document should now have .dark class
    const isDarkAfterToggle = await basePage.isDarkMode()
    expect(isDarkAfterToggle).toBe(true)
  })

  test("clicking toggle again removes .dark class", async ({ basePage }) => {
    // Start in light mode
    await basePage.page.addInitScript(() => {
      localStorage.removeItem("theme")
    })

    await basePage.goto("/")

    // Toggle to dark
    await basePage.toggleTheme()
    expect(await basePage.isDarkMode()).toBe(true)

    // Toggle back to light
    await basePage.toggleTheme()
    expect(await basePage.isDarkMode()).toBe(false)
  })

  test("theme preference persists to localStorage", async ({ basePage }) => {
    // Start clean
    await basePage.page.addInitScript(() => {
      localStorage.removeItem("theme")
    })

    await basePage.goto("/")

    // Toggle to dark
    await basePage.toggleTheme()

    // Check localStorage value
    const storedTheme = await basePage.page.evaluate(() =>
      localStorage.getItem("theme")
    )
    expect(storedTheme).toBe("dark")

    // Toggle back to light
    await basePage.toggleTheme()

    const storedThemeLight = await basePage.page.evaluate(() =>
      localStorage.getItem("theme")
    )
    expect(storedThemeLight).toBe("light")
  })

  test("theme persists across page reload", async ({ basePage }) => {
    // Clear theme before navigating (use evaluate, not addInitScript,
    // because addInitScript runs on EVERY page load including reload,
    // which would clear the theme we want to persist)
    await basePage.goto("/")
    await basePage.page.evaluate(() => localStorage.removeItem("theme"))
    await basePage.page.reload()
    await basePage.page.waitForLoadState("domcontentloaded")

    // Toggle to dark
    await basePage.toggleTheme()
    expect(await basePage.isDarkMode()).toBe(true)

    // Reload the page
    await basePage.page.reload()
    await basePage.page.waitForLoadState("domcontentloaded")

    // Dark mode should be preserved (read from localStorage on init)
    expect(await basePage.isDarkMode()).toBe(true)
  })

  test("Moon icon is shown in light mode", async ({ basePage }) => {
    // Force light mode
    await basePage.page.addInitScript(() => {
      localStorage.setItem("theme", "light")
    })

    await basePage.goto("/")

    // The toggle button should contain the Moon icon (Lucide Moon SVG)
    // In light mode, Moon icon is rendered to indicate "click to switch to dark"
    const moonIcon = basePage.themeToggleButton.locator(
      'svg.lucide-moon'
    )
    await expect(moonIcon).toBeVisible()
  })

  test("Sun icon is shown in dark mode", async ({ basePage }) => {
    // Force dark mode
    await basePage.page.addInitScript(() => {
      localStorage.setItem("theme", "dark")
      document.documentElement.classList.add("dark")
    })

    await basePage.goto("/")

    // The toggle button should contain the Sun icon (Lucide Sun SVG)
    // In dark mode, Sun icon is rendered to indicate "click to switch to light"
    const sunIcon = basePage.themeToggleButton.locator(
      'svg.lucide-sun'
    )
    await expect(sunIcon).toBeVisible()
  })

  test("toggling theme switches the displayed icon", async ({ basePage }) => {
    // Start in light mode
    await basePage.page.addInitScript(() => {
      localStorage.removeItem("theme")
    })

    await basePage.goto("/")

    // Light mode shows Moon icon
    const moonIcon = basePage.themeToggleButton.locator(
      'svg.lucide-moon'
    )
    const sunIcon = basePage.themeToggleButton.locator(
      'svg.lucide-sun'
    )

    await expect(moonIcon).toBeVisible()
    await expect(sunIcon).not.toBeVisible()

    // Toggle to dark
    await basePage.toggleTheme()

    // Dark mode shows Sun icon
    await expect(sunIcon).toBeVisible()
    await expect(moonIcon).not.toBeVisible()

    // Toggle back to light
    await basePage.toggleTheme()

    // Light mode shows Moon icon again
    await expect(moonIcon).toBeVisible()
    await expect(sunIcon).not.toBeVisible()
  })
})
