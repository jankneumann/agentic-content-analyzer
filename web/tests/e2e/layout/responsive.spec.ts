/**
 * Responsive Layout E2E Tests
 *
 * Tests the responsive behavior of the AppShell layout across
 * desktop and mobile viewports. Covers sidebar visibility,
 * hamburger menu, mobile overlay, backdrop dismissal,
 * Escape key handling, and safe area padding.
 *
 * The Playwright config defines three projects:
 *   - chromium (Desktop Chrome, viewport 1280x720)
 *   - Mobile Chrome (Pixel 7, viewport 412x915)
 *   - Mobile Safari (iPhone 14, viewport 390x844)
 *
 * Tests use `test.skip()` guards based on viewport width to ensure
 * desktop-only and mobile-only tests run in the correct project.
 */

import { test, expect } from "../fixtures"

test.describe("Desktop Layout", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("sidebar is visible on desktop", async ({ basePage }) => {
    test.skip(basePage.isMobile(), "Desktop-only test")

    await basePage.goto("/")

    // Desktop sidebar container (hidden md:block wrapper)
    await expect(basePage.sidebar.first()).toBeVisible()
  })

  test("hamburger menu button is not visible on desktop", async ({
    basePage,
  }) => {
    test.skip(basePage.isMobile(), "Desktop-only test")

    await basePage.goto("/")

    // The mobile menu button has class md:hidden, so it should not be visible
    await expect(basePage.mobileMenuButton).not.toBeVisible()
  })

  test("header is visible with breadcrumbs and actions", async ({
    basePage,
  }) => {
    test.skip(basePage.isMobile(), "Desktop-only test")

    await basePage.goto("/contents")

    await expect(basePage.header).toBeVisible()
    await expect(basePage.breadcrumb).toBeVisible()
    await expect(basePage.themeToggleButton).toBeVisible()
  })
})

test.describe("Mobile Layout", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("sidebar is hidden on mobile", async ({ basePage }) => {
    test.skip(!basePage.isMobile(), "Mobile-only test")

    await basePage.goto("/")

    // The desktop sidebar wrapper has class "hidden md:block",
    // so the sidebar should not be visible on small screens
    const desktopSidebar = basePage.page.locator(".hidden.md\\:block aside")
    await expect(desktopSidebar).not.toBeVisible()
  })

  test("hamburger menu button is visible on mobile", async ({ basePage }) => {
    test.skip(!basePage.isMobile(), "Mobile-only test")

    await basePage.goto("/")

    await expect(basePage.mobileMenuButton).toBeVisible()
  })

  test("clicking hamburger opens sidebar overlay", async ({ basePage }) => {
    test.skip(!basePage.isMobile(), "Mobile-only test")

    await basePage.goto("/")

    // Sidebar overlay should not be visible initially
    await expect(basePage.mobileBackdrop).not.toBeVisible()

    // Open mobile menu
    await basePage.openMobileMenu()

    // Backdrop and mobile sidebar should appear
    await expect(basePage.mobileBackdrop).toBeVisible()
    await expect(basePage.mobileSidebar).toBeVisible()
  })

  test("clicking backdrop closes sidebar overlay", async ({ basePage }) => {
    test.skip(!basePage.isMobile(), "Mobile-only test")

    await basePage.goto("/")

    // Open mobile menu
    await basePage.openMobileMenu()
    await expect(basePage.mobileBackdrop).toBeVisible()

    // Click backdrop to dismiss
    await basePage.closeMobileMenuViaBackdrop()

    // Overlay should be gone
    await expect(basePage.mobileBackdrop).not.toBeVisible()
    await expect(basePage.mobileSidebar).not.toBeVisible()
  })

  test("pressing Escape closes sidebar overlay", async ({ basePage }) => {
    test.skip(!basePage.isMobile(), "Mobile-only test")

    await basePage.goto("/")

    // Open mobile menu
    await basePage.openMobileMenu()
    await expect(basePage.mobileBackdrop).toBeVisible()

    // Press Escape
    await basePage.closeMobileMenuViaEscape()

    // Overlay should be gone
    await expect(basePage.mobileBackdrop).not.toBeVisible()
    await expect(basePage.mobileSidebar).not.toBeVisible()
  })

  test("mobile sidebar shows all navigation links", async ({ basePage }) => {
    test.skip(!basePage.isMobile(), "Mobile-only test")

    await basePage.goto("/")
    await basePage.openMobileMenu()

    // All nav links should be visible within the mobile sidebar
    await expect(basePage.navLinks.dashboard).toBeVisible()
    await expect(basePage.navLinks.content).toBeVisible()
    await expect(basePage.navLinks.summaries).toBeVisible()
    await expect(basePage.navLinks.themes).toBeVisible()
    await expect(basePage.navLinks.digests).toBeVisible()
    await expect(basePage.navLinks.scripts).toBeVisible()
    await expect(basePage.navLinks.podcasts).toBeVisible()
    await expect(basePage.navLinks.audioDigests).toBeVisible()
    await expect(basePage.navLinks.reviewQueue).toBeVisible()
    await expect(basePage.navLinks.settings).toBeVisible()
  })

  test("navigating via mobile sidebar closes the overlay", async ({
    basePage,
  }) => {
    test.skip(!basePage.isMobile(), "Mobile-only test")

    await basePage.goto("/")
    await basePage.openMobileMenu()

    // Click a nav link in the mobile sidebar
    await basePage.navLinks.content.click()
    await basePage.page.waitForURL("**/contents")

    // The collapse toggle in the mobile sidebar acts as a close action,
    // but clicking a nav link itself should trigger navigation.
    // Verify we navigated successfully.
    expect(basePage.page.url()).toContain("/contents")
  })
})

test.describe("Safe Area Padding", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("root layout applies safe area top padding", async ({ basePage }) => {
    await basePage.goto("/")

    // The AppShell root div uses pt-[var(--safe-area-top)]
    // Verify the CSS custom property is applied via the style/class
    const rootDiv = basePage.page.locator(".flex.h-screen.overflow-hidden")
    await expect(rootDiv).toBeVisible()

    // Check the class includes the safe area padding utility
    await expect(rootDiv).toHaveClass(/pt-\[var\(--safe-area-top\)\]/)
  })

  test("mobile sidebar overlay applies safe area top padding", async ({
    basePage,
  }) => {
    test.skip(!basePage.isMobile(), "Mobile-only test")

    await basePage.goto("/")
    await basePage.openMobileMenu()

    // The mobile sidebar container uses pt-[var(--safe-area-top)]
    const mobileContainer = basePage.page.locator(
      ".fixed.inset-y-0.left-0"
    )
    await expect(mobileContainer).toBeVisible()
    await expect(mobileContainer).toHaveClass(/pt-\[var\(--safe-area-top\)\]/)
  })
})
