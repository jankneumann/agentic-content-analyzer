/**
 * Settings > Prompts E2E Tests
 *
 * Tests the prompt management UI on the Settings page:
 * - Prompt list with category grouping
 * - Override indicators
 * - Prompt editor dialog (edit, save, reset, test)
 * - Search filtering
 * - Error and empty states
 */

import { test, expect } from "../fixtures"
import {
  createPromptListResponse,
  createPromptInfo,
  createEmptyPromptListResponse,
  createPromptTestResponse,
} from "../fixtures/mock-data"

test.describe("Settings > Prompts", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockPrompts()
    await apiMocks.mockPromptDetail()
    await apiMocks.mockPromptUpdate()
    await apiMocks.mockPromptTest()
  })

  test.describe("Prompt List", () => {
    test("displays prompt categories on the settings page", async ({
      settingsPage,
    }) => {
      await settingsPage.navigate()

      // The LLM Prompts section should be visible
      await expect(
        settingsPage.page.getByText("Prompt Configuration")
      ).toBeVisible()

      // Category groups should be visible
      await expect(
        settingsPage.page.getByRole("button", { name: /Pipeline/i })
      ).toBeVisible()
      await expect(
        settingsPage.page.getByRole("button", { name: /Chat/i })
      ).toBeVisible()
    })

    test("shows prompt count in category headers", async ({
      settingsPage,
    }) => {
      await settingsPage.navigate()

      // Pipeline category has 3 prompts in default mock
      const pipelineButton = settingsPage.page.getByRole("button", {
        name: /Pipeline/i,
      })
      await expect(pipelineButton).toContainText("(3)")

      // Chat category has 1 prompt
      const chatButton = settingsPage.page.getByRole("button", {
        name: /Chat/i,
      })
      await expect(chatButton).toContainText("(1)")
    })

    test("shows override badge on categories with overrides", async ({
      settingsPage,
    }) => {
      await settingsPage.navigate()

      // Pipeline category has 1 override (digest_creation.system)
      const pipelineButton = settingsPage.page.getByRole("button", {
        name: /Pipeline/i,
      })
      await expect(pipelineButton).toContainText("1 override")
    })

    test("expands category to show prompts", async ({ settingsPage }) => {
      await settingsPage.navigate()

      // Click Pipeline to expand
      await settingsPage.page
        .getByRole("button", { name: /Pipeline/i })
        .click()

      // Should show the individual prompts inside
      await expect(
        settingsPage.page.getByText("pipeline.summarization.system")
      ).toBeVisible()
      await expect(
        settingsPage.page.getByText("pipeline.summarization.user_template")
      ).toBeVisible()
      await expect(
        settingsPage.page.getByText("pipeline.digest_creation.system")
      ).toBeVisible()
    })

    test("shows Override badge on overridden prompts", async ({
      settingsPage,
    }) => {
      await settingsPage.navigate()

      // Expand pipeline
      await settingsPage.page
        .getByRole("button", { name: /Pipeline/i })
        .click()

      // The digest_creation prompt should show an Override badge
      const digestRow = settingsPage.page
        .locator("button")
        .filter({ hasText: "pipeline.digest_creation.system" })
      await expect(digestRow.getByText("Override")).toBeVisible()
      await expect(digestRow.getByText("v2")).toBeVisible()
    })

    test("search filters prompts across categories", async ({
      settingsPage,
    }) => {
      await settingsPage.navigate()

      // Type in search
      await settingsPage.page.getByPlaceholder("Search prompts...").fill("digest")

      // Should show filtered count
      await expect(settingsPage.page.getByText("1 prompts")).toBeVisible()

      // Only pipeline category should remain (with digest prompt)
      await expect(
        settingsPage.page.getByRole("button", { name: /Pipeline/i })
      ).toBeVisible()

      // Chat category should be gone (no match)
      await expect(
        settingsPage.page.getByRole("button", { name: /Chat/i })
      ).not.toBeVisible()
    })

    test("shows empty state when no prompts match search", async ({
      settingsPage,
    }) => {
      await settingsPage.navigate()

      await settingsPage.page
        .getByPlaceholder("Search prompts...")
        .fill("nonexistent_prompt_xyz")

      await expect(
        settingsPage.page.getByText(/No prompts matching/)
      ).toBeVisible()
    })

    test("shows empty state when no prompts exist", async ({
      settingsPage,
      apiMocks,
    }) => {
      await apiMocks.mockPromptsEmpty()
      await settingsPage.navigate()

      await expect(
        settingsPage.page.getByText("No prompts configured")
      ).toBeVisible()
    })

    test("shows error state on API failure", async ({
      settingsPage,
      apiMocks,
    }) => {
      await apiMocks.mockWithError(
        "**/api/v1/settings/prompts",
        500,
        "Internal server error"
      )
      await settingsPage.navigate()

      await expect(
        settingsPage.page.getByText(/Failed to load prompts/)
      ).toBeVisible()

      // Retry button should be present
      await expect(
        settingsPage.page.getByRole("button", { name: /Retry/i })
      ).toBeVisible()
    })
  })

  test.describe("Prompt Editor Dialog", () => {
    test("opens editor dialog when clicking a prompt", async ({
      settingsPage,
    }) => {
      await settingsPage.navigate()

      // Expand pipeline category
      await settingsPage.page
        .getByRole("button", { name: /Pipeline/i })
        .click()

      // Click on a prompt
      await settingsPage.page
        .locator("button")
        .filter({ hasText: "pipeline.summarization.system" })
        .click()

      // Dialog should open
      const dialog = settingsPage.page.getByRole("dialog")
      await expect(dialog).toBeVisible()
      await expect(dialog.getByText("Edit Prompt")).toBeVisible()
      await expect(
        dialog.getByText("pipeline.summarization.system")
      ).toBeVisible()
    })

    test("shows prompt value in textarea", async ({ settingsPage }) => {
      await settingsPage.navigate()

      // Expand and click a prompt
      await settingsPage.page
        .getByRole("button", { name: /Pipeline/i })
        .click()
      await settingsPage.page
        .locator("button")
        .filter({ hasText: "pipeline.summarization.system" })
        .click()

      // Textarea should contain the prompt value
      const textarea = settingsPage.page.getByRole("dialog").locator("textarea")
      await expect(textarea).toHaveValue(
        /You are a professional content analyst/
      )
    })

    test("enables Save button only when value changes", async ({
      settingsPage,
    }) => {
      await settingsPage.navigate()

      await settingsPage.page
        .getByRole("button", { name: /Pipeline/i })
        .click()
      await settingsPage.page
        .locator("button")
        .filter({ hasText: "pipeline.summarization.system" })
        .click()

      const dialog = settingsPage.page.getByRole("dialog")

      // Save should be disabled initially (no changes)
      const saveButton = dialog.getByRole("button", { name: /Save/i })
      await expect(saveButton).toBeDisabled()

      // Type something to make it dirty
      const textarea = dialog.locator("textarea")
      await textarea.fill("Modified prompt value")

      // Save should now be enabled
      await expect(saveButton).toBeEnabled()
    })

    test("shows Show Default toggle for diff view", async ({
      settingsPage,
    }) => {
      await settingsPage.navigate()

      await settingsPage.page
        .getByRole("button", { name: /Pipeline/i })
        .click()
      await settingsPage.page
        .locator("button")
        .filter({ hasText: "pipeline.digest_creation.system" })
        .click()

      const dialog = settingsPage.page.getByRole("dialog")

      // Click Show Default button
      await dialog.getByRole("button", { name: /Show Default/i }).click()

      // Default value section should appear
      await expect(dialog.getByText("Default Value")).toBeVisible()
      await expect(
        dialog.getByText(/You are an AI newsletter curator/)
      ).toBeVisible()
    })

    test("shows Reset to Default button for overridden prompts", async ({
      settingsPage,
    }) => {
      await settingsPage.navigate()

      await settingsPage.page
        .getByRole("button", { name: /Pipeline/i })
        .click()
      await settingsPage.page
        .locator("button")
        .filter({ hasText: "pipeline.digest_creation.system" })
        .click()

      const dialog = settingsPage.page.getByRole("dialog")

      // Should show Reset to Default (prompt has override)
      await expect(
        dialog.getByRole("button", { name: /Reset to Default/i })
      ).toBeVisible()
    })

    test("does not show Reset button for non-overridden prompts", async ({
      settingsPage,
    }) => {
      await settingsPage.navigate()

      await settingsPage.page
        .getByRole("button", { name: /Pipeline/i })
        .click()
      await settingsPage.page
        .locator("button")
        .filter({ hasText: "pipeline.summarization.system" })
        .click()

      const dialog = settingsPage.page.getByRole("dialog")

      // Should NOT show Reset to Default (no override)
      await expect(
        dialog.getByRole("button", { name: /Reset to Default/i })
      ).not.toBeVisible()
    })

    test("closes dialog on Cancel", async ({ settingsPage }) => {
      await settingsPage.navigate()

      await settingsPage.page
        .getByRole("button", { name: /Pipeline/i })
        .click()
      await settingsPage.page
        .locator("button")
        .filter({ hasText: "pipeline.summarization.system" })
        .click()

      const dialog = settingsPage.page.getByRole("dialog")
      await expect(dialog).toBeVisible()

      // Click Cancel
      await dialog.getByRole("button", { name: /Cancel/i }).click()

      // Dialog should close
      await expect(dialog).not.toBeVisible()
    })

    test("detects template variables and displays them", async ({
      settingsPage,
    }) => {
      await settingsPage.navigate()

      await settingsPage.page
        .getByRole("button", { name: /Pipeline/i })
        .click()
      await settingsPage.page
        .locator("button")
        .filter({ hasText: "pipeline.summarization.user_template" })
        .click()

      const dialog = settingsPage.page.getByRole("dialog")

      // Should show detected variables
      await expect(dialog.getByText(/Variables:.*\{title\}/)).toBeVisible()
    })
  })

  test.describe("Test Prompt", () => {
    test("shows test section with variable inputs", async ({
      settingsPage,
    }) => {
      await settingsPage.navigate()

      await settingsPage.page
        .getByRole("button", { name: /Pipeline/i })
        .click()
      await settingsPage.page
        .locator("button")
        .filter({ hasText: "pipeline.digest_creation.system" })
        .click()

      const dialog = settingsPage.page.getByRole("dialog")

      // Open test panel
      await dialog.getByRole("button", { name: /Show Test/i }).click()

      // Should show Render Template button
      await expect(
        dialog.getByRole("button", { name: /Render Template/i })
      ).toBeVisible()
    })

    test("renders template with test variables", async ({
      settingsPage,
    }) => {
      await settingsPage.navigate()

      await settingsPage.page
        .getByRole("button", { name: /Pipeline/i })
        .click()
      await settingsPage.page
        .locator("button")
        .filter({ hasText: "pipeline.digest_creation.system" })
        .click()

      const dialog = settingsPage.page.getByRole("dialog")

      // Open test panel
      await dialog.getByRole("button", { name: /Show Test/i }).click()

      // Click render
      await dialog.getByRole("button", { name: /Render Template/i }).click()

      // Should show rendered output
      await expect(dialog.getByText("Rendered Output")).toBeVisible()
      await expect(
        dialog.getByText(/creating a daily digest for senior engineers/)
      ).toBeVisible()
    })
  })
})
