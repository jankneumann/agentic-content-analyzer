/**
 * Podcast Player Dialog Tests
 *
 * Tests for the podcast player dialog: opening, title, duration,
 * voice info, audio player elements, and dialog lifecycle.
 */

import { test, expect } from "../../fixtures"

test.describe("Podcast Player Dialog", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockPodcastDetail()
  })

  test("clicking table row opens player dialog", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.clickTableRow(0)

    const dialog = await podcastsPage.waitForDialog()
    await expect(dialog).toBeVisible()
  })

  test("dialog shows podcast title", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.clickTableRow(0)

    const dialog = await podcastsPage.waitForDialog()
    // From createPodcastDetail: title = "AI Weekly Deep Dive - Episode 42"
    await expect(dialog.getByText("AI Weekly Deep Dive - Episode 42")).toBeVisible()
  })

  test("dialog shows duration info", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.clickTableRow(0)

    const dialog = await podcastsPage.waitForDialog()
    // From createPodcastDetail: duration_seconds = 718 -> "11:58"
    await expect(dialog.getByText(/11:58/)).toBeVisible()
  })

  test("dialog shows voice provider info", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.clickTableRow(0)

    const dialog = await podcastsPage.waitForDialog()
    // From createPodcastDetail: voice_provider = "openai"
    await expect(dialog.getByText("openai")).toBeVisible()
  })

  test("dialog shows file size", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.clickTableRow(0)

    const dialog = await podcastsPage.waitForDialog()
    // From createPodcastDetail: file_size_bytes = 11520000 -> "11.0 MB"
    await expect(dialog.getByText("11.0 MB")).toBeVisible()
  })

  test("dialog shows format info", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.clickTableRow(0)

    const dialog = await podcastsPage.waitForDialog()
    // From createPodcastDetail: audio_format = "mp3"
    await expect(dialog.getByText("mp3")).toBeVisible()
  })

  test("audio player controls are present", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.clickTableRow(0)

    const dialog = await podcastsPage.waitForDialog()

    // Audio player has play/pause button
    await expect(dialog.getByRole("button", { name: /play/i })).toBeVisible()
    // Rewind and forward buttons
    await expect(dialog.getByRole("button", { name: /rewind/i })).toBeVisible()
    await expect(dialog.getByRole("button", { name: /forward/i })).toBeVisible()
  })

  test("audio element is present in dialog", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.clickTableRow(0)

    const dialog = await podcastsPage.waitForDialog()
    // Audio element should be rendered
    await expect(dialog.locator("audio")).toBeAttached()
  })

  test("dialog shows download button for completed podcasts", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.clickTableRow(0)

    const dialog = await podcastsPage.waitForDialog()
    await expect(dialog.getByRole("link", { name: /download/i })).toBeVisible()
  })

  test("dialog closes when Close button is clicked", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.clickTableRow(0)

    const dialog = await podcastsPage.waitForDialog()
    await expect(dialog).toBeVisible()

    await dialog.getByRole("button", { name: "Close" }).click()
    await expect(podcastsPage.dialog).not.toBeVisible()
  })

  test("dialog closes when Escape is pressed", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.clickTableRow(0)

    const dialog = await podcastsPage.waitForDialog()
    await expect(dialog).toBeVisible()

    await podcastsPage.closeDialogViaEscape()
    await expect(podcastsPage.dialog).not.toBeVisible()
  })
})
