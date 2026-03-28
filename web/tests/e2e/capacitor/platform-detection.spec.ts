/**
 * E2E Tests: Platform Detection
 *
 * Verifies that Capacitor native-only features are correctly hidden
 * when running in a web browser. Native-mode testing requires actual
 * Capacitor runtime (Xcode/Android Studio) — see manual test checklist.
 *
 * Task 12.1 — E2E tests for platform detection (web context)
 */

import { test, expect } from "../fixtures"

test.describe("Platform Detection — Web Context", () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.mockAllDefaults()
  })

  test("push notification toggle is hidden on web platform", async ({
    settingsPage,
  }) => {
    await settingsPage.navigate()

    // isNative() returns false in browsers → PushNotificationToggle renders null
    await expect(
      settingsPage.page.getByText("Push Notifications", { exact: true }),
    ).not.toBeVisible()
  })

  test("settings page renders without native-only sections", async ({
    settingsPage,
  }) => {
    await settingsPage.navigate()

    // Standard settings sections should be visible
    await expect(settingsPage.page.locator("main")).toBeVisible()

    // Native-only elements should not be present
    await expect(
      settingsPage.page.getByRole("switch", {
        name: /toggle push notifications/i,
      }),
    ).toHaveCount(0)
  })

  test("app loads cleanly with initShareTarget no-op on web", async ({
    dashboardPage,
  }) => {
    // initShareTarget() is called at module scope in __root.tsx.
    // On web, isNative() returns false — exits immediately with no side effects.
    await dashboardPage.navigate()
    await expect(dashboardPage.page.locator("main")).toBeVisible()

    // No spurious error toasts from share handler
    await expect(
      dashboardPage.page.getByText(/unsupported url scheme/i),
    ).not.toBeVisible()
  })

  test("notification bell renders without push-related errors", async ({
    dashboardPage,
  }) => {
    // NotificationBell.tsx uses useLocalNotificationBridge() which
    // imports from push-notifications.ts — should be no-op on web.
    await dashboardPage.navigate()

    const bell = dashboardPage.page.getByRole("button", {
      name: /notification/i,
    })
    await expect(bell).toBeVisible()
  })

  test("voice input settings visible without native STT crash", async ({
    settingsPage,
  }) => {
    // NativeSTTEngine.isAvailable() returns false on web (catches import error).
    // AutoSTTEngine skips it and selects browser/cloud.
    await settingsPage.navigate()
    await expect(settingsPage.page.locator("main")).toBeVisible()
  })
})
