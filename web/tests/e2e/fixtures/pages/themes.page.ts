import { BasePage } from "../base.page"
import type { Page, Locator } from "@playwright/test"

export class ThemesPage extends BasePage {
  readonly analyzeButton: Locator
  readonly statsCards: Locator
  readonly themeList: Locator
  readonly themeItems: Locator
  readonly emptyState: Locator

  constructor(page: Page) {
    super(page)
    this.analyzeButton = page.getByRole("button", { name: /analyze/i })
    this.statsCards = page.locator(".grid").first()
    this.themeList = page.locator("main")
    this.themeItems = page.locator('[data-testid="theme-item"], .border.rounded').filter({ hasText: /theme|trend|category/i })
    this.emptyState = page.getByText(/no theme|no analysis|run.*analysis/i)
  }

  async navigate(): Promise<void> {
    await this.goto("/themes")
  }

  async openAnalyzeDialog(): Promise<void> {
    await this.analyzeButton.click()
  }
}
