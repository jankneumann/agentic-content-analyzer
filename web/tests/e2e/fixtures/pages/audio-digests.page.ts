import { BasePage } from "../base.page"
import type { Page, Locator } from "@playwright/test"

export class AudioDigestsPage extends BasePage {
  readonly statusFilter: Locator
  readonly table: Locator
  readonly tableRows: Locator
  readonly generateButton: Locator
  readonly emptyState: Locator
  readonly audioPlayer: Locator

  constructor(page: Page) {
    super(page)
    this.statusFilter = page.getByRole("combobox").first()
    this.table = page.getByRole("table")
    this.tableRows = page.locator("tbody tr")
    this.generateButton = page.getByRole("button", { name: /generate/i })
    this.emptyState = page.getByText(/no audio|no items|no results/i)
    this.audioPlayer = page.locator("audio, [data-testid='audio-player']")
  }

  async navigate(): Promise<void> {
    await this.goto("/audio-digests")
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
