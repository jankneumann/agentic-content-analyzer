import { BasePage } from "../base.page"
import type { Page, Locator } from "@playwright/test"

export class SettingsPage extends BasePage {
  readonly settingsSections: Locator
  readonly pageTitle: Locator
  readonly sourcesTitle: Locator
  readonly addSourceButton: Locator

  constructor(page: Page) {
    super(page)
    this.settingsSections = page.locator("section, .rounded-lg.border")
    this.pageTitle = page.locator("h1, h2").first()
    this.sourcesTitle = page.getByRole("heading", { name: "Ingestion Sources" })
    this.addSourceButton = page.getByRole("button", { name: "Add source" })
  }

  async navigate(): Promise<void> {
    await this.goto("/settings")
  }

  async navigateSources(): Promise<void> {
    await this.goto("/settings/sources")
  }

  sourceToggle(name: string): Locator {
    return this.page.getByRole("switch", { name: "Toggle " + name })
  }

  removeOverrideButton(name: string): Locator {
    return this.page.getByRole("button", {
      name: "Remove database override for " + name,
    })
  }

  async selectSourceType(name: string): Promise<void> {
    await this.page.getByRole("combobox", { name: "Type" }).click()
    await this.page.getByRole("option", { name }).click()
  }
}
