/**
 * Settings > Connections E2E Tests
 *
 * Tests the connection dashboard on the Settings page:
 * - Service list with status indicators
 * - Overall health indicator
 * - Refresh functionality
 * - Error states
 */

import { test, expect } from "../fixtures"
import {
  createConnectionStatusResponse,
  createServiceStatus,
} from "../fixtures/mock-data"

test.describe("Settings > Connections", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
    await apiMocks.mockConnectionStatus()
  })

  test("displays connection status section", async ({ settingsPage }) => {
    await settingsPage.navigate()
    await expect(
      settingsPage.page.getByText("API Connections")
    ).toBeVisible()
  })

  test("shows all services", async ({ settingsPage }) => {
    await settingsPage.navigate()

    // Default mock has 5 services
    await expect(settingsPage.page.getByText("PostgreSQL")).toBeVisible()
    await expect(settingsPage.page.getByText("Neo4j")).toBeVisible()
    await expect(settingsPage.page.getByText("Anthropic")).toBeVisible()
    await expect(settingsPage.page.getByText("Embeddings")).toBeVisible()
  })

  test("shows latency for services with latency data", async ({
    settingsPage,
  }) => {
    await settingsPage.navigate()

    // PostgreSQL has latency_ms: 5.2 in the mock, component renders Math.round() = 5ms
    await expect(settingsPage.page.getByText(/5ms/)).toBeVisible()
  })

  test("shows overall healthy status", async ({ settingsPage }) => {
    await settingsPage.navigate()

    // The mock data has all_ok: true
    await expect(
      settingsPage.page.getByText(/all connected/i)
    ).toBeVisible()
  })

  test("shows issues when service is unavailable", async ({
    settingsPage,
    apiMocks,
  }) => {
    const data = createConnectionStatusResponse({
      services: [
        createServiceStatus({
          name: "PostgreSQL",
          status: "unavailable",
          details: "Connection refused",
          latency_ms: null,
        }),
      ],
      all_ok: false,
    })
    await apiMocks.mockConnectionStatus(data)
    await settingsPage.navigate()

    await expect(
      settingsPage.page.getByText(/issues detected/i)
    ).toBeVisible()
  })

  test("shows error state when API fails", async ({
    settingsPage,
    apiMocks,
  }) => {
    await apiMocks.mockWithError(
      "**/api/v1/settings/connections*",
      500,
      "Internal server error"
    )
    await settingsPage.navigate()

    await expect(
      settingsPage.page.getByText(/failed to check/i)
    ).toBeVisible()
  })

  test("has a refresh button", async ({ settingsPage }) => {
    await settingsPage.navigate()

    // Look for a button with refresh icon or text
    const refreshButton = settingsPage.page.getByRole("button", {
      name: /refresh/i,
    })
    await expect(refreshButton).toBeVisible()
  })
})
