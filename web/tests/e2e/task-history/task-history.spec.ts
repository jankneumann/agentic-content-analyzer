/**
 * Task History Page Tests
 *
 * Tests the /task-history page: table rendering, filter controls,
 * empty state, pagination, and status badges.
 */

import { test, expect } from "../fixtures"
import {
  createJobHistoryItem,
  createJobHistoryResponse,
} from "../fixtures/mock-data"

test.describe("Task History Page", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("renders table with task history items", async ({ taskHistoryPage }) => {
    await taskHistoryPage.navigate()

    await expect(taskHistoryPage.table).toBeVisible()

    // Default mock has 3 items
    await expect(taskHistoryPage.rows).toHaveCount(3)

    // Verify task labels appear
    await expect(taskHistoryPage.page.getByText("Summarize").first()).toBeVisible()
    await expect(taskHistoryPage.page.getByText("Ingest", { exact: true })).toBeVisible()

    // Verify descriptions appear
    await expect(taskHistoryPage.page.getByText("AI Weekly Newsletter")).toBeVisible()
    await expect(taskHistoryPage.page.getByText("Gmail ingestion")).toBeVisible()
  })

  test("shows empty state when no history exists", async ({
    taskHistoryPage,
    apiMocks,
  }) => {
    await apiMocks.mockJobHistoryEmpty()
    await taskHistoryPage.navigate()

    await expect(taskHistoryPage.emptyState).toBeVisible()
    await expect(taskHistoryPage.table).not.toBeVisible()
  })

  test("displays status badges with correct variants", async ({
    taskHistoryPage,
  }) => {
    await taskHistoryPage.navigate()

    // Completed badge
    await expect(taskHistoryPage.page.getByText("Completed").first()).toBeVisible()

    // Failed badge
    await expect(taskHistoryPage.page.getByText("Failed")).toBeVisible()
  })

  test("filter controls are visible", async ({ taskHistoryPage }) => {
    await taskHistoryPage.navigate()

    // All three filter selects should be present
    await expect(taskHistoryPage.timeRangeSelect).toBeVisible()
    await expect(taskHistoryPage.taskTypeSelect).toBeVisible()
    await expect(taskHistoryPage.statusSelect).toBeVisible()
  })

  test("pagination controls appear when needed", async ({
    taskHistoryPage,
    apiMocks,
  }) => {
    const manyItems = Array.from({ length: 50 }, (_, i) =>
      createJobHistoryItem({
        id: i + 1,
        description: `Task ${i + 1}`,
      })
    )
    await apiMocks.mockJobHistory(
      createJobHistoryResponse({
        data: manyItems,
        pagination: { page: 1, page_size: 20, total: 60 },
      })
    )

    await taskHistoryPage.navigate()

    // Should show pagination info
    await expect(taskHistoryPage.paginationInfo).toBeVisible()
    await expect(taskHistoryPage.page.getByText("Page 1 of 3")).toBeVisible()

    // Previous should be disabled on first page
    await expect(taskHistoryPage.prevButton).toBeDisabled()
    await expect(taskHistoryPage.nextButton).toBeEnabled()
  })

  test("pagination is hidden with single page of results", async ({
    taskHistoryPage,
  }) => {
    // Default mock has 3 items with total=3, fits in one page
    await taskHistoryPage.navigate()

    await expect(taskHistoryPage.table).toBeVisible()
    await expect(taskHistoryPage.prevButton).not.toBeVisible()
    await expect(taskHistoryPage.nextButton).not.toBeVisible()
  })

  test("page title and description are visible", async ({
    taskHistoryPage,
  }) => {
    await taskHistoryPage.navigate()

    await expect(
      taskHistoryPage.page.getByRole("heading", { name: "Task History" })
    ).toBeVisible()
    await expect(
      taskHistoryPage.page.getByText("Audit log of all pipeline task executions")
    ).toBeVisible()
  })
})
