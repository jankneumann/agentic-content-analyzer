/**
 * Audio Digest Player Dialog Tests
 *
 * Tests for the audio digest player dialog: opening, audio player elements,
 * voice/speed/provider info, and dialog lifecycle.
 */

import { test, expect } from "../fixtures"

test.describe("Audio Digest Player Dialog", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockAudioDigestDetail()
  })

  test("clicking table row opens player dialog", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.clickTableRow(0)

    const dialog = await audioDigestsPage.waitForDialog()
    await expect(dialog).toBeVisible()
  })

  test("dialog shows Audio Digest Player title", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.clickTableRow(0)

    const dialog = await audioDigestsPage.waitForDialog()
    await expect(dialog.getByText("Audio Digest Player")).toBeVisible()
  })

  test("dialog shows digest ID reference", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.clickTableRow(0)

    const dialog = await audioDigestsPage.waitForDialog()
    // From createAudioDigestDetail: digest_id = 1
    await expect(dialog.getByText(/Digest #1/)).toBeVisible()
  })

  test("dialog shows voice info", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.clickTableRow(0)

    const dialog = await audioDigestsPage.waitForDialog()
    // From createAudioDigestDetail: voice = "nova" (capitalize is CSS-only)
    await expect(dialog.getByText("Voice:")).toBeVisible()
    await expect(dialog.getByText("nova").first()).toBeVisible()
  })

  test("dialog shows speed info", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.clickTableRow(0)

    const dialog = await audioDigestsPage.waitForDialog()
    // From createAudioDigestDetail: speed = 1.0
    await expect(dialog.getByText("Speed:")).toBeVisible()
    await expect(dialog.getByText("1x").first()).toBeVisible()
  })

  test("dialog shows provider info", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.clickTableRow(0)

    const dialog = await audioDigestsPage.waitForDialog()
    // From createAudioDigestDetail: provider = "openai" (capitalize is CSS-only)
    await expect(dialog.getByText("Provider:")).toBeVisible()
    await expect(dialog.getByText("openai").first()).toBeVisible()
  })

  test("dialog shows file size", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.clickTableRow(0)

    const dialog = await audioDigestsPage.waitForDialog()
    // From createAudioDigestDetail: file_size_bytes = 7680000 -> "7.3 MB"
    await expect(dialog.getByText("File Size:")).toBeVisible()
    await expect(dialog.getByText("7.3 MB")).toBeVisible()
  })

  test("audio player controls are present", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.clickTableRow(0)

    const dialog = await audioDigestsPage.waitForDialog()

    // Audio player has play/pause, rewind, forward buttons
    await expect(dialog.getByRole("button", { name: /play/i })).toBeVisible()
    await expect(dialog.getByRole("button", { name: /rewind/i })).toBeVisible()
    await expect(dialog.getByRole("button", { name: /forward/i })).toBeVisible()
  })

  test("audio element is present in dialog", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.clickTableRow(0)

    const dialog = await audioDigestsPage.waitForDialog()
    await expect(dialog.locator("audio")).toBeAttached()
  })

  test("dialog shows download button for completed digests", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.clickTableRow(0)

    const dialog = await audioDigestsPage.waitForDialog()
    await expect(dialog.getByRole("link", { name: /download/i })).toBeVisible()
  })

  test("dialog closes when Close button is clicked", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.clickTableRow(0)

    const dialog = await audioDigestsPage.waitForDialog()
    await expect(dialog).toBeVisible()

    await dialog.getByRole("button", { name: "Close" }).first().click()
    await expect(audioDigestsPage.dialog).not.toBeVisible()
  })

  test("dialog closes when Escape is pressed", async ({ audioDigestsPage }) => {
    await audioDigestsPage.navigate()

    await audioDigestsPage.clickTableRow(0)

    const dialog = await audioDigestsPage.waitForDialog()
    await expect(dialog).toBeVisible()

    await audioDigestsPage.closeDialogViaEscape()
    await expect(audioDigestsPage.dialog).not.toBeVisible()
  })
})
