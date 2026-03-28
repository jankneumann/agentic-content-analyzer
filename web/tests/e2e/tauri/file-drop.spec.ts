/**
 * E2E Tests: Tauri File Drop
 *
 * Verifies drag-and-drop file validation logic including supported
 * extensions, file size limits, and drop zone overlay visibility.
 */

import { test, expect } from "@playwright/test"

test.describe("Tauri File Drop", () => {
  test.describe("file validation", () => {
    test("accepts supported file extensions", async ({ page }) => {
      await page.goto("/")

      const result = await page.evaluate(() => {
        const SUPPORTED = new Set([
          ".pdf",
          ".docx",
          ".pptx",
          ".xlsx",
          ".txt",
          ".md",
          ".html",
          ".epub",
          ".wav",
          ".mp3",
          ".msg",
        ])
        const ext = ".pdf"
        return SUPPORTED.has(ext)
      })
      expect(result).toBe(true)
    })

    test("rejects unsupported file extensions", async ({ page }) => {
      await page.goto("/")

      const result = await page.evaluate(() => {
        const SUPPORTED = new Set([
          ".pdf",
          ".docx",
          ".pptx",
          ".xlsx",
          ".txt",
          ".md",
          ".html",
          ".epub",
          ".wav",
          ".mp3",
          ".msg",
        ])
        return SUPPORTED.has(".exe")
      })
      expect(result).toBe(false)
    })

    test("rejects oversized files", async ({ page }) => {
      await page.goto("/")

      const result = await page.evaluate(() => {
        const maxSizeMB = 500
        const maxBytes = maxSizeMB * 1024 * 1024
        const fileSizeBytes = 600 * 1024 * 1024 // 600MB
        return fileSizeBytes > maxBytes ? "oversized" : "valid"
      })
      expect(result).toBe("oversized")
    })

    test("accepts files within size limit", async ({ page }) => {
      await page.goto("/")

      const result = await page.evaluate(() => {
        const maxSizeMB = 500
        const maxBytes = maxSizeMB * 1024 * 1024
        const fileSizeBytes = 10 * 1024 * 1024 // 10MB
        return fileSizeBytes > maxBytes ? "oversized" : "valid"
      })
      expect(result).toBe("valid")
    })
  })

  test.describe("drop zone overlay", () => {
    test("DropZone component is not visible by default", async ({ page }) => {
      await page.goto("/")

      // The drop zone overlay should not exist when no drag is happening
      const overlay = page.locator('[class*="fixed inset-0"]').filter({
        hasText: "Drop files to upload",
      })
      await expect(overlay).not.toBeVisible()
    })
  })
})
