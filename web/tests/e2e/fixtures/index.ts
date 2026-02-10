/**
 * Custom Test Fixtures
 *
 * Extends Playwright's base test with page objects and API mocks.
 * Import `test` and `expect` from this file instead of @playwright/test.
 *
 * Usage:
 *   import { test, expect } from '../fixtures'
 *
 *   test('example', async ({ contentsPage, apiMocks }) => {
 *     await apiMocks.mockAllDefaults()
 *     await contentsPage.navigate()
 *     await expect(contentsPage.table).toBeVisible()
 *   })
 */

import { test as base, expect } from "@playwright/test"
import { ApiMocks } from "./api-mocks"
import { BasePage } from "./base.page"
import { DashboardPage } from "./pages/dashboard.page"
import { ContentsPage } from "./pages/contents.page"
import { SummariesPage } from "./pages/summaries.page"
import { DigestsPage } from "./pages/digests.page"
import { ScriptsPage } from "./pages/scripts.page"
import { PodcastsPage } from "./pages/podcasts.page"
import { AudioDigestsPage } from "./pages/audio-digests.page"
import { ThemesPage } from "./pages/themes.page"
import { ReviewPage } from "./pages/review.page"
import { SettingsPage } from "./pages/settings.page"
import { TaskHistoryPage } from "./pages/task-history.page"

/** All custom fixtures available in tests */
interface Fixtures {
  basePage: BasePage
  dashboardPage: DashboardPage
  contentsPage: ContentsPage
  summariesPage: SummariesPage
  digestsPage: DigestsPage
  scriptsPage: ScriptsPage
  podcastsPage: PodcastsPage
  audioDigestsPage: AudioDigestsPage
  themesPage: ThemesPage
  reviewPage: ReviewPage
  settingsPage: SettingsPage
  taskHistoryPage: TaskHistoryPage
  apiMocks: ApiMocks
}

/**
 * Extended test with page objects and API mocks.
 *
 * Each fixture is lazily instantiated per test —
 * only the page objects you destructure in a test get created.
 */
export const test = base.extend<Fixtures>({
  basePage: async ({ page }, use) => {
    await use(new BasePage(page))
  },
  dashboardPage: async ({ page }, use) => {
    await use(new DashboardPage(page))
  },
  contentsPage: async ({ page }, use) => {
    await use(new ContentsPage(page))
  },
  summariesPage: async ({ page }, use) => {
    await use(new SummariesPage(page))
  },
  digestsPage: async ({ page }, use) => {
    await use(new DigestsPage(page))
  },
  scriptsPage: async ({ page }, use) => {
    await use(new ScriptsPage(page))
  },
  podcastsPage: async ({ page }, use) => {
    await use(new PodcastsPage(page))
  },
  audioDigestsPage: async ({ page }, use) => {
    await use(new AudioDigestsPage(page))
  },
  themesPage: async ({ page }, use) => {
    await use(new ThemesPage(page))
  },
  reviewPage: async ({ page }, use) => {
    await use(new ReviewPage(page))
  },
  settingsPage: async ({ page }, use) => {
    await use(new SettingsPage(page))
  },
  taskHistoryPage: async ({ page }, use) => {
    await use(new TaskHistoryPage(page))
  },
  apiMocks: async ({ page }, use) => {
    await use(new ApiMocks(page))
  },
})

export { expect }
