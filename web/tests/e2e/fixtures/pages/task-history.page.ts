import { BasePage } from "../base.page"
import type { Page, Locator } from "@playwright/test"

export class TaskHistoryPage extends BasePage {
  readonly table: Locator
  readonly rows: Locator
  readonly emptyState: Locator
  readonly timeRangeSelect: Locator
  readonly taskTypeSelect: Locator
  readonly statusSelect: Locator
  readonly prevButton: Locator
  readonly nextButton: Locator
  readonly paginationInfo: Locator

  constructor(page: Page) {
    super(page)
    this.table = page.locator("table")
    this.rows = page.locator("table tbody tr")
    this.emptyState = page.getByText("No task history found")
    this.timeRangeSelect = page.getByRole("combobox").first()
    this.taskTypeSelect = page.getByRole("combobox").nth(1)
    this.statusSelect = page.getByRole("combobox").nth(2)
    this.prevButton = page.getByRole("button", { name: "Previous" })
    this.nextButton = page.getByRole("button", { name: "Next" })
    this.paginationInfo = page.getByText(/Page \d+ of \d+/)
  }

  async navigate(): Promise<void> {
    await this.goto("/task-history")
  }
}
