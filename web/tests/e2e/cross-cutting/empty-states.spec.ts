/**
 * Empty States E2E Tests
 *
 * Verifies that every main page renders appropriate empty state UI
 * when the API returns empty data. Each page should communicate
 * clearly that no items exist rather than showing a broken layout.
 */

import { test, expect } from "../../fixtures"

test.describe("Empty States", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllEmpty()
  })

  test("Contents page shows empty state when no items exist", async ({
    contentsPage,
  }) => {
    await contentsPage.navigate()

    await expect(contentsPage.emptyState).toBeVisible()
    // Table should not be populated with data rows
    expect(await contentsPage.getRowCount()).toBe(0)
  })

  test("Summaries page shows empty state when no summaries exist", async ({
    summariesPage,
  }) => {
    await summariesPage.navigate()

    await expect(summariesPage.emptyState).toBeVisible()
    expect(await summariesPage.getRowCount()).toBe(0)
  })

  test("Digests page shows empty state when no digests exist", async ({
    digestsPage,
  }) => {
    await digestsPage.navigate()

    await expect(digestsPage.emptyState).toBeVisible()
  })

  test("Scripts page shows empty state when no scripts exist", async ({
    scriptsPage,
  }) => {
    await scriptsPage.navigate()

    await expect(scriptsPage.emptyState).toBeVisible()
  })

  test("Podcasts page shows empty state when no podcasts exist", async ({
    podcastsPage,
  }) => {
    await podcastsPage.navigate()

    await expect(podcastsPage.emptyState).toBeVisible()
  })

  test("Audio Digests page shows empty state when no audio digests exist", async ({
    audioDigestsPage,
  }) => {
    await audioDigestsPage.navigate()

    await expect(audioDigestsPage.emptyState).toBeVisible()
  })

  test("Themes page shows no analysis message when no themes exist", async ({
    themesPage,
  }) => {
    await themesPage.navigate()

    await expect(themesPage.emptyState).toBeVisible()
  })
})
