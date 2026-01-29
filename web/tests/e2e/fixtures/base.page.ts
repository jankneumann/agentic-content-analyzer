/**
 * Base Page Object
 *
 * Shared locators and actions for the application layout.
 * All page objects extend this to access sidebar, header,
 * breadcrumbs, and theme toggle.
 */

import type { Page, Locator } from "@playwright/test"

export class BasePage {
  // Layout containers
  readonly sidebar: Locator
  readonly header: Locator
  readonly main: Locator

  // Header elements
  readonly breadcrumb: Locator
  readonly mobileMenuButton: Locator
  readonly themeToggleButton: Locator
  readonly notificationsButton: Locator

  // Sidebar elements
  readonly sidebarBrand: Locator
  readonly collapseButton: Locator
  readonly expandButton: Locator

  // Mobile overlay
  readonly mobileBackdrop: Locator
  readonly mobileSidebar: Locator

  // Navigation links (by title)
  readonly navLinks: {
    dashboard: Locator
    content: Locator
    summaries: Locator
    themes: Locator
    digests: Locator
    scripts: Locator
    podcasts: Locator
    audioDigests: Locator
    reviewQueue: Locator
    settings: Locator
  }

  constructor(public page: Page) {
    // Layout
    this.sidebar = page.locator("aside")
    this.header = page.locator("header")
    this.main = page.locator("main")

    // Header
    this.breadcrumb = page.locator('nav[aria-label="Breadcrumb"]')
    this.mobileMenuButton = page.getByRole("button", { name: "Open menu" })
    this.themeToggleButton = page.getByRole("button", { name: "Toggle theme" })
    this.notificationsButton = page.getByRole("button", {
      name: "Notifications",
    })

    // Sidebar
    this.sidebarBrand = page.locator("aside").getByText("NA").first()
    this.collapseButton = page.getByRole("button", {
      name: "Collapse sidebar",
    })
    this.expandButton = page.getByRole("button", { name: "Expand sidebar" })

    // Mobile overlay
    this.mobileBackdrop = page.locator(".fixed.inset-0.bg-black\\/50")
    this.mobileSidebar = page.locator(".fixed.inset-y-0.left-0 aside")

    // Navigation links (scoped to sidebar to avoid matching dashboard quick-action links)
    const sidebar = page.locator("aside")
    this.navLinks = {
      dashboard: sidebar.getByRole("link", { name: "Dashboard", exact: true }),
      content: sidebar.getByRole("link", { name: "Content", exact: true }),
      summaries: sidebar.getByRole("link", { name: "Summaries", exact: true }),
      themes: sidebar.getByRole("link", { name: "Themes", exact: true }),
      digests: sidebar.getByRole("link", { name: "Digests", exact: true }),
      scripts: sidebar.getByRole("link", { name: "Scripts", exact: true }),
      podcasts: sidebar.getByRole("link", { name: "Podcasts", exact: true }),
      audioDigests: sidebar.getByRole("link", { name: "Audio Digests", exact: true }),
      reviewQueue: sidebar.getByRole("link", { name: "Review Queue", exact: true }),
      settings: sidebar.getByRole("link", { name: "Settings", exact: true }),
    }
  }

  /** Navigate to a URL and wait for load */
  async goto(path: string): Promise<void> {
    await this.page.goto(path)
    await this.page.waitForLoadState("domcontentloaded")
  }

  /** Check if running on a mobile viewport */
  isMobile(): boolean {
    const viewport = this.page.viewportSize()
    return !!viewport && viewport.width < 768
  }

  /** Get the current page heading text */
  async getPageHeading(): Promise<string> {
    const heading = this.page.locator("h1").first()
    return heading.textContent() ?? ""
  }

  /** Get visible breadcrumb text */
  async getBreadcrumbText(): Promise<string> {
    const breadcrumb = this.breadcrumb
    if ((await breadcrumb.count()) === 0) {
      // On dashboard, heading is shown instead of breadcrumb
      return this.getPageHeading()
    }
    return (await breadcrumb.textContent()) ?? ""
  }

  /** Toggle the theme (dark/light) */
  async toggleTheme(): Promise<void> {
    await this.themeToggleButton.click()
  }

  /** Check if dark mode is active */
  async isDarkMode(): Promise<boolean> {
    return this.page.evaluate(() =>
      document.documentElement.classList.contains("dark")
    )
  }

  /** Open mobile menu */
  async openMobileMenu(): Promise<void> {
    await this.mobileMenuButton.click()
  }

  /** Close mobile menu via backdrop click */
  async closeMobileMenuViaBackdrop(): Promise<void> {
    await this.mobileBackdrop.click()
  }

  /** Close mobile menu via Escape key */
  async closeMobileMenuViaEscape(): Promise<void> {
    await this.page.keyboard.press("Escape")
  }

  /** Wait for a dialog to be visible */
  async waitForDialog(): Promise<Locator> {
    const dialog = this.page.getByRole("dialog")
    await dialog.waitFor({ state: "visible" })
    return dialog
  }

  /** Close a dialog via the X button */
  async closeDialog(): Promise<void> {
    const dialog = this.page.getByRole("dialog")
    await dialog.getByRole("button", { name: "Close" }).first().click()
  }

  /** Close dialog via Escape */
  async closeDialogViaEscape(): Promise<void> {
    await this.page.keyboard.press("Escape")
  }

  /** Get the dialog element */
  get dialog(): Locator {
    return this.page.getByRole("dialog")
  }
}
