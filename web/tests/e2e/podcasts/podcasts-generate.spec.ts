/**
 * Generate Podcast Dialog Tests
 *
 * Tests for the podcast audio generation dialog: opening, script selection,
 * voice provider options, and submit behavior.
 */

import { test, expect } from "../fixtures"

test.describe("Generate Podcast Dialog", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockApprovedScripts()
  })

  test("Generate Audio button opens dialog", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.openGenerateDialog()

    const dialog = await podcastsPage.waitForDialog()
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText("Generate Podcast Audio")).toBeVisible()
  })

  test("dialog shows script selection dropdown", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.openGenerateDialog()

    const dialog = await podcastsPage.waitForDialog()
    await expect(dialog.getByText("Source Script")).toBeVisible()
    await expect(dialog.getByText("Select an approved script...")).toBeVisible()
  })

  test("dialog shows voice provider selection", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.openGenerateDialog()

    const dialog = await podcastsPage.waitForDialog()
    await expect(dialog.getByText("Voice Provider")).toBeVisible()
  })

  test("dialog shows Alex and Sam voice selections", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.openGenerateDialog()

    const dialog = await podcastsPage.waitForDialog()
    await expect(dialog.getByText("Alex Voice")).toBeVisible()
    await expect(dialog.getByText("Sam Voice")).toBeVisible()
  })

  test("dialog shows VP of Engineering and Distinguished Engineer labels", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.openGenerateDialog()

    const dialog = await podcastsPage.waitForDialog()
    await expect(dialog.getByText("VP of Engineering")).toBeVisible()
    await expect(dialog.getByText("Distinguished Engineer")).toBeVisible()
  })

  test("Generate Audio button is disabled without script selection", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.openGenerateDialog()

    const dialog = await podcastsPage.waitForDialog()
    const generateButton = dialog.getByRole("button", { name: /generate audio/i })
    await expect(generateButton).toBeDisabled()
  })

  test("Cancel button closes the dialog", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.openGenerateDialog()

    const dialog = await podcastsPage.waitForDialog()
    await dialog.getByRole("button", { name: "Cancel" }).click()

    await expect(podcastsPage.dialog).not.toBeVisible()
  })

  test("dialog description mentions approved script", async ({ podcastsPage }) => {
    await podcastsPage.navigate()

    await podcastsPage.openGenerateDialog()

    const dialog = await podcastsPage.waitForDialog()
    await expect(
      dialog.getByText(/synthesize audio from an approved podcast script/i)
    ).toBeVisible()
  })
})
