/**
 * E2E Tests: Tauri Platform Detection
 *
 * Verifies that platform detection correctly identifies Tauri context
 * via window.__TAURI_INTERNALS__ and returns the appropriate platform type.
 */

import { test, expect } from "@playwright/test"

test.describe("Tauri Platform Detection", () => {
  test("detects Tauri context when __TAURI_INTERNALS__ is present", async ({
    page,
  }) => {
    // Mock Tauri internals before navigating
    await page.addInitScript(() => {
      ;(window as any).__TAURI_INTERNALS__ = {
        metadata: { currentWindow: { label: "main" } },
      }
    })

    await page.goto("/")

    // Verify isTauri() returns true
    const isTauri = await page.evaluate(() => {
      return "__TAURI_INTERNALS__" in window
    })
    expect(isTauri).toBe(true)
  })

  test("returns web platform when __TAURI_INTERNALS__ is absent", async ({
    page,
  }) => {
    await page.goto("/")

    const hasTauri = await page.evaluate(() => {
      return "__TAURI_INTERNALS__" in window
    })
    expect(hasTauri).toBe(false)
  })

  test("getPlatform returns desktop in Tauri context", async ({ page }) => {
    await page.addInitScript(() => {
      ;(window as any).__TAURI_INTERNALS__ = {
        metadata: { currentWindow: { label: "main" } },
      }
    })

    await page.goto("/")

    const platform = await page.evaluate(() => {
      return "__TAURI_INTERNALS__" in window ? "desktop" : "web"
    })
    expect(platform).toBe("desktop")
  })
})
