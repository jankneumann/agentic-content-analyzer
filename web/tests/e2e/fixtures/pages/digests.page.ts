import { BasePage } from "../base.page"
import type { Page, Locator } from "@playwright/test"

export class DigestsPage extends BasePage {
  readonly searchInput: Locator
  readonly typeFilter: Locator
  readonly statusFilter: Locator
  readonly table: Locator
  readonly tableRows: Locator
  readonly generateButton: Locator
  readonly emptyState: Locator
  readonly statsCards: Locator

  constructor(page: Page) {
    super(page)
    this.searchInput = page.getByPlaceholder(/search/i)
    this.typeFilter = page.getByRole("combobox").filter({ hasText: /type|all types/i }).first()
    this.statusFilter = page.getByRole("combobox").filter({ hasText: /status|all status/i }).first()
    this.table = page.getByRole("table")
    this.tableRows = page.locator("tbody tr")
    this.generateButton = page.getByRole("button", { name: /generate/i })
    this.emptyState = page.getByText(/no digest|no items|no results/i)
    this.statsCards = page.locator(".grid").first()
  }

  async navigate(): Promise<void> {
    await this.goto("/digests")
  }

  async searchFor(text: string): Promise<void> {
    await this.searchInput.fill(text)
  }

  async openGenerateDialog(): Promise<void> {
    await this.generateButton.click()
  }

  async clickTableRow(index: number): Promise<void> {
    await this.tableRows.nth(index).click()
  }

  async getRowCount(): Promise<number> {
    return this.tableRows.count()
  }

  async selectTab(tabName: string): Promise<void> {
    await this.page.getByRole("tab", { name: tabName }).click()
  }
}
