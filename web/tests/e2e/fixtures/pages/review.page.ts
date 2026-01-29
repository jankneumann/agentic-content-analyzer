import { BasePage } from "../base.page"
import type { Page, Locator } from "@playwright/test"

export class ReviewPage extends BasePage {
  readonly reviewLinks: Locator
  readonly pendingCount: Locator
  readonly emptyState: Locator
  readonly leftPane: Locator
  readonly rightPane: Locator
  readonly feedbackPanel: Locator
  readonly approveButton: Locator
  readonly rejectButton: Locator
  readonly prevButton: Locator
  readonly nextButton: Locator

  constructor(page: Page) {
    super(page)
    this.reviewLinks = page.getByRole("link").filter({ hasText: /review|pending/i })
    this.pendingCount = page.locator('[data-testid="pending-count"], .badge')
    this.emptyState = page.getByText(/no items|nothing.*review|all caught up/i)
    this.leftPane = page.locator('[data-testid="left-pane"], .flex-1').first()
    this.rightPane = page.locator('[data-testid="right-pane"], .flex-1').last()
    this.feedbackPanel = page.locator('[data-testid="feedback-panel"]')
    this.approveButton = page.getByRole("button", { name: /approve/i })
    this.rejectButton = page.getByRole("button", { name: /reject/i })
    this.prevButton = page.getByRole("button", { name: /prev|previous/i })
    this.nextButton = page.getByRole("button", { name: /next/i }).first()
  }

  async navigate(): Promise<void> {
    await this.goto("/review")
  }

  async navigateToDigestReview(id: number): Promise<void> {
    await this.goto(`/review/digest/${id}`)
  }

  async navigateToSummaryReview(id: number): Promise<void> {
    await this.goto(`/review/summary/${id}`)
  }

  async navigateToScriptReview(id: number): Promise<void> {
    await this.goto(`/review/script/${id}`)
  }
}
