/**
 * E2E Tests: Push Notification — Web Guard
 *
 * Verifies push notification UI is correctly gated to native platforms.
 * These tests run in a browser where isNative() returns false, confirming
 * the PushNotificationToggle renders null and hooks exit early.
 *
 * Native-mode opt-in flow testing requires actual Capacitor runtime.
 * See manual test checklist (task 12.6).
 *
 * Task 12.3 — E2E tests for push notification opt-in flow
 */

import { test, expect } from "../fixtures"

test.describe("Push Notifications — Web Guard", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("push toggle not rendered in settings on web", async ({
    settingsPage,
  }) => {
    await settingsPage.navigate()

    // PushNotificationToggle returns null when !isAvailable (web)
    await expect(
      settingsPage.page.getByRole("switch", {
        name: /toggle push notifications/i,
      }),
    ).toHaveCount(0)
  })

  test("no push-related text visible in settings on web", async ({
    settingsPage,
  }) => {
    await settingsPage.navigate()

    // None of the push-specific labels should appear
    await expect(
      settingsPage.page.getByText("Push Notifications", { exact: true }),
    ).not.toBeVisible()
    await expect(
      settingsPage.page.getByText("Enabled"),
    ).not.toBeVisible()
    await expect(
      settingsPage.page.getByText("Not set"),
    ).not.toBeVisible()
  })

  test("notification bell renders without push-related errors on web", async ({
    dashboardPage,
  }) => {
    // NotificationBell uses useLocalNotificationBridge() which imports
    // push-notifications.ts — should be no-op on web without crashing.
    await dashboardPage.navigate()

    const bell = dashboardPage.page.getByRole("button", {
      name: /notification/i,
    })
    await expect(bell).toBeVisible()
  })
})
