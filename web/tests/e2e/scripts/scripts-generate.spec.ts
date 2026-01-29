/**
 * Generate Script Dialog Tests
 *
 * Tests for the script generation dialog: opening, digest selection,
 * length tabs, and submit behavior.
 */

import { test, expect } from "../fixtures"

test.describe("Generate Script Dialog", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockDigestDetail()
  })

  test("Generate Script button opens dialog", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await scriptsPage.openGenerateDialog()

    const dialog = await scriptsPage.waitForDialog()
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText("Generate Podcast Script")).toBeVisible()
  })

  test("dialog shows digest selection dropdown", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await scriptsPage.openGenerateDialog()

    const dialog = await scriptsPage.waitForDialog()
    await expect(dialog.getByText("Source Digest")).toBeVisible()
    await expect(dialog.getByText("Select a digest...")).toBeVisible()
  })

  test("dialog shows length tabs (Brief, Standard, Extended)", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await scriptsPage.openGenerateDialog()

    const dialog = await scriptsPage.waitForDialog()
    await expect(dialog.getByText("Script Length")).toBeVisible()
    await expect(dialog.getByRole("tab", { name: "Brief" })).toBeVisible()
    await expect(dialog.getByRole("tab", { name: "Standard" })).toBeVisible()
    await expect(dialog.getByRole("tab", { name: "Extended" })).toBeVisible()
  })

  test("Standard tab is selected by default", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await scriptsPage.openGenerateDialog()

    const dialog = await scriptsPage.waitForDialog()
    const standardTab = dialog.getByRole("tab", { name: "Standard" })
    await expect(standardTab).toHaveAttribute("data-state", "active")
  })

  test("clicking Brief tab switches selection", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await scriptsPage.openGenerateDialog()

    const dialog = await scriptsPage.waitForDialog()
    await dialog.getByRole("tab", { name: "Brief" }).click()

    const briefTab = dialog.getByRole("tab", { name: "Brief" })
    await expect(briefTab).toHaveAttribute("data-state", "active")
    await expect(dialog.getByText(/~5 minutes/)).toBeVisible()
  })

  test("clicking Extended tab switches selection", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await scriptsPage.openGenerateDialog()

    const dialog = await scriptsPage.waitForDialog()
    await dialog.getByRole("tab", { name: "Extended" }).click()

    const extendedTab = dialog.getByRole("tab", { name: "Extended" })
    await expect(extendedTab).toHaveAttribute("data-state", "active")
    await expect(dialog.getByText(/~15 minutes/)).toBeVisible()
  })

  test("dialog shows web search toggle", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await scriptsPage.openGenerateDialog()

    const dialog = await scriptsPage.waitForDialog()
    await expect(dialog.getByText("Enable Web Search")).toBeVisible()
  })

  test("dialog shows focus topics input", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await scriptsPage.openGenerateDialog()

    const dialog = await scriptsPage.waitForDialog()
    await expect(dialog.getByText("Focus Topics")).toBeVisible()
    await expect(dialog.getByPlaceholder("Add a topic to emphasize...")).toBeVisible()
  })

  test("Generate Script button is disabled without digest selection", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await scriptsPage.openGenerateDialog()

    const dialog = await scriptsPage.waitForDialog()
    const generateButton = dialog.getByRole("button", { name: /generate script/i })
    await expect(generateButton).toBeDisabled()
  })

  test("Cancel button closes the dialog", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    await scriptsPage.openGenerateDialog()

    const dialog = await scriptsPage.waitForDialog()
    await dialog.getByRole("button", { name: "Cancel" }).click()

    await expect(scriptsPage.dialog).not.toBeVisible()
  })
})
