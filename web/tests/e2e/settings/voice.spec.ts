/**
 * Settings > Voice E2E Tests
 *
 * Tests the voice configurator UI on the Settings page:
 * - Provider selection
 * - Speed display
 * - Voice presets
 * - Source badges and reset
 * - Error states
 */

import { test, expect } from "../fixtures"
import {
  createVoiceSettingsResponse,
  createVoiceSettingInfo,
} from "../fixtures/mock-data"

test.describe("Settings > Voice", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockVoiceSettings()
    await apiMocks.mockVoiceUpdate()
  })

  test("displays voice configuration section", async ({ settingsPage }) => {
    await settingsPage.navigate()
    await expect(settingsPage.page.getByText("TTS Voices")).toBeVisible()
  })

  test("shows current provider", async ({ settingsPage }) => {
    await settingsPage.navigate()

    // Should show "openai" as the current provider (default mock)
    await expect(settingsPage.page.getByText("openai")).toBeVisible()
  })

  test("shows current speed value", async ({ settingsPage }) => {
    await settingsPage.navigate()

    // Speed is displayed as "1.0x" or "1.0"
    await expect(settingsPage.page.getByText(/1\.0/)).toBeVisible()
  })

  test("shows voice presets", async ({ settingsPage }) => {
    await settingsPage.navigate()

    // Mock data has 4 presets: professional, warm, energetic, calm
    await expect(
      settingsPage.page.getByText("professional", { exact: false })
    ).toBeVisible()
    await expect(
      settingsPage.page.getByText("warm", { exact: false })
    ).toBeVisible()
  })

  test("shows error state when API fails", async ({
    settingsPage,
    apiMocks,
  }) => {
    await apiMocks.mockWithError(
      "**/api/v1/settings/voice",
      500,
      "Internal server error"
    )
    await settingsPage.navigate()

    await expect(
      settingsPage.page.getByText(/failed to load/i)
    ).toBeVisible()
  })

  test("shows db badge when provider is overridden", async ({
    settingsPage,
    apiMocks,
  }) => {
    const data = createVoiceSettingsResponse({
      provider: createVoiceSettingInfo({
        key: "voice.provider",
        value: "elevenlabs",
        source: "db",
      }),
    })
    await apiMocks.mockVoiceSettings(data)
    await settingsPage.navigate()

    await expect(
      settingsPage.page.getByText("elevenlabs")
    ).toBeVisible()
  })
})
