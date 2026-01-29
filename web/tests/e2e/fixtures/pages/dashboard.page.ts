import { BasePage } from "../base.page"
import type { Page, Locator } from "@playwright/test"

export class DashboardPage extends BasePage {
  readonly pipelineCards: Locator
  readonly quickActions: Locator
  readonly statsSection: Locator

  constructor(page: Page) {
    super(page)
    this.pipelineCards = page.locator('[data-testid="pipeline-card"], .rounded-lg.border').filter({ hasText: /content|summar|theme|digest|script|podcast/i })
    this.quickActions = page.getByRole("link").filter({ hasText: /view|go to|manage/i })
    this.statsSection = page.locator("main")
  }

  async navigate(): Promise<void> {
    await this.goto("/")
  }

  async getPipelineCardCount(): Promise<number> {
    return this.pipelineCards.count()
  }
}
