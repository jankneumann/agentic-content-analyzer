import { BasePage } from "../base.page"
import type { Page, Locator } from "@playwright/test"

export class SettingsPage extends BasePage {
  readonly settingsSections: Locator
  readonly pageTitle: Locator

  constructor(page: Page) {
    super(page)
    this.settingsSections = page.locator("section, .rounded-lg.border")
    this.pageTitle = page.locator("h1, h2").first()
  }

  async navigate(): Promise<void> {
    await this.goto("/settings")
  }
}
