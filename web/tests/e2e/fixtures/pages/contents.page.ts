import { BasePage } from "../base.page"
import type { Page, Locator } from "@playwright/test"

export class ContentsPage extends BasePage {
  readonly searchInput: Locator
  readonly sourceFilter: Locator
  readonly statusFilter: Locator
  readonly table: Locator
  readonly tableRows: Locator
  readonly ingestButton: Locator
  readonly emptyState: Locator
  readonly statsCards: Locator

  constructor(page: Page) {
    super(page)
    this.searchInput = page.getByPlaceholder(/search/i)
    this.sourceFilter = page.getByRole("combobox").filter({ hasText: /source|all sources/i }).first()
    this.statusFilter = page.getByRole("combobox").filter({ hasText: /status|all status/i }).first()
    this.table = page.getByRole("table")
    this.tableRows = page.locator("tbody tr")
    this.ingestButton = page.getByRole("button", { name: /ingest/i })
    this.emptyState = page.getByText(/no content|no items|no results/i)
    this.statsCards = page.locator(".grid").first()
  }

  async navigate(): Promise<void> {
    await this.goto("/contents")
  }

  async searchFor(text: string): Promise<void> {
    await this.searchInput.fill(text)
  }

  async openIngestDialog(): Promise<void> {
    await this.ingestButton.click()
  }

  async clickTableRow(index: number): Promise<void> {
    await this.tableRows.nth(index).click()
  }

  async getRowCount(): Promise<number> {
    return this.tableRows.count()
  }
}
