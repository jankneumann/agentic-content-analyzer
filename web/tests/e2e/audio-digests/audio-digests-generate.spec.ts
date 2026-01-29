/**
 * Generate Audio Digest Dialog Tests
 *
 * Tests for the audio digest generation dialog: opening, digest selection,
 * voice selection, speed slider, provider selection, and submit behavior.
 */

import { test, expect } from "../../fixtures"

test.describe("Generate Audio Digest Dialog", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockAvailableDigests()
  })

  test("Generate Audio button opens dialog", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.openGenerateDialog()

    const dialog = await audioDigestsPage.waitForDialog()
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText("Generate Audio Digest")).toBeVisible()
  })

  test("dialog description mentions single-voice", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.openGenerateDialog()

    const dialog = await audioDigestsPage.waitForDialog()
    await expect(
      dialog.getByText(/single-voice audio narration/i)
    ).toBeVisible()
  })

  test("dialog shows digest selection dropdown", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.openGenerateDialog()

    const dialog = await audioDigestsPage.waitForDialog()
    await expect(dialog.getByText("Source Digest")).toBeVisible()
    await expect(dialog.getByText("Select a digest...")).toBeVisible()
  })

  test("dialog shows voice provider selection", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.openGenerateDialog()

    const dialog = await audioDigestsPage.waitForDialog()
    await expect(dialog.getByText("Voice Provider")).toBeVisible()
  })

  test("dialog shows voice selection dropdown", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.openGenerateDialog()

    const dialog = await audioDigestsPage.waitForDialog()
    await expect(dialog.getByText("Voice")).toBeVisible()
  })

  test("dialog shows speed slider", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.openGenerateDialog()

    const dialog = await audioDigestsPage.waitForDialog()
    await expect(dialog.getByText("Playback Speed")).toBeVisible()
    // Speed slider shows min/max labels
    await expect(dialog.getByText("0.5x").first()).toBeVisible()
    await expect(dialog.getByText("2.0x")).toBeVisible()
  })

  test("speed displays default 1.0x value", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.openGenerateDialog()

    const dialog = await audioDigestsPage.waitForDialog()
    await expect(dialog.getByText("1.0x").first()).toBeVisible()
  })

  test("Generate Audio button is disabled without digest selection", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.openGenerateDialog()

    const dialog = await audioDigestsPage.waitForDialog()
    const generateButton = dialog.getByRole("button", { name: /generate audio/i })
    await expect(generateButton).toBeDisabled()
  })

  test("Cancel button closes the dialog", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.openGenerateDialog()

    const dialog = await audioDigestsPage.waitForDialog()
    await dialog.getByRole("button", { name: "Cancel" }).click()

    await expect(audioDigestsPage.dialog).not.toBeVisible()
  })

  test("voice provider defaults to OpenAI TTS", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.openGenerateDialog()

    const dialog = await audioDigestsPage.waitForDialog()
    await expect(dialog.getByText("OpenAI TTS")).toBeVisible()
  })
})
