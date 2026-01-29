/**
 * Script Detail Dialog Tests
 *
 * Tests for the script detail dialog opened from the scripts table.
 * Verifies script metadata, dialogue sections, speaker badges, and dialog lifecycle.
 */

import { test, expect } from "../../fixtures"

test.describe("Script Detail Dialog", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockScriptDetail()
  })

  test("clicking view button opens detail dialog", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    // Click the view button on the first row
    const viewButton = scriptsPage.page.getByRole("button", { name: "View script" }).first()
    await viewButton.click()

    const dialog = await scriptsPage.waitForDialog()
    await expect(dialog).toBeVisible()
  })

  test("dialog shows script title", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    const viewButton = scriptsPage.page.getByRole("button", { name: "View script" }).first()
    await viewButton.click()

    const dialog = await scriptsPage.waitForDialog()
    await expect(dialog.getByText("Script Details")).toBeVisible()
  })

  test("dialog shows script metadata - length", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    const viewButton = scriptsPage.page.getByRole("button", { name: "View script" }).first()
    await viewButton.click()

    const dialog = await scriptsPage.waitForDialog()
    // From createScriptDetail: length = "standard"
    await expect(dialog.getByText("standard")).toBeVisible()
  })

  test("dialog shows script metadata - title field", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    const viewButton = scriptsPage.page.getByRole("button", { name: "View script" }).first()
    await viewButton.click()

    const dialog = await scriptsPage.waitForDialog()
    // From createScriptDetail: title = "AI Weekly Deep Dive - Episode 42"
    await expect(dialog.getByText("AI Weekly Deep Dive - Episode 42")).toBeVisible()
  })

  test("dialog shows dialogue sections", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    const viewButton = scriptsPage.page.getByRole("button", { name: "View script" }).first()
    await viewButton.click()

    const dialog = await scriptsPage.waitForDialog()
    // From createScriptDetail: sections include "Opening", "Strategic Insights", etc.
    await expect(dialog.getByText("Opening")).toBeVisible()
    await expect(dialog.getByText("Strategic Insights")).toBeVisible()
    await expect(dialog.getByText("Technical Deep-Dive")).toBeVisible()
  })

  test("dialog shows speaker names in dialogue", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    const viewButton = scriptsPage.page.getByRole("button", { name: "View script" }).first()
    await viewButton.click()

    const dialog = await scriptsPage.waitForDialog()
    // From createScriptSection: dialogue has speakers "alex" and "sam"
    await expect(dialog.getByText("alex").first()).toBeVisible()
    await expect(dialog.getByText("sam").first()).toBeVisible()
  })

  test("dialog shows speaker dialogue text", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    const viewButton = scriptsPage.page.getByRole("button", { name: "View script" }).first()
    await viewButton.click()

    const dialog = await scriptsPage.waitForDialog()
    // From createScriptSection: alex says "Welcome to another episode..."
    await expect(
      dialog.getByText(/Welcome to another episode/)
    ).toBeVisible()
  })

  test("dialog shows emphasis badges when present", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    const viewButton = scriptsPage.page.getByRole("button", { name: "View script" }).first()
    await viewButton.click()

    const dialog = await scriptsPage.waitForDialog()
    // From createScriptSection: first dialogue has emphasis "excited"
    await expect(dialog.getByText("[excited]")).toBeVisible()
  })

  test("dialog shows section word counts", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    const viewButton = scriptsPage.page.getByRole("button", { name: "View script" }).first()
    await viewButton.click()

    const dialog = await scriptsPage.waitForDialog()
    // From createScriptSection: word_count = 250
    await expect(dialog.getByText("250 words").first()).toBeVisible()
  })

  test("dialog closes when Close button is clicked", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    const viewButton = scriptsPage.page.getByRole("button", { name: "View script" }).first()
    await viewButton.click()

    const dialog = await scriptsPage.waitForDialog()
    await expect(dialog).toBeVisible()

    await dialog.getByRole("button", { name: "Close" }).click()
    await expect(scriptsPage.dialog).not.toBeVisible()
  })

  test("dialog closes when Escape is pressed", async ({ scriptsPage }) => {
    await scriptsPage.navigate()

    const viewButton = scriptsPage.page.getByRole("button", { name: "View script" }).first()
    await viewButton.click()

    const dialog = await scriptsPage.waitForDialog()
    await expect(dialog).toBeVisible()

    await scriptsPage.closeDialogViaEscape()
    await expect(scriptsPage.dialog).not.toBeVisible()
  })
})
