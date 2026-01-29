import { BasePage } from "../base.page"
import type { Page, Locator } from "@playwright/test"

export class SummariesPage extends BasePage {
  readonly searchInput: Locator
  readonly modelFilter: Locator
  readonly table: Locator
  readonly tableRows: Locator
  readonly generateButton: Locator
  readonly emptyState: Locator

  constructor(page: Page) {
    super(page)
    this.searchInput = page.getByPlaceholder(/search/i)
    this.modelFilter = page.getByRole("combobox").first()
    this.table = page.getByRole("table")
    this.tableRows = page.locator("tbody tr")
    this.generateButton = page.getByRole("button", { name: /generate/i })
    this.emptyState = page.getByText(/no summar|no items|no results/i)
  }

  async navigate(): Promise<void> {
    await this.goto("/summaries")
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
}
