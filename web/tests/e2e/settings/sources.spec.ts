import { test, expect } from "../fixtures"

test.describe("Settings > Sources", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("renders mixed origins and keeps Obsidian identity opaque", async ({
    page,
    settingsPage,
  }) => {
    await settingsPage.navigateSources()

    await expect(settingsPage.sourcesTitle).toBeVisible()
    await expect(page.getByText("Release feed", { exact: true })).toBeVisible()
    await expect(
      page.getByText("Readwise Reader", { exact: true })
    ).toBeVisible()
    await expect(page.getByText("yaml", { exact: true })).toHaveCount(1)
    await expect(page.getByText("db", { exact: true })).toHaveCount(2)
    await expect(settingsPage.sourceToggle("Release feed")).toBeChecked()
    await expect(settingsPage.sourceToggle("Readwise Reader")).not.toBeChecked()

    await expect(
      page.getByText("Obsidian vault", { exact: true })
    ).toBeVisible()
    await expect(
      page.getByText("src_0123456789abcdefabcd", { exact: true })
    ).toBeVisible()
    await expect(page.getByText(/private research vault/i)).toHaveCount(0)
    await expect(
      page.getByText(/\/srv\/private|vault_path|ingest_folder/i)
    ).toHaveCount(0)

    await settingsPage.addSourceButton.click()
    const addDialog = page.getByRole("dialog", { name: "Add ingestion source" })
    await addDialog.getByRole("combobox", { name: "Type" }).click()
    await expect(page.getByRole("option", { name: "Obsidian" })).toHaveCount(0)
    await expect(addDialog.getByLabel(/vault|folder|path/i)).toHaveCount(0)
  })

  test("adds Readwise with only the reviewed nested quick-add fields", async ({
    page,
    settingsPage,
  }) => {
    await settingsPage.navigateSources()
    await settingsPage.addSourceButton.click()
    await settingsPage.selectSourceType("Readwise")
    await page
      .getByRole("textbox", { name: "Source types" })
      .fill("articles, books")
    await page.getByRole("checkbox", { name: "Include deleted items" }).click()

    const requestPromise = page.waitForRequest(
      (request) =>
        request.url().endsWith("/api/v1/sources") && request.method() === "POST"
    )
    await page.getByRole("button", { name: "Add", exact: true }).click()
    const request = await requestPromise
    const body = request.postDataJSON()

    expect(body).toEqual({
      config: {
        type: "readwise",
        source_types: ["articles", "books"],
        include_deleted: true,
      },
    })
    expect(JSON.stringify(body)).not.toMatch(/token|secret|credential/i)
    await expect(settingsPage.sourceToggle("Readwise Reader")).toBeChecked()
  })

  test("toggles through PATCH and reflects only the confirmed response", async ({
    page,
    settingsPage,
  }) => {
    await settingsPage.navigateSources()
    const toggle = settingsPage.sourceToggle("Readwise Reader")
    await expect(toggle).not.toBeChecked()

    const requestPromise = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/sources/readwise%3Areader") &&
        request.method() === "PATCH"
    )
    await toggle.click()
    const request = await requestPromise

    expect(request.postDataJSON()).toEqual({ enabled: true })
    await expect(toggle).toBeChecked()
  })

  test("uses generic database-override deletion semantics", async ({
    page,
    settingsPage,
  }) => {
    await settingsPage.navigateSources()
    await settingsPage.removeOverrideButton("Readwise Reader").click()

    const dialog = page.getByRole("dialog", {
      name: "Remove database override?",
    })
    await expect(dialog).toContainText(
      "Remove database override; a YAML definition may reappear."
    )

    const requestPromise = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/sources/readwise%3Areader") &&
        request.method() === "DELETE"
    )
    await dialog.getByRole("button", { name: "Remove override" }).click()
    await requestPromise

    await expect(
      page.getByText("Readwise Reader", { exact: true })
    ).toHaveCount(0)
  })

  test("keeps Readwise add recoverable after an authorization failure", async ({
    page,
    settingsPage,
    apiMocks,
  }) => {
    await apiMocks.mockSources(undefined, {
      add: { status: 403, detail: "Admin credentials are invalid" },
    })
    await settingsPage.navigateSources()
    await settingsPage.addSourceButton.click()
    await settingsPage.selectSourceType("Readwise")
    await page.getByRole("button", { name: "Add", exact: true }).click()

    await expect(page.getByRole("alert")).toContainText(
      "Admin credentials are invalid"
    )
    await expect(
      page.getByRole("dialog", { name: "Add ingestion source" })
    ).toBeVisible()
    await expect(
      page.getByRole("button", { name: "Add", exact: true })
    ).toBeEnabled()
  })

  test("rolls back a failed toggle and leaves the control usable", async ({
    page,
    settingsPage,
    apiMocks,
  }) => {
    await apiMocks.mockSources(undefined, {
      toggle: { status: 500, detail: "Source update failed" },
    })
    await settingsPage.navigateSources()
    const toggle = settingsPage.sourceToggle("Readwise Reader")
    await toggle.click()

    await expect(page.getByRole("alert")).toContainText("Source update failed")
    await expect(toggle).not.toBeChecked()
    await expect(toggle).toBeEnabled()
  })

  test("keeps the override row after a failed deletion", async ({
    page,
    settingsPage,
    apiMocks,
  }) => {
    await apiMocks.mockSources(undefined, {
      delete: { status: 404, detail: "Source override no longer exists" },
    })
    await settingsPage.navigateSources()
    await settingsPage.removeOverrideButton("Readwise Reader").click()
    await page.getByRole("button", { name: "Remove override" }).click()

    await expect(page.getByRole("alert")).toContainText(
      "Source override no longer exists"
    )
    await page.getByRole("button", { name: "Cancel" }).click()
    await expect(
      page.getByText("Readwise Reader", { exact: true })
    ).toBeVisible()
    await expect(settingsPage.sourceToggle("Readwise Reader")).not.toBeChecked()
  })
})
