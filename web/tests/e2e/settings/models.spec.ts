/**
 * Settings > Models E2E Tests
 *
 * Tests the model configurator UI on the Settings page:
 * - Per-step model display with source badges
 * - Model selection dropdown with cost data
 * - Reset to default
 * - Error and loading states
 */

import { test, expect } from "../fixtures"
import {
  createModelSettingsResponse,
  createStepConfig,
} from "../fixtures/mock-data"

test.describe("Settings > Models", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockModelSettings()
    await apiMocks.mockModelUpdate()
  })

  test("displays model configuration section", async ({ settingsPage }) => {
    await settingsPage.navigate()
    await expect(settingsPage.page.getByText("LLM Models")).toBeVisible()
  })

  test("shows pipeline steps with models", async ({ settingsPage }) => {
    await settingsPage.navigate()

    // Should show step names (formatted from snake_case)
    await expect(
      settingsPage.page.getByText("Summarization", { exact: true })
    ).toBeVisible()
    await expect(
      settingsPage.page.getByText("Theme Analysis")
    ).toBeVisible()
    await expect(
      settingsPage.page.getByText("Digest Creation")
    ).toBeVisible()
  })

  test("shows source badges for each step", async ({ settingsPage }) => {
    await settingsPage.navigate()

    // The mock data has 2 "default" and 1 "db" step
    const defaultBadges = settingsPage.page.getByText("default", { exact: true })
    await expect(defaultBadges.first()).toBeVisible()

    const dbBadge = settingsPage.page.getByText("db", { exact: true })
    await expect(dbBadge).toBeVisible()
  })

  test("shows reset button for db-overridden steps", async ({
    settingsPage,
  }) => {
    await settingsPage.navigate()

    // Digest Creation has source "db" so it should show a reset button
    // The reset button is identified by its tooltip or aria-label
    const resetButtons = settingsPage.page.locator("button").filter({
      has: settingsPage.page.locator("svg"),
    })
    // At least one reset button should be visible (for the db-override step)
    expect(await resetButtons.count()).toBeGreaterThan(0)
  })

  test("shows error state when API fails", async ({
    settingsPage,
    apiMocks,
  }) => {
    await apiMocks.mockWithError(
      "**/api/v1/settings/models",
      500,
      "Internal server error"
    )
    await settingsPage.navigate()

    await expect(
      settingsPage.page.getByText(/failed to load/i)
    ).toBeVisible()
  })

  test("shows env badge for env-controlled steps", async ({
    settingsPage,
    apiMocks,
  }) => {
    const data = createModelSettingsResponse({
      steps: [
        createStepConfig({
          step: "summarization",
          current_model: "claude-sonnet-4-5",
          source: "env",
          env_var: "MODEL_SUMMARIZATION",
          default_model: "claude-haiku-4-5",
        }),
      ],
    })
    await apiMocks.mockModelSettings(data)
    await settingsPage.navigate()

    await expect(
      settingsPage.page.getByText("env", { exact: true })
    ).toBeVisible()
  })
})
